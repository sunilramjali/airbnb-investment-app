# ONS Price Index of Private Rents (PIPR) — Bronze load (table rebuild + parse + audit).
# Databricks port of etl/ingestion_layer/08_ons_private_rent_load.sql.
# ============================================================
# ONS PRIVATE RENT (PIPR)  —  LOAD (run EVERY load).
# ------------------------------------------------------------
# Depends on 07_ons_private_rent_parse.py (the openpyxl parse function) and on the
# external location `airbnb_raw_ons`.
#
# Rebuilds RAW_ONS_PRIVATE_RENT, then parses the NEWEST .xlsx on S3 and appends one
# faithful row per spreadsheet row (all cells as an ARRAY of TEXT). Rebuild +
# single-file parse keeps the load idempotent — re-running after the monthly Lambda
# refresh yields no duplicates.
#
# The Snowflake original was a .sql file whose step 2 was `CALL BRONZE.LOAD_ONS_PRIVATE_RENT('Table 1', 2)`.
# Databricks has no SQL-invoked Python procedure, so the CALL becomes a function
# call and this orchestration file becomes Python too. See the header of
# 07_ons_private_rent_parse.py for why.
# ============================================================

import importlib
import importlib.util
import os
import sys
from pathlib import Path


def find_project_root(marker: str = "config") -> Path:
    """Walk up from the current directory until a folder containing `marker/` is found."""
    p = Path.cwd().resolve()
    for candidate in [p, *p.parents]:
        if (candidate / marker).is_dir():
            return candidate
    raise FileNotFoundError(f"Could not find '{marker}/' above {p}")


PROJECT_ROOT = find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config.databricks_context
importlib.reload(config.databricks_context)
from config.databricks_context import get_session, table, RAW_PATHS

SCHEMA = "bronze"
PREFIX = f"{RAW_PATHS['ons']}/private-rents/"

# ONS puts 2 title rows above the header on the data tab. Matches the Snowflake
# CALL arguments exactly: CALL BRONZE.LOAD_ONS_PRIVATE_RENT('Table 1', 2).
SHEET_NAME = "Table 1"
SKIP_ROWS = 2


def _load_parser():
    """Import the sibling parse module by path (leading digit => not a valid module name)."""
    spec = importlib.util.spec_from_file_location(
        "ons_parse", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "07_ons_private_rent_parse.py"),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["ons_parse"] = module
    spec.loader.exec_module(module)
    return module


def create_table(session, target: str) -> None:
    """Rebuild the Bronze table.

    Each spreadsheet row -> one table row: the cells as an ARRAY of TEXT (survives
    ONS's multi-row titles / merged headers) + lineage columns. Rebuilt each run
    (OR REPLACE) to keep the load idempotent. SILVER locates the header row and
    reshapes CELLS into typed columns.

    TBLPROPERTIES allowColumnDefaults is required before Delta will accept the
    DEFAULT on _LOAD_TS — Snowflake needed no equivalent opt-in.
    """
    session.sql(f"""
        CREATE OR REPLACE TABLE {target} (
            SHEET             STRING,        -- workbook tab the row came from
            CELLS             ARRAY<STRING>, -- ordered cell values as TEXT (NULLs preserved)
            _FILENAME         STRING,        -- lineage: source file (full s3:// path)
            _FILE_ROW_NUMBER  BIGINT,        -- lineage: 1-based row position within the sheet
            _LOAD_TS          TIMESTAMP_NTZ DEFAULT current_timestamp()
        )
        COMMENT 'Bronze ONS PIPR workbook — faithful, one ARRAY row per sheet row, rebuilt each run.'
        TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')
    """)


def verify(session, target: str) -> None:
    rows, last = session.sql(
        f"SELECT COUNT(*), MAX(_LOAD_TS) FROM {target}"
    ).collect()[0]
    print(f"   RAW_ONS_PRIVATE_RENT: total {rows:,} rows (last load {last})")


def run(session) -> None:
    target = table("RAW_ONS_PRIVATE_RENT", SCHEMA)
    audit = table("LOAD_AUDIT", SCHEMA)

    print(f"[RAW_ONS_PRIVATE_RENT] rebuilding table")
    create_table(session, target)

    parser = _load_parser()
    print(f"[RAW_ONS_PRIVATE_RENT] parsing newest .xlsx under {PREFIX}")
    summary = parser.load_ons_private_rent(
        session, PREFIX, target, audit,
        sheet_name=SHEET_NAME, skip_rows=SKIP_ROWS,
    )
    print(f"   {summary}")

    verify(session, target)


if __name__ == "__main__":
    run(get_session())

# ---------------------------------------------
# Verify (uncomment to run interactively):
#   -- most recent ONS load outcome
#   SELECT * FROM BRONZE.LOAD_AUDIT
#   WHERE TABLE_NAME = 'RAW_ONS_PRIVATE_RENT' ORDER BY LOAD_TS DESC;
#
#   -- row count + first rows: row 3 is the header, data is _FILE_ROW_NUMBER >= 4
#   SELECT COUNT(*) AS rows, MAX(_LOAD_TS) AS last_load FROM BRONZE.RAW_ONS_PRIVATE_RENT;
#   SELECT _FILE_ROW_NUMBER, CELLS
#   FROM BRONZE.RAW_ONS_PRIVATE_RENT ORDER BY _FILE_ROW_NUMBER LIMIT 30;
# ---------------------------------------------
