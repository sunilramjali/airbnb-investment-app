# Run a .sql file against the Databricks serverless SQL warehouse from a laptop.
# Databricks counterpart of config/run_sql_file.py.
# ============================================================
# WHY THIS EXISTS SEPARATELY FROM config/run_sql_file.py
# ------------------------------------------------------------
# config/run_sql_file.py needs an active Snowpark session. There is no equivalent
# local session for Databricks here: `databricks-connect` is not installed and was
# never verified against Free Edition serverless (see LOG.md, Session 3). So this
# module talks to the Statement Execution API through the `databricks` CLI instead,
# which needs nothing installed beyond the CLI that is already configured.
#
# Inside a Databricks notebook you do NOT need this — just use spark.sql(). This is
# for driving the ported .sql files from a terminal.
#
# ⚠️ EACH API CALL IS ITS OWN SESSION. `USE CATALOG` / `USE SCHEMA` do NOT carry
# over between statements, which is why catalog+schema are sent on every request.
# The ported .sql files still open with USE statements so they read naturally and
# work unchanged when pasted into a notebook or the SQL editor.
#
# USAGE
#   python databricks/run_sql.py databricks/ingestion_layer/04_land_registry_load.sql
#   python databricks/run_sql.py --sql "SELECT count(*) FROM airbnb_investment.bronze.raw_listings"
# ============================================================

import json
import os
import subprocess
import sys
import tempfile

WAREHOUSE_ID = "bdef2ebe62faebea"   # Serverless Starter Warehouse (2X-Small)
PROFILE = "airbnb"
CATALOG = "airbnb_investment"
SCHEMA = "bronze"


def _cli(args, **kw):
    return subprocess.run(["databricks", *args], capture_output=True, text=True, **kw)


def run_statement(statement: str, limit: int = 60) -> int:
    """Execute one statement and print its result. Returns 0 on success."""
    payload = {
        "warehouse_id": WAREHOUSE_ID,
        "statement": statement,
        "wait_timeout": "50s",
        "on_wait_timeout": "CONTINUE",
        "catalog": CATALOG,
        "schema": SCHEMA,
    }
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    try:
        proc = _cli(["api", "post", "/api/2.0/sql/statements",
                     "--profile", PROFILE, "--json", f"@{path}"])
    finally:
        os.unlink(path)

    if not proc.stdout.strip():
        print("CLI ERROR:", proc.stderr.strip()[:1500])
        return 1
    try:
        d = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("NON-JSON RESPONSE:", proc.stdout[:1500])
        return 1

    # Long statements return PENDING/RUNNING; poll until they settle.
    stmt_id = d.get("statement_id")
    while d.get("status", {}).get("state") in ("PENDING", "RUNNING"):
        p = _cli(["api", "get", f"/api/2.0/sql/statements/{stmt_id}", "--profile", PROFILE])
        d = json.loads(p.stdout)

    state = d.get("status", {}).get("state")
    if state != "SUCCEEDED":
        print("STATE:", state)
        print(json.dumps(d.get("status", {}).get("error", d))[:2000])
        return 1

    cols = [c["name"] for c in d["manifest"]["schema"].get("columns", [])]
    if not cols:
        print("OK (statement succeeded, no result set)")
        return 0

    print(" | ".join(cols))
    print("-" * min(100, sum(len(c) + 3 for c in cols)))
    for r in (d.get("result", {}).get("data_array") or [])[:limit]:
        print(" | ".join("NULL" if v is None else str(v) for v in r))
    total = d["manifest"].get("total_row_count")
    print(f"({total} rows)" + (f" showing {limit}" if total and total > limit else ""))
    return 0


def split_statements(text: str):
    """Split on top-level semicolons, ignoring those inside strings and comments.

    Hand-rolled rather than using sqlparse (as config/run_sql_file.py does) to keep
    this runnable with no third-party install — the CLI is the only dependency.
    """
    stmts, buf = [], []
    in_s = in_d = in_line = in_block = False
    i = 0
    while i < len(text):
        c = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if in_line:
            in_line = c != "\n"
            buf.append(c)
        elif in_block:
            buf.append(c)
            if c == "*" and nxt == "/":
                buf.append(nxt); i += 1; in_block = False
        elif in_s:
            buf.append(c); in_s = c != "'"
        elif in_d:
            buf.append(c); in_d = c != '"'
        elif c == "-" and nxt == "-":
            in_line = True; buf.append(c)
        elif c == "/" and nxt == "*":
            in_block = True; buf.append(c); buf.append(nxt); i += 1
        elif c == "'":
            in_s = True; buf.append(c)
        elif c == '"':
            in_d = True; buf.append(c)
        elif c == ";":
            stmts.append("".join(buf)); buf = []
        else:
            buf.append(c)
        i += 1
    if "".join(buf).strip():
        stmts.append("".join(buf))
    return stmts


def _is_executable(stmt: str) -> bool:
    """False for blank or comment-only chunks (a trailing '-- Verify' block is its
    own statement after splitting, and the API rejects it as empty SQL)."""
    return any(
        line.strip() and not line.strip().startswith("--")
        for line in stmt.splitlines()
    )


def run_sql_file(sql_file_path: str) -> int:
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")
    with open(sql_file_path, encoding="utf-8") as fh:
        statements = [s for s in split_statements(fh.read()) if _is_executable(s)]

    print(f"{len(statements)} statement(s) in {sql_file_path}\n")
    for i, stmt in enumerate(statements, 1):
        head = " ".join(
            l.strip() for l in stmt.splitlines()
            if l.strip() and not l.strip().startswith("--")
        )[:100]
        print(f"[{i}/{len(statements)}] Running: {head}...")
        if run_statement(stmt) != 0:
            print(f"Statement {i} failed:\n{stmt}")
            return 1
        print()
    print("All statements succeeded.")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__ or "usage: run_sql.py <file.sql> | --sql \"<statement>\"")
        sys.exit(2)
    if args[0] == "--sql":
        sys.exit(run_statement(" ".join(args[1:])))
    sys.exit(run_sql_file(args[0]))
