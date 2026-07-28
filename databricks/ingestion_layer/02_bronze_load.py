# Bronze loader: ingests every dataset for every city from S3 into BRONZE.
# Databricks port of etl/ingestion_layer/02_bronze_load.py.
# ============================================================
# BRONZE LOADER  —  the generic "how" of ingestion.
# ------------------------------------------------------------
# Reads config/ingestion_manifest.py (SHARED with the Snowflake loader — it is
# platform-agnostic) and loads every dataset for every city into the BRONZE
# schema, faithfully (no cleaning).
#
# PREREQUISITES (run once, in this order):
#   1) databricks/ingestion_layer/01_bronze_ddl.sql  -> creates LOAD_AUDIT.
#   2) A Lambda uploads each city's snapshot to
#        s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/<city>/snapshot_date=<YYYY-MM-DD>/<dataset>/<file>.
# Then run this file.
#
# The dated snapshot folder changes every quarter as new data lands, so the
# loader resolves the LATEST snapshot per city at runtime (see latest_snapshot)
# rather than hardcoding a date.
#
# Lineage is captured per row via _FILENAME (path encodes city + snapshot),
# _FILE_ROW_NUMBER, and _LOAD_TS. City and snapshot are therefore runtime
# parameters, not hardcoded values.
#
# ============================================================
# SNOWFLAKE -> DATABRICKS TRANSLATION NOTES
# ------------------------------------------------------------
#   @BRONZE.RAW_STAGE/<city>/     -> s3://.../raw/inside_airbnb/<city>/  (external
#                                    location airbnb_raw; no @STAGE indirection)
#   LIST @stage                   -> LIST 's3://...'   (same statement, real URL)
#   INFER_SCHEMA + USING TEMPLATE -> DROPPED, and the port is SIMPLER than the
#     with every TYPE overridden      original. Snowflake needed INFER_SCHEMA to
#     to TEXT                         discover column NAMES and then had to fight it
#                                     to stop it guessing types. Spark's CSV reader
#                                     with inferSchema=false returns EVERY column as
#                                     STRING already, reading names from the header.
#                                     Same all-TEXT Bronze discipline, no template.
#   COPY INTO ... MATCH_BY_COLUMN_NAME
#                                 -> unionByName(allowMissingColumns=True) across
#                                    cities, which is the same "align by header name,
#                                    tolerate drift" behaviour.
#   METADATA$FILENAME             -> _metadata.file_path
#   METADATA$START_SCAN_TIME      -> current_timestamp()
#   METADATA$FILE_ROW_NUMBER      -> NO EQUIVALENT. See _FILE_ROW_NUMBER note below.
#   ON_ERROR = CONTINUE           -> mode=PERMISSIVE + rescuedDataColumn, so bad
#                                    input is captured rather than dropped silently.
#   NULL_IF = ('','NULL','null','N/A')
#                                 -> applied explicitly in _normalise_nulls(); Spark's
#                                    CSV reader accepts only ONE nullValue, so the
#                                    remaining markers are normalised after the read.
#                                    Without this, 'N/A' would survive as a literal
#                                    string here but be NULL in Snowflake.
# ============================================================

# import packages
import sys                # interact with current Python env
import importlib          # force-reload modules during development
from pathlib import Path  # object-oriented file pathing

from pyspark.sql import functions as F
from pyspark.sql import Window


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
import config.databricks_context
import config.ingestion_manifest
importlib.reload(config.databricks_context)
importlib.reload(config.ingestion_manifest)
from config.databricks_context import get_session, use_schema, table, RAW_PATHS
from config.ingestion_manifest import CITIES, DATASETS

SCHEMA = "bronze"
RAW_ROOT = RAW_PATHS["inside_airbnb"]   # s3://.../raw/inside_airbnb

# Snowflake's CSV_HDR_FF, expressed as Spark reader options.
# COMPRESSION=AUTO has no counterpart: Spark decompresses .gz by extension.
CSV_OPTIONS = {
    "header": "true",                  # PARSE_HEADER = TRUE
    "inferSchema": "false",            # every column lands as STRING (the all-TEXT rule)
    "quote": '"',                      # FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    "escape": '"',                     # doubled quotes inside quoted fields
    "multiLine": "true",               # newlines inside quoted text fields
    "mode": "PERMISSIVE",              # ON_ERROR = CONTINUE (keep going, don't abort)
    "ignoreLeadingWhiteSpace": "true",  # TRIM_SPACE = TRUE
    "ignoreTrailingWhiteSpace": "true",
    "encoding": "UTF-8",               # ENCODING = 'UTF8'
    "rescuedDataColumn": "_RESCUED",   # where malformed / extra input is parked
}

# Snowflake's NULL_IF list. Spark's CSV reader takes a single nullValue, so the
# full set is applied after the read instead (see _normalise_nulls).
NULL_MARKERS = ["", "NULL", "null", "N/A"]

SNAPSHOT_PREFIX = "snapshot_date="   # Hive-style partition folder, e.g. snapshot_date=2025-09-14


def _is_snapshot_folder(segment: str) -> bool:
    """True for a Hive-style snapshot folder: 'snapshot_date=YYYY-MM-DD'."""
    if not segment.startswith(SNAPSHOT_PREFIX):
        return False
    d = segment[len(SNAPSHOT_PREFIX):]
    return (
        len(d) == 10 and d[4] == "-" and d[7] == "-"
        and d[:4].isdigit() and d[5:7].isdigit() and d[8:10].isdigit()
    )


def latest_snapshot(session, city: str) -> str:
    """Return the newest 'snapshot_date=YYYY-MM-DD' folder name under a city.

    The quarterly Lambda adds a new
    s3://.../inside_airbnb/<city>/snapshot_date=<YYYY-MM-DD>/ folder each load;
    we LIST the city prefix, collect the snapshot_date= folder segments, and
    pick the most recent. The constant prefix + ISO date sort lexically, so
    each city resolves its own newest snapshot independently.

    Ports from Snowflake UNCHANGED apart from the path: Databricks LIST returns a
    `path` column where Snowflake returned `name`, and the value is a full s3:// URL
    rather than a stage-relative one — but the segment-splitting logic is identical.
    """
    rows = session.sql(f"LIST '{RAW_ROOT}/{city}/'").collect()
    snaps = set()
    for r in rows:
        for seg in str(r["path"]).split("/"):
            if _is_snapshot_folder(seg):
                snaps.add(seg)
    if not snaps:
        raise FileNotFoundError(
            f"No 'snapshot_date=YYYY-MM-DD' folder found under {city}/ at {RAW_ROOT}"
        )
    return sorted(snaps)[-1]


def file_path(city: str, snapshot: str, dataset_dir: str, file: str) -> str:
    """Build the S3 location for one file: <city>/<snapshot>/<dataset_dir>/<file>."""
    return f"{RAW_ROOT}/{city}/{snapshot}/{dataset_dir}/{file}"


def _normalise_nulls(df, columns):
    """Apply Snowflake's NULL_IF = ('', 'NULL', 'null', 'N/A') to the given columns.

    Snowflake normalised all four markers to NULL at COPY time. Spark's CSV reader
    exposes only `nullValue` (one string) and `emptyValue`, so the rest are handled
    here. Skipping this would leave 'N/A' as a literal string in Bronze where
    Snowflake stored NULL — a silent parity break that Silver's TRY_CAST would hide
    for typed columns but NOT for ones that stay TEXT.
    """
    return df.select(*[
        F.when(F.col(f"`{c}`").isin(NULL_MARKERS), None).otherwise(F.col(f"`{c}`")).alias(c)
        if c in columns else F.col(f"`{c}`")
        for c in df.columns
    ])


# ------------------------------------------------------------
# CSV path: read every column as TEXT. This keeps Bronze
# faithful and deterministic:
#   - nothing can fail to load (every value is valid as a string),
#   - the schema does not depend on sampled values (e.g. "$1,250.00"
#     prices no longer flip a column to NUMBER vs TEXT by accident),
#   - a new city / monthly snapshot can't break the load via drift.
# Real typing/casting happens explicitly in SILVER (try_cast), where a
# failed cast becomes a NULL we can count — not a row that vanishes.
#
# Snowflake reached this with INFER_SCHEMA + USING TEMPLATE + a forced TEXT
# override. Spark gets there by simply not inferring, which is both simpler and
# stricter — there is no sampling step that could behave differently per city.
# ------------------------------------------------------------
def read_csv_city(session, location: str):
    """Read one city's CSV as all-TEXT, with lineage columns attached."""
    df = session.read.options(**CSV_OPTIONS).csv(location)

    source_cols = [c for c in df.columns if c != "_RESCUED"]
    df = _normalise_nulls(df, source_cols)

    # _FILE_ROW_NUMBER — synthetic. Snowflake's METADATA$FILE_ROW_NUMBER gave the
    # PHYSICAL line number within the file; Databricks exposes no such value.
    # row_number() over the file gives a stable, unique row id per file, which is
    # what every downstream consumer actually uses it for (it appears only in Silver
    # SELECT lists, never in a WHERE or join — verified before choosing this).
    #
    # ⚠️ It is NOT a file line number. Ordering reflects Spark's read order, not the
    # order of lines in the CSV. Do not use it to locate a row in the source file,
    # and do not compare it against Snowflake's values row-for-row.
    ordering = F.monotonically_increasing_id()
    per_file = Window.partitionBy("_FILENAME").orderBy(ordering)

    return (
        df.withColumn("_FILENAME", F.col("_metadata.file_path"))
          .withColumn("_FILE_ROW_NUMBER", F.row_number().over(per_file))
          .withColumn("_LOAD_TS", F.current_timestamp().cast("timestamp_ntz"))
    )


def load_csv(session, tbl: str, locations: list) -> None:
    """Read every city's CSV and write one Bronze table.

    unionByName(allowMissingColumns=True) replaces Snowflake's
    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE: columns align by header name and a city
    missing a column gets NULL rather than failing the load. Column names are
    lower-cased first so the match is genuinely case-insensitive, as Snowflake's was.
    """
    frames = []
    for loc in locations:
        df = read_csv_city(session, loc)
        frames.append(df.toDF(*[c.lower() for c in df.columns]))

    combined = frames[0]
    for f in frames[1:]:
        combined = combined.unionByName(f, allowMissingColumns=True)

    (combined.write
             .mode("overwrite")               # CREATE OR REPLACE TABLE
             .option("overwriteSchema", "true")
             .saveAsTable(tbl))


# ------------------------------------------------------------
# GeoJSON path: one VARIANT column (the whole FeatureCollection)
# plus audit columns. Flattening happens in SILVER.
#
# Snowflake used STRIP_OUTER_ARRAY = FALSE so the FeatureCollection landed as ONE
# VARIANT row. Spark's JSON reader would instead explode the object into columns,
# so the file is read as whole text and parsed with parse_json() — which returns a
# native VARIANT (confirmed available in Session 2). That preserves the one-row,
# one-VARIANT shape Silver expects.
# ------------------------------------------------------------
def load_geojson(session, tbl: str, locations: list) -> None:
    frames = []
    for loc in locations:
        df = (session.read
                     .option("wholetext", "true")     # whole file = one row
                     .text(loc)
                     .select(
                         F.parse_json(F.col("value")).alias("raw"),
                         F.col("_metadata.file_path").alias("_filename"),
                         F.current_timestamp().cast("timestamp_ntz").alias("_load_ts"),
                     ))
        frames.append(df)

    combined = frames[0]
    for f in frames[1:]:
        combined = combined.unionByName(f)

    (combined.write
             .mode("overwrite")
             .option("overwriteSchema", "true")
             .saveAsTable(tbl))


def report_and_audit(session, tbl: str, table_short: str) -> None:
    """Print the per-file outcome and persist it to BRONZE.LOAD_AUDIT.

    Snowflake read this from the COPY result (one row per file). Databricks
    COPY INTO returns one row per STATEMENT, so instead the outcome is derived by
    grouping the written table by _FILENAME — which restores true PER-FILE
    granularity, matching the Snowflake audit rather than degrading it.

    ERRORS_SEEN counts rows where _RESCUED is non-null: input Spark could not parse
    into the expected shape. That is the direct analogue of Snowflake's
    ON_ERROR = CONTINUE skip counter, except the data is kept rather than dropped.
    """
    has_rescued = "_rescued" in [c.lower() for c in session.table(tbl).columns]
    rescued_expr = "SUM(CASE WHEN _RESCUED IS NOT NULL THEN 1 ELSE 0 END)" if has_rescued else "0"

    rows = session.sql(f"""
        SELECT _FILENAME                AS file_name,
               COUNT(*)                 AS rows_loaded,
               {rescued_expr}           AS errors_seen
        FROM {tbl}
        GROUP BY _FILENAME
        ORDER BY _FILENAME
    """).collect()

    for r in rows:
        fname = str(r["file_name"]).rsplit("/", 1)[-1]
        errors = r["errors_seen"] or 0
        flag = f"   WARNING: {errors} row(s) rescued" if errors else ""
        print(f"   {fname}: {r['rows_loaded']:,} rows loaded{flag}")

        session.sql(
            f"""
            INSERT INTO {table('LOAD_AUDIT')}
                (TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED,
                 ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE)
            VALUES (:tbl, :fname, :status, :parsed, :loaded, :errors, NULL, NULL)
            """,
            args={
                "tbl": table_short,
                "fname": str(r["file_name"]),
                "status": "PARTIALLY_LOADED" if errors else "LOADED",
                "parsed": r["rows_loaded"],
                "loaded": r["rows_loaded"],
                "errors": errors,
            },
        )


def verify(session, tbl: str, table_short: str) -> None:
    """Print the final total row count for the table."""
    n = session.sql(f"SELECT COUNT(*) FROM {tbl}").collect()[0][0]
    print(f"   {table_short}: total {n:,} rows")


# ------------------------------------------------------------
# Orchestration: loop datasets x cities.
# ------------------------------------------------------------
def run(session, datasets=DATASETS, cities=CITIES) -> None:
    use_schema(session, SCHEMA)

    # Resolve the latest snapshot folder once per city (logged for traceability).
    snapshots = {c: latest_snapshot(session, c) for c in cities}
    for c, snap in snapshots.items():
        print(f"[snapshot] {c}: loading from {snap}")

    for ds in datasets:
        name, fmt, file, ddir = ds["name"], ds["format"], ds["file"], ds["dir"]
        tbl = table(name, SCHEMA)
        locations = [file_path(c, snapshots[c], ddir, file) for c in cities]
        print(f"[{name}] loading {len(cities)} city/cities from '{ddir}/{file}' ({fmt})")

        if fmt == "csv":
            load_csv(session, tbl, locations)
        elif fmt == "geojson":
            load_geojson(session, tbl, locations)
        else:
            raise ValueError(f"Unknown format '{fmt}' for dataset '{name}'")

        report_and_audit(session, tbl, name)
        verify(session, tbl, name)

    print("Bronze ingestion complete.")


if __name__ == "__main__":
    session = get_session()
    run(session)
