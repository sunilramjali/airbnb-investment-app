# Gold aggregation driver: runs the GOLD dimensions, facts, and app marts in order and verifies row counts.
# Co-authored with CoCo
# ============================================================
# GOLD AGGREGATION DRIVER  —  silver -> gold.
# ------------------------------------------------------------
# Runs the SQL that builds the GOLD star (dimensions + facts)
# and the app-facing consumer marts, then prints a row-count
# summary for every object produced.
#
# PREREQUISITES:
#   1) Silver built (etl/cleaning_layer/cleaning_layer.py).
#   2) Change tracking enabled on the SILVER source tables that
#      feed the dynamic tables (LISTINGS_CLEANED, CALENDAR_CLEANED,
#      POI_CLEANED, NEIGHBOURHOODS_GEO_CLEANED, ONS_PRIVATE_RENT_CLEANED,
#      NEIGHBOURHOOD_ONS_AREA_MAP) — otherwise the dynamic-table refresh fails.
# Then run this file. It executes, in order:
#   1) 01_dimensions.sql  -> GOLD.DIM_* (+ generated DIM_DATE).
#   2) 02_facts.sql       -> GOLD.FCT_*.
#   3) 03_app_marts.sql   -> GOLD.MART_* (app consumer layer).
#
# Adding another gold file later = add one (sql, produces) entry
# to STEPS below.
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
SQL_DIR = PROJECT_ROOT / "etl" / "aggregation_layer"

# One entry per gold SQL file, run in order.
#   sql      = file that builds the objects (CREATE OR REPLACE ...)
#   produces = fully-qualified GOLD objects the file creates, verified after the run
STEPS = [
    {
        "sql": SQL_DIR / "01_dimensions.sql",
        "produces": [
            "GOLD.DIM_LISTING",
            "GOLD.DIM_HOST",
            "GOLD.DIM_NEIGHBOURHOOD",
            "GOLD.DIM_PROPERTY_GROUP",
            "GOLD.DIM_POI",
            "GOLD.DIM_CITY_ASSUMPTIONS",
            "GOLD.DIM_DATE",
        ],
    },
    {
        "sql": SQL_DIR / "02_facts.sql",
        "produces": [
            "GOLD.FCT_CALENDAR_DAILY",
            "GOLD.FCT_LISTING_SNAPSHOT",
            "GOLD.FCT_LISTING_POI",
            "GOLD.FCT_AREA_SALE_PRICE",
            "GOLD.FCT_AREA_RENT",
        ],
    },
    {
        "sql": SQL_DIR / "03_app_marts_core.sql",
        "produces": [
            "GOLD.MART_LISTING_CANDIDATES",
            "GOLD.MART_AREA_OVERVIEW",
            "GOLD.MART_AREA_POI",
            "GOLD.MART_AREA_SEASONAL",
        ],
    },
    {
        "sql": SQL_DIR / "04_app_marts_property.sql",
        "produces": [
            "GOLD.MART_PROPERTY_TYPE",
            "GOLD.MART_BEDROOMS",
            "GOLD.MART_PROPERTY_SEASONAL",
        ],
    },
    {
        "sql": SQL_DIR / "05_app_marts_strategy.sql",
        "produces": [
            "GOLD.MART_ST_VS_LT",
        ],
    },
    {
        "sql": SQL_DIR / "06_app_marts_amenities.sql",
        "produces": [
            "GOLD.MART_AREA_AMENITIES",
            "GOLD.MART_AREA_AMENITY_GAP",
        ],
    },
]


def count_rows(session, table: str) -> int:
    """Return COUNT(*) for a fully-qualified table, or 0 if it does not exist yet."""
    try:
        return session.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    except Exception:
        return 0


# ------------------------------------------------------------
# Orchestration: run each gold file in order, then verify.
# ------------------------------------------------------------
def run(session, steps=STEPS) -> None:
    for step in steps:
        sql_file, produces = step["sql"], step["produces"]
        print(f"[{sql_file.name}] building {', '.join(produces)}")
        run_sql_file(session, sql_file)
        for obj in produces:
            print(f"   {obj}: {count_rows(session, obj):,} rows")
    print("Gold aggregation complete.")


if __name__ == "__main__":
    # Marts build on AIRBNB_APP_WH; dims/facts DDL pins COMPUTE_WH internally.
    session = get_session("query")
    run(session)
