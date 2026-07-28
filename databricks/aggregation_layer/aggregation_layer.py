# Gold aggregation driver: runs the GOLD dimensions, facts, and app marts in order and verifies row counts.
# Databricks port of etl/aggregation_layer/aggregation_layer.py.
# ============================================================
# GOLD AGGREGATION DRIVER  —  silver -> gold.
# ------------------------------------------------------------
# Runs the SQL that builds the GOLD star (dimensions + facts) and the
# app-facing consumer marts, then prints a row-count summary for every object.
#
# PREREQUISITE: Silver built (databricks/cleaning_layer/cleaning_layer.py).
#
# ============================================================
# WHAT CHANGED FROM SNOWFLAKE
# ------------------------------------------------------------
#   get_session("query") -> get_session()
#       The Snowflake driver selected the APP warehouse for the marts while the
#       dims/facts DDL pinned COMPUTE_WH internally. Free Edition is serverless:
#       there is no warehouse to select and no split to preserve.
#
#   run_sql_file(...) -> _run_sql_file below, using spark.sql().
#   two-level SCHEMA.TABLE -> three-level catalog.schema.table.
#
# 🔴 THE SECOND PREREQUISITE IS GONE — AND THAT IS THE POINT.
#    The Snowflake driver required change tracking on six SILVER tables or the
#    dynamic-table refresh would fail. Gold is now plain tables (see
#    01_dimensions.sql for the 5m39s-vs-4.6s evidence), so there is no change
#    tracking to enable and no refresh to fail. The STEPS ordering below carries
#    the dependency DAG, exactly as it always did.
#
# ⚠️ STEPS ORDER IS LOAD-BEARING. 03 builds MART_LISTING_CANDIDATES, which 04
#    and 05 read; 06 reads FCT_/DIM_/SILVER only and is order-independent after
#    03. Do not reorder without checking those reads.
# ============================================================

import importlib
import sys
from pathlib import Path


def find_project_root(marker: str = "config") -> Path:
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
from config.databricks_context import get_session, CATALOG

SQL_DIR = PROJECT_ROOT / "databricks" / "aggregation_layer"
G = f"{CATALOG}.gold"

# One entry per gold SQL file, run in order.
#   sql      = file that builds the objects
#   produces = fully-qualified GOLD objects the file creates, verified after the run
STEPS = [
    {
        "sql": SQL_DIR / "01_dimensions.sql",
        "produces": [
            f"{G}.DIM_LISTING",
            f"{G}.DIM_HOST",
            f"{G}.DIM_NEIGHBOURHOOD",
            f"{G}.DIM_PROPERTY_GROUP",
            f"{G}.DIM_POI",
            f"{G}.DIM_CITY_ASSUMPTIONS",
            f"{G}.DIM_DATE",
        ],
    },
    {
        "sql": SQL_DIR / "02_facts.sql",
        "produces": [
            f"{G}.FCT_CALENDAR_DAILY",
            f"{G}.FCT_LISTING_SNAPSHOT",
            f"{G}.FCT_LISTING_POI",
            f"{G}.FCT_AREA_SALE_PRICE",
            f"{G}.FCT_AREA_RENT",
        ],
    },
    {
        "sql": SQL_DIR / "03_app_marts_core.sql",
        "produces": [
            f"{G}.MART_LISTING_CANDIDATES",
            f"{G}.MART_AREA_OVERVIEW",
            f"{G}.MART_AREA_POI",
            f"{G}.MART_AREA_SEASONAL",
        ],
    },
    {
        "sql": SQL_DIR / "04_app_marts_property.sql",
        "produces": [
            f"{G}.MART_PROPERTY_TYPE",
            f"{G}.MART_BEDROOMS",
            f"{G}.MART_PROPERTY_SEASONAL",
        ],
    },
    {
        "sql": SQL_DIR / "05_app_marts_strategy.sql",
        "produces": [f"{G}.MART_ST_VS_LT"],
    },
    {
        "sql": SQL_DIR / "06_app_marts_amenities.sql",
        "produces": [
            f"{G}.MART_AREA_AMENITIES",
            f"{G}.MART_AREA_AMENITY_GAP",
        ],
    },
]


def _split_statements(text: str):
    """Reuse the dependency-free splitter from databricks/run_sql.py."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "db_run_sql", str(PROJECT_ROOT / "databricks" / "run_sql.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [s for s in mod.split_statements(text) if mod._is_executable(s)]


def _run_sql_file(session, path: Path) -> None:
    for stmt in _split_statements(path.read_text(encoding="utf-8")):
        session.sql(stmt).collect()


def count_rows(session, table: str) -> int:
    """COUNT(*) for a fully-qualified table, or 0 if it does not exist yet.

    ⚠️ Returns 0 on ANY failure, as the Snowflake original did — but it now
    WARNS. A silent 0 in the summary would read as an empty mart rather than a
    broken query."""
    try:
        return session.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    except Exception as e:
        print(f"   WARNING: count_rows({table}) failed, reporting 0 -> {e}")
        return 0


def run(session, steps=STEPS) -> None:
    for step in steps:
        sql_file, produces = step["sql"], step["produces"]
        print(f"[{sql_file.name}] building {', '.join(o.split('.')[-1] for o in produces)}")
        _run_sql_file(session, sql_file)
        for obj in produces:
            print(f"   {obj}: {count_rows(session, obj):,} rows")
    print("Gold aggregation complete.")


if __name__ == "__main__":
    run(get_session())
