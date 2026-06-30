# Setup runner that bootstraps a fresh account then runs all setup SQL in order.
# Co-authored with CoCo
# ============================================================
# Setup runner — executes all setup/*.sql files in order,
# server-side from the live workspace stage.
# ============================================================

# import packages
import sys                # interact with current Python env
import importlib          # force-reload modules during development
from pathlib import Path  # object-oriented file pathing

# ---- locate project root & enable config/ imports ----
def find_project_root(marker: str = "config") -> Path:
    """Walk up from the current directory until a folder containing `marker/` is found."""
    p = Path.cwd().resolve()
    for candidate in [p, *p.parents]:
        if (candidate / marker).is_dir():
            return candidate
    raise FileNotFoundError(f"Could not find '{marker}/' above {p}")

PROJECT_ROOT = find_project_root()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))  # give project imports priority

# ---- import helpers (reloaded fresh so config/ edits are picked up) ----
import config.snowflake_context
importlib.reload(config.snowflake_context)
from config.snowflake_context import get_session, confirm_warehouse, workspace_stage_path

# ---- connect (bootstrap: no warehouse/db context — they don't exist yet) ----
session = get_session(set_context=False)

# ---- locate setup files on the LIVE workspace stage ----
# The kernel's local file mount is a frozen snapshot from session start;
# the live stage always reflects current saved edits — no kernel restart needed.
WORKSPACE_STAGE = workspace_stage_path("setup")

listed = session.sql(f"LIST '{WORKSPACE_STAGE}/'").collect()
sql_files = sorted(
    row[0].rsplit("/", 1)[-1]              # keep just the filename
    for row in listed
    if row[0].lower().endswith(".sql")
)

if not sql_files:
    raise FileNotFoundError(f"No .sql files found on stage: {WORKSPACE_STAGE}")

# ---- run each setup file in order, server-side ----
for i, sql_file in enumerate(sql_files, 1):
    print(f"[{i}/{len(sql_files)}] Running setup file: {sql_file}")
    try:
        session.sql(f"EXECUTE IMMEDIATE FROM '{WORKSPACE_STAGE}/{sql_file}'").collect()
    except Exception as e:
        raise RuntimeError(f"Setup file '{sql_file}' failed") from e

# ---- set context now that the warehouse + database exist, then verify ----
from config.snowflake_context import WAREHOUSES, DATABASE
session.sql(f"USE WAREHOUSE {WAREHOUSES['dev']}").collect()
session.sql(f"USE DATABASE {DATABASE}").collect()
confirm_warehouse(session)
print("Setup Complete.")