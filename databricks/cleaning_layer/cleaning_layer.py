# Silver cleaning driver: runs the SILVER DDL + cleaning transforms and records clean-audit rows.
# Databricks port of etl/cleaning_layer/cleaning_layer.py.
# ============================================================
# SILVER CLEANING DRIVER  —  bronze -> silver.
# ------------------------------------------------------------
# Runs the SQL transforms that turn faithful, all-TEXT BRONZE tables into
# typed, validated SILVER tables, then records a row-in vs row-out audit so
# dropped/deduped rows leave a trace.
#
# PREREQUISITE: Bronze loaded (databricks/ingestion_layer/, 9 of 9 tables).
#
# ============================================================
# WHAT CHANGED FROM SNOWFLAKE
# ------------------------------------------------------------
#   get_session("dev") -> get_session()   (no warehouse to select on serverless)
#   run_sql_file(...)  -> _run_sql_file below, using spark.sql()
#       config/run_sql_file.py needs sqlparse and a Snowpark session. The
#       statement splitter is reused from databricks/run_sql.py instead, which
#       is dependency-free.
#   two-level SCHEMA.TABLE -> three-level catalog.schema.table
#
# 🔴 THE rows_in_sql OVERRIDES WERE SNOWFLAKE SQL AND HAD TO BE PORTED TOO.
#    This is the easiest thing in the whole layer to miss. count_rows_in()
#    catches every exception and returns 0, so an unported override does NOT
#    fail the run — it silently records ROWS_IN = 0, which then makes
#    ROWS_DROPPED negative and the audit meaningless. Three of the four needed
#    real edits (LATERAL FLATTEN, ARRAY_SIZE, three-level names).
#    The helpers now WARN on failure instead of failing silently.
#
# ⚠️ 09's source changed: BRONZE.RAW_CODE_POINT -> BRONZE.RAW_ONSPD (ONSPD
#    replaces the Ordnance Survey Code-Point Open share). See file 09.
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

SQL_DIR = PROJECT_ROOT / "databricks" / "cleaning_layer"
DDL_FILE = SQL_DIR / "01_silver_ddl.sql"

B = f"{CATALOG}.bronze"
S = f"{CATALOG}.silver"

# One entry per cleaning transform, run in order.
#   source      = table the transform reads
#   target      = silver table it writes
#   sql         = file that creates `target`
#   rows_in_sql = OPTIONAL count query for ROWS_IN, when the natural input
#                 cardinality is not COUNT(*) of `source` (fan-outs, unpivots).
TRANSFORMS = [
    {"source": f"{B}.raw_listings",       "target": f"{S}.listings_cleaned",
     "sql": SQL_DIR / "02_silver_listings.sql"},
    {"source": f"{B}.raw_calendar",       "target": f"{S}.calendar_cleaned",
     "sql": SQL_DIR / "03_silver_calendar.sql"},
    {"source": f"{B}.raw_reviews",        "target": f"{S}.reviews_cleaned",
     "sql": SQL_DIR / "04_silver_reviews.sql"},
    {"source": f"{B}.raw_neighbourhoods", "target": f"{S}.neighbourhoods_cleaned",
     "sql": SQL_DIR / "05_silver_neighbourhoods.sql"},
    {
        "source": f"{B}.raw_neighbourhoods_geo",
        "target": f"{S}.neighbourhoods_geo_cleaned",
        "sql": SQL_DIR / "06_silver_neighbourhoods_geo.sql",
        # 3 VARIANT documents -> 108 features. Count the FEATURES so ROWS_IN
        # matches ROWS_OUT and ROWS_DROPPED stays meaningful (0).
        # ⚠️ Snowflake used `SELECT ARRAY_SIZE(RAW:features)` and read row [0][0].
        # That silently counted ONE city's features and ignored the other two.
        # Exploding and counting is both correct and city-count independent.
        "rows_in_sql": f"SELECT count(*) FROM {B}.raw_neighbourhoods_geo, "
                       f"LATERAL variant_explode(raw:features)",
    },
    {"source": f"{B}.raw_price_paid",     "target": f"{S}.price_paid_cleaned",
     "sql": SQL_DIR / "07_silver_price_paid.sql"},
    {
        # ROWS_DROPPED here is meaningful: POIs filtered out as non-relevant.
        "source": f"{B}.raw_overture_poi", "target": f"{S}.poi_cleaned",
        "sql": SQL_DIR / "08_silver_poi.sql",
    },
    {
        # ⚠️ SOURCE CHANGED: was BRONZE.RAW_CODE_POINT (Ordnance Survey share).
        # Clean-only: no filter. ROWS_DROPPED should be 0.
        "source": f"{B}.raw_onspd",        "target": f"{S}.code_point_cleaned",
        "sql": SQL_DIR / "09_silver_code_point.sql",
    },
    {
        "source": f"{S}.listings_cleaned", "target": f"{S}.property_group_map",
        "sql": SQL_DIR / "10_silver_property_group_map.sql",
        "rows_in_sql": f"SELECT count(DISTINCT property_type) FROM {S}.listings_cleaned",
    },
    {
        "source": f"{S}.listings_cleaned", "target": f"{S}.listing_amenities",
        "sql": SQL_DIR / "11_silver_amenities.sql",
        # total amenity occurrences (the fan-out count), so ROWS_DROPPED is
        # just the blank/null amenities. LATERAL FLATTEN -> variant_explode.
        "rows_in_sql": f"SELECT count(*) FROM {S}.listings_cleaned l, "
                       f"LATERAL variant_explode(try_parse_json(l.AMENITIES)) f",
    },
    {
        # ROWS_DROPPED = postcodes that fell outside every neighbourhood polygon,
        # PLUS the 24,012 with no grid reference (GEOM IS NULL). Both meaningful.
        "source": f"{S}.code_point_cleaned", "target": f"{S}.postcode_neighbourhood_map",
        "sql": SQL_DIR / "12_silver_postcode_neighbourhood_map.sql",
    },
    {
        "source": f"{B}.raw_ons_private_rent", "target": f"{S}.ons_private_rent_cleaned",
        "sql": SQL_DIR / "13_silver_ons_private_rent.sql",
        # scoped wide rows x 9 breakdowns = theoretical max, so ROWS_DROPPED =
        # null/absent measure cells that produced no row.
        "rows_in_sql": f"SELECT count(*) * 9 FROM {B}.raw_ons_private_rent "
                       f"WHERE _FILE_ROW_NUMBER >= 4 AND ("
                       f"TRIM(CELLS[1]::STRING) = 'E06000023' "
                       f"OR TRIM(CELLS[1]::STRING) BETWEEN 'E08000001' AND 'E08000010' "
                       f"OR TRIM(CELLS[1]::STRING) LIKE 'E09%' "
                       f"OR TRIM(CELLS[1]::STRING) = 'E12000007')",
    },
    {
        # One row per neighbourhood. City of London resolves to a NULL ONS code
        # but IS still emitted, so ROWS_DROPPED should be 0, not 1.
        "source": f"{S}.neighbourhoods_geo_cleaned", "target": f"{S}.neighbourhood_ons_area_map",
        "sql": SQL_DIR / "14_silver_neighbourhood_ons_area_map.sql",
        "rows_in_sql": f"SELECT count(DISTINCT NEIGHBOURHOOD) FROM {S}.neighbourhoods_geo_cleaned",
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

    ⚠️ Returns 0 on ANY failure, exactly as the Snowflake original did — but it
    now WARNS. A silent 0 here makes ROWS_DROPPED wrong without failing the run,
    which is precisely how an unported rows_in_sql would hide."""
    try:
        return session.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    except Exception as e:
        print(f"   WARNING: count_rows({table}) failed, recording 0 -> {e}")
        return 0


def count_rows_in(session, transform: dict) -> int:
    """Rows the transform logically consumes: the rows_in_sql override when
    present (fan-outs, unpivots), else COUNT(*) of `source`."""
    rows_in_sql = transform.get("rows_in_sql")
    if rows_in_sql:
        try:
            return session.sql(rows_in_sql).collect()[0][0]
        except Exception as e:
            print(f"   WARNING: rows_in_sql failed for {transform['target']}, "
                  f"recording 0 -> {e}")
            return 0
    return count_rows(session, transform["source"])


def record_audit(session, target: str, source: str,
                 rows_in: int, rows_out: int) -> None:
    """Persist one cleaning outcome into SILVER.CLEAN_AUDIT.

    Values are inlined rather than bound: Snowpark's `params=` has no portable
    spark.sql() equivalent across runtimes. Safe here because every value is
    either an int or a table name from TRANSFORMS above — none is user input.
    Quotes are escaped anyway rather than relying on that."""
    t, s = target.replace("'", "''"), source.replace("'", "''")
    session.sql(f"""
        INSERT INTO {S}.CLEAN_AUDIT
            (TABLE_NAME, SOURCE_TABLE, ROWS_IN, ROWS_OUT, ROWS_DROPPED)
        VALUES ('{t}', '{s}', {int(rows_in)}, {int(rows_out)}, {int(rows_in - rows_out)})
    """).collect()


def verify(target: str, source: str, rows_in: int, rows_out: int) -> None:
    dropped = rows_in - rows_out
    print(f"   {target}: {rows_out:,} rows out "
          f"(from {rows_in:,} in {source}; {dropped:,} dropped)")


def run(session, transforms=TRANSFORMS) -> None:
    print(f"[SILVER DDL] {DDL_FILE.name}")
    _run_sql_file(session, DDL_FILE)

    for t in transforms:
        source, target, sql_file = t["source"], t["target"], t["sql"]
        print(f"[{target}] cleaning from {source} via {sql_file.name}")

        rows_in = count_rows_in(session, t)
        _run_sql_file(session, sql_file)
        rows_out = count_rows(session, target)
        record_audit(session, target, source, rows_in, rows_out)
        verify(target, source, rows_in, rows_out)

    print("Silver cleaning complete.")


if __name__ == "__main__":
    run(get_session())
