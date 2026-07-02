# Silver cleaning driver: runs the SILVER DDL + cleaning transforms and records clean-audit rows.
# Co-authored with CoCo
# ============================================================
# SILVER CLEANING DRIVER  —  bronze -> silver.
# ------------------------------------------------------------
# Runs the SQL transforms that turn faithful, all-TEXT BRONZE
# tables into typed, validated SILVER tables, then records a
# row-in vs row-out audit so dropped/deduped rows leave a trace.
#
# PREREQUISITES:
#   1) Bronze loaded (etl/ingestion_layer/02_bronze_load.py).
# Then run this file. It executes, in order:
#   1) 01_silver_ddl.sql                 -> SILVER schema + CLEAN_AUDIT.
#   2) 02_silver_listings.sql            -> SILVER.LISTINGS_CLEANED.
#   3) 03_silver_calendar.sql            -> SILVER.CALENDAR_CLEANED.
#   4) 04_silver_reviews.sql             -> SILVER.REVIEWS_CLEANED.
#   5) 05_silver_neighbourhoods.sql      -> SILVER.NEIGHBOURHOODS_CLEANED.
#   6) 06_silver_neighbourhoods_geo.sql  -> SILVER.NEIGHBOURHOODS_GEO_CLEANED.
#
# Adding another table later = add one (source, target, sql) entry
# to TRANSFORMS below.
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
import config.run_sql_file
importlib.reload(config.snowflake_context)
importlib.reload(config.run_sql_file)
from config.snowflake_context import get_session
from config.run_sql_file import run_sql_file

# Folder holding this layer's SQL files.
SQL_DIR = PROJECT_ROOT / "etl" / "cleaning_layer"

# DDL run once per invocation (idempotent: schema + audit table).
DDL_FILE = SQL_DIR / "01_silver_ddl.sql"

# One entry per cleaning transform, run in order.
#   source      = BRONZE.RAW_* table the transform reads
#   target      = SILVER.*_CLEANED table the transform writes
#   sql         = file that creates `target` (CREATE OR REPLACE TABLE ... AS SELECT)
#   rows_in_sql = OPTIONAL count query for ROWS_IN. Use when the natural input
#                 cardinality is not COUNT(*) of `source` — e.g. the GeoJSON
#                 fan-out, where 1 VARIANT document yields N features. When
#                 omitted, ROWS_IN falls back to COUNT(*) of `source`.
TRANSFORMS = [
    {
        "source": "BRONZE.RAW_LISTINGS",
        "target": "SILVER.LISTINGS_CLEANED",
        "sql": SQL_DIR / "02_silver_listings.sql",
    },
    {
        "source": "BRONZE.RAW_CALENDAR",
        "target": "SILVER.CALENDAR_CLEANED",
        "sql": SQL_DIR / "03_silver_calendar.sql",
    },
    {
        "source": "BRONZE.RAW_REVIEWS",
        "target": "SILVER.REVIEWS_CLEANED",
        "sql": SQL_DIR / "04_silver_reviews.sql",
    },
    {
        "source": "BRONZE.RAW_NEIGHBOURHOODS",
        "target": "SILVER.NEIGHBOURHOODS_CLEANED",
        "sql": SQL_DIR / "05_silver_neighbourhoods.sql",
    },
    {
        "source": "BRONZE.RAW_NEIGHBOURHOODS_GEO",
        "target": "SILVER.NEIGHBOURHOODS_GEO_CLEANED",
        "sql": SQL_DIR / "06_silver_neighbourhoods_geo.sql",
        # 1 VARIANT document -> N GeoJSON features: count the features, not the doc,
        # so ROWS_IN matches ROWS_OUT and ROWS_DROPPED stays meaningful (0).
        "rows_in_sql": "SELECT ARRAY_SIZE(RAW:features) FROM BRONZE.RAW_NEIGHBOURHOODS_GEO",
    },
    {
        "source": "BRONZE.RAW_PRICE_PAID",
        "target": "SILVER.PRICE_PAID_CLEANED",
        "sql": SQL_DIR / "07_silver_price_paid.sql",
    },
    {
        # Overture POIs -> investment-relevant amenities. Requires BRONZE.RAW_OVERTURE_POI,
        # loaded by etl/ingestion_layer/05_overture_poi_load.sql (run before this driver).
        # ROWS_DROPPED here is meaningful: it counts POIs filtered out as non-relevant.
        "source": "BRONZE.RAW_OVERTURE_POI",
        "target": "SILVER.POI_CLEANED",
        "sql": SQL_DIR / "08_silver_poi.sql",
    },
]


def count_rows(session, table: str) -> int:
    """Return COUNT(*) for a fully-qualified table, or 0 if it does not exist yet."""
    try:
        return session.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    except Exception:
        return 0


def count_rows_in(session, transform: dict) -> int:
    """Rows the transform logically consumes. Uses the optional `rows_in_sql`
    override when present (e.g. the GeoJSON fan-out), else COUNT(*) of `source`."""
    rows_in_sql = transform.get("rows_in_sql")
    if rows_in_sql:
        try:
            return session.sql(rows_in_sql).collect()[0][0]
        except Exception:
            return 0
    return count_rows(session, transform["source"])


def record_audit(session, target: str, source: str,
                 rows_in: int, rows_out: int) -> None:
    """Persist one cleaning outcome into SILVER.CLEAN_AUDIT (created by 01_silver_ddl.sql).
    ROWS_DROPPED = rows_in - rows_out captures everything removed by validation + dedup,
    so silently filtered rows leave a durable, queryable trace. Bind params keep table
    names safe inside the INSERT."""
    session.sql(
        """
        INSERT INTO SILVER.CLEAN_AUDIT
            (TABLE_NAME, SOURCE_TABLE, ROWS_IN, ROWS_OUT, ROWS_DROPPED)
        VALUES (?, ?, ?, ?, ?)
        """,
        params=[target, source, rows_in, rows_out, rows_in - rows_out],
    ).collect()


def verify(session, target: str, source: str,
           rows_in: int, rows_out: int) -> None:
    """Print the in/out/dropped summary for one transform."""
    dropped = rows_in - rows_out
    print(f"   {target}: {rows_out:,} rows out "
          f"(from {rows_in:,} in {source}; {dropped:,} dropped)")


# ------------------------------------------------------------
# Orchestration: run DDL once, then each transform in order.
# ------------------------------------------------------------
def run(session, transforms=TRANSFORMS) -> None:
    print(f"[SILVER DDL] {DDL_FILE.name}")
    run_sql_file(session, DDL_FILE)

    for t in transforms:
        source, target, sql_file = t["source"], t["target"], t["sql"]
        print(f"[{target}] cleaning from {source} via {sql_file.name}")

        rows_in = count_rows_in(session, t)              # bronze rows before (override-aware)
        run_sql_file(session, sql_file)                  # rebuild the silver table
        rows_out = count_rows(session, target)           # silver rows after

        record_audit(session, target, source, rows_in, rows_out)
        verify(session