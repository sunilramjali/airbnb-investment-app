# ============================================================
# BRONZE LOADER  —  the generic "how" of ingestion.
# ------------------------------------------------------------
# Reads config/ingestion_manifest.py and loads every dataset for
# every city into the BRONZE schema, faithfully (no cleaning).
#
# PREREQUISITES (run once, in this order):
#   1) etl/01_bronze_ddl.sql  -> creates file formats + RAW_STAGE.
#   2) Upload each city's files to @BRONZE.RAW_STAGE/<city>/.
# Then run this file.
#
# Lineage is captured per row via _FILENAME (path encodes the city),
# _FILE_ROW_NUMBER, and _LOAD_TS. City is therefore a runtime parameter,
# not a hardcoded value.
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
import config.ingestion_manifest
importlib.reload(config.snowflake_context)
importlib.reload(config.ingestion_manifest)
from config.snowflake_context import get_session
from config.ingestion_manifest import CITIES, DATASETS

# Schema + file formats created by 01_bronze_ddl.sql
SCHEMA      = "BRONZE"
CSV_FORMAT  = "BRONZE.CSV_HDR_FF"
JSON_FORMAT = "BRONZE.GEOJSON_FF"


def stage_path(city: str, file: str) -> str:
    """Build the stage location for one city's file."""
    return f"@{SCHEMA}.RAW_STAGE/{city}/{file}"


# ------------------------------------------------------------
# CSV path: use INFER_SCHEMA only to DISCOVER column NAMES from the
# FIRST city, but FORCE every column to TEXT. This keeps Bronze
# faithful and deterministic:
#   - nothing can fail to load (every value is valid as a string),
#   - the schema does not depend on sampled values (e.g. "$1,250.00"
#     prices no longer flip a column to NUMBER vs TEXT by accident),
#   - a new city / monthly snapshot can't break the load via drift.
# Real typing/casting happens explicitly in SILVER (TRY_CAST), where a
# failed cast becomes a NULL we can count — not a row that vanishes.
# ------------------------------------------------------------
def create_csv_table(session, table: str, sample_location: str) -> None:
    """Create the table shell with all-TEXT columns (names discovered via
    INFER_SCHEMA, types overridden to TEXT), plus audit columns."""
    session.sql(f"""
        CREATE OR REPLACE TABLE {SCHEMA}.{table}
        USING TEMPLATE (
            SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
                       'COLUMN_NAME', COLUMN_NAME,
                       'TYPE',        'TEXT',   -- override INFER_SCHEMA's guess
                       'NULLABLE',    TRUE
                   ))
            WITHIN GROUP (ORDER BY ORDER_ID)
            FROM TABLE(
                INFER_SCHEMA(
                    LOCATION    => '{sample_location}',
                    FILE_FORMAT => '{CSV_FORMAT}'
                )
            )
        )
    """).collect()

    session.sql(f"""
        ALTER TABLE {SCHEMA}.{table} ADD COLUMN
            _FILENAME        STRING,
            _FILE_ROW_NUMBER NUMBER,
            _LOAD_TS         TIMESTAMP_NTZ
    """).collect()


def copy_csv(session, table: str, location: str) -> list:
    """Append one CSV file into an existing table, matching by header name.
    Returns the COPY result rows (per file: rows_parsed / rows_loaded / errors_seen)."""
    return session.sql(f"""
        COPY INTO {SCHEMA}.{table}
        FROM '{location}'
        FILE_FORMAT = (FORMAT_NAME = '{CSV_FORMAT}')
        MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
        INCLUDE_METADATA = (
            _FILENAME        = METADATA$FILENAME,
            _FILE_ROW_NUMBER = METADATA$FILE_ROW_NUMBER,
            _LOAD_TS         = METADATA$START_SCAN_TIME
        )
        ON_ERROR = CONTINUE
    """).collect()


# ------------------------------------------------------------
# GeoJSON path: one VARIANT column (the whole FeatureCollection)
# plus audit columns. Flattening happens in SILVER. ABORT_STATEMENT
# because a single malformed object means the file is unusable.
# ------------------------------------------------------------
def create_geojson_table(session, table: str) -> None:
    session.sql(f"""
        CREATE OR REPLACE TABLE {SCHEMA}.{table} (
            RAW       VARIANT,
            _FILENAME STRING,
            _LOAD_TS  TIMESTAMP_NTZ
        )
    """).collect()


def copy_geojson(session, table: str, location: str) -> list:
    return session.sql(f"""
        COPY INTO {SCHEMA}.{table} (RAW, _FILENAME, _LOAD_TS)
        FROM (
            SELECT $1, METADATA$FILENAME, METADATA$START_SCAN_TIME
            FROM '{location}' (FILE_FORMAT => '{JSON_FORMAT}')
        )
        ON_ERROR = ABORT_STATEMENT
    """).collect()


def report_copy(results: list) -> None:
    """Print the per-file outcome of a COPY (rows loaded + any skipped rows).
    The COPY result itself is the source of truth here — more reliable than VALIDATE,
    which does not support MATCH_BY_COLUMN_NAME loads."""
    for r in results:
        row = {k.lower(): v for k, v in r.as_dict().items()}
        if "rows_loaded" in row:                       # a file was processed
            errors = row.get("errors_seen") or 0
            fname = str(row.get("file", "")).rsplit("/", 1)[-1]
            flag = f"   WARNING: {errors} row(s) skipped" if errors else ""
            print(f"   {fname}: {row['rows_loaded']:,} rows loaded{flag}")
        else:                                          # e.g. "0 files processed"
            print(f"   {row.get('status', r)}")


def record_audit(session, table: str, results: list) -> None:
    """Persist each COPY result row into BRONZE.LOAD_AUDIT so rows skipped by
    ON_ERROR = CONTINUE (errors_seen) leave a durable, queryable trace instead
    of disappearing when the notebook closes. Bind params are used so error
    text containing quotes can't break the INSERT. Created by 01_bronze_ddl.sql."""
    for r in results:
        row = {k.lower(): v for k, v in r.as_dict().items()}
        if "rows_loaded" not in row:          # non-file status row (e.g. "0 files processed")
            continue
        session.sql(
            f"""
            INSERT INTO {SCHEMA}.LOAD_AUDIT
                (TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED,
                 ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params=[
                table,
                str(row.get("file", "")),
                row.get("status"),
                row.get("rows_parsed"),
                row.get("rows_loaded"),
                row.get("errors_seen") or 0,
                row.get("first_error"),
                row.get("first_error_line"),
            ],
        ).collect()


def verify(session, table: str) -> None:
    """Print the final total row count for the table."""
    rows = session.sql(f"SELECT COUNT(*) FROM {SCHEMA}.{table}").collect()[0][0]
    print(f"   {table}: total {rows:,} rows")


# ------------------------------------------------------------
# Orchestration: loop datasets x cities.
# ------------------------------------------------------------
def run(session, datasets=DATASETS, cities=CITIES) -> None:
    for ds in datasets:
        table, fmt, file = ds["name"], ds["format"], ds["file"]
        locations = [stage_path(c, file) for c in cities]
        print(f"[{table}] loading {len(cities)} city/cities from '{file}' ({fmt})")

        if fmt == "csv":
            create_csv_table(session, table, locations[0])  # infer once from first city
            for loc in locations:
                results = copy_csv(session, table, loc)
                report_copy(results)
                record_audit(session, table, results)
        elif fmt == "geojson":
            create_geojson_table(session, table)
            for loc in locations:
                results = copy_geojson(session, table, loc)
                report_copy(results)
                record_audit(session, table, results)
        else:
            raise ValueError(f"Unknown format '{fmt}' for dataset '{table}'")

        verify(session, table)

    print("Bronze ingestion complete.")


if __name__ == "__main__":
    session = get_session("dev")
    run(session)
