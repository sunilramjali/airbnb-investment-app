# ONS Postcode Directory (ONSPD) — Bronze load.
# Replaces etl/ingestion_layer/06_code_point_load.sql (Ordnance Survey Code-Point Open).
# ============================================================
# ONSPD  —  LOAD (run each refresh).
# ------------------------------------------------------------
# ⚠️ THIS IS A SOURCE CHANGE, NOT A PORT.
#
# The Snowflake original read the Ordnance Survey "Code-Point Open" Marketplace
# share (POSTCODE_UNITS__GREAT_BRITAIN_CODEPOINT_OPEN). No equivalent live share is
# attached to this Databricks workspace, and the two listings that ARE attached —
# CARTO_OVERTURE_MAPS_PLACES and FOURSQUARE_OS_PLACES — are both POI datasets.
# Foursquare "OS" is *Open Source*, NOT *Ordnance Survey*: it carries no GB postcode
# units and cannot substitute.
#
# The replacement source is the ONS Postcode Directory (ONSPD): open, no account
# required, and it carries postcode + lat/long + admin codes, which covers what
# etl/cleaning_layer/09_silver_code_point.sql:50 actually consumes.
#
# Ingested like the other file-based sources (03/04): read from S3, all-TEXT,
# lineage columns, LOAD_AUDIT row. CREATE OR REPLACE keeps it idempotent.
#
# ============================================================
# WHY THIS FILE IS .py AND DERIVES ITS COLUMNS AT RUNTIME
# ------------------------------------------------------------
# ONSPD ships ~50 columns and ONS adds/renames them between quarterly editions.
# Hard-coding a column list would either be a guess (wrong) or need editing every
# release. Instead the header row IS the schema: every column is read as STRING and
# carried through under its real ONSPD name.
#
# Bronze stays faithful to the source it actually has. The columns are deliberately
# NOT renamed to Code-Point Open's names — that would be a derivation, and it would
# hide the source change from anyone reading the table.
#
# ⚠️ SILVER MUST CHANGE. etl/cleaning_layer/09_silver_code_point.sql reads
# Code-Point column names that do not exist in ONSPD.
#
# ✅ ALL MAPPINGS CONFIRMED 2026-07-28 against the real 53-column header of
#    ONSPD_FEB_2024_UK.csv. Nothing below is a guess any more.
#
#     Code-Point Open (old)   ->  ONSPD (new)   evidence (row 1: AB1 0AA)
#     POSTCODE                ->  pcds          'AB1 0AA' (variable-width, single-space)
#     ADMIN_DISTRICT_CODE     ->  oslaua        'S12000033'
#     ADMIN_WARD_CODE         ->  osward        'S13002843'
#     COUNTRY_CODE            ->  ctry          'S92000003' = Scotland — correct for AB
#     ADMIN_COUNTY_CODE       ->  oscty         'S99999999' = the "not applicable"
#                                               pseudo-code (Scotland has no county)
#     POSITIONAL_QUALITY_IND. ->  osgrdind      '1' (grid-reference positional quality)
#     NHS_HA_CODE             ->  oshlthau      'S08000020' (former health authority)
#     NHS_REGIONAL_HA_CODE    ->  nhser         'S99999999' (NHS England Region;
#                                               pseudo-coded outside England)
#     GEOMETRY / GEOGRAPHY    ->  NO EQUIVALENT. ONSPD gives lat/long as plain
#                                 numbers ('57.101474', '-2.242851'), kept as TEXT
#                                 here per the all-TEXT rule. The point must be
#                                 CONSTRUCTED in Silver:
#                                   st_setsrid(st_point(try_cast(long AS DOUBLE),
#                                                       try_cast(lat  AS DOUBLE)), 4326)
#
# ⚠️ ONSPD carries TERMINATED postcodes (`doterm` set) — 901,381 of 2,700,777 in the
#    Feb 2024 edition. Code-Point Open carried live postcodes only. Silver must decide
#    explicitly whether to keep them: KEEPING them raises Price-Paid postcode coverage
#    (historic sales on since-retired postcodes now resolve), which is desirable here,
#    but it is a behaviour change from Snowflake and must not happen by accident.
#
# ============================================================
# PREREQUISITE — ✅ SATISFIED 2026-07-28
#   ONSPD_FEB_2024_UK.csv (1.45 GB, 2,700,777 rows) landed by Sunil under
#     s3://.../raw/ons/postcode_directory/
#   Covered by the existing external location `airbnb_raw_ons` (scoped to raw/ons)
#   — no new UC object and no IAM change was needed.
#
# ⚠️ EDITION IS STALE. ONSPD ships quarterly (Feb/May/Aug/Nov); the current release
#   as of 2026-07-28 is MAY 2026, so this file is ~9 releases behind. Postcodes
#   created after Feb 2024 are absent, which suppresses Price-Paid coverage for
#   2024-26 new-build sales. That pushes the documented 99.95% coverage invariant
#   DOWN while the terminated postcodes push it UP — two opposing effects that make
#   the resulting number unattributable. Land the current edition before judging
#   the Silver coverage gate (see databricks/verification_invariants.md).
#
#   Upgrading is a pure file drop: newest_csv() below selects by modification_time,
#   and the write is CREATE OR REPLACE. No code change is needed for a new edition.
# ============================================================

import importlib
import sys
from pathlib import Path

from pyspark.sql import Window
from pyspark.sql import functions as F


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
from config.databricks_context import get_session, table, RAW_PATHS

SCHEMA = "bronze"
PREFIX = f"{RAW_PATHS['ons']}/postcode_directory/"

# ONSPD is a plain headered CSV. Same reader settings as the Airbnb CSV path, so the
# all-TEXT discipline and NULL handling stay consistent across Bronze — with ONE
# deliberate difference, see multiLine below.
CSV_OPTIONS = {
    "header": "true",
    "inferSchema": "false",      # every column lands as STRING
    "quote": '"',
    "escape": '"',
    # ⚠️ multiLine is FALSE here, unlike the Airbnb loader where it is load-bearing.
    # Airbnb descriptions contain newlines inside quoted fields; ONSPD is machine-
    # generated admin codes with none. Setting it true would make this 1.45 GB file
    # NON-SPLITTABLE and force single-threaded parsing of the whole thing for no
    # benefit. Verified 2026-07-28: reads correctly at multiLine=false, and
    # count(*) == count(distinct pcds) == 2,700,777 confirms no rows were split.
    "multiLine": "false",
    "mode": "PERMISSIVE",
    "ignoreLeadingWhiteSpace": "true",
    "ignoreTrailingWhiteSpace": "true",
    "encoding": "UTF-8",
    "rescuedDataColumn": "_RESCUED",
}

NULL_MARKERS = ["", "NULL", "null", "N/A"]


def newest_csv(session, prefix: str) -> str:
    """Full S3 path of the most recently modified .csv under `prefix`.

    ONS republishes ONSPD quarterly; taking the newest file mirrors how the Airbnb
    loader resolves the latest snapshot_date= folder rather than hardcoding an edition.
    """
    rows = session.sql(f"LIST '{prefix}'").collect()
    csvs = [r for r in rows if str(r["path"]).lower().endswith(".csv")]
    if not csvs:
        raise FileNotFoundError(
            f"No .csv found under {prefix}. The ONSPD release has not been landed yet "
            f"— see the PREREQUISITE note at the top of this file."
        )
    return str(max(csvs, key=lambda r: r["modification_time"])["path"])


def load(session, path: str, target: str):
    df = session.read.options(**CSV_OPTIONS).csv(path)

    source_cols = [c for c in df.columns if c != "_RESCUED"]
    df = df.select(*[
        F.when(F.col(f"`{c}`").isin(NULL_MARKERS), None).otherwise(F.col(f"`{c}`")).alias(c)
        if c in source_cols else F.col(f"`{c}`")
        for c in df.columns
    ])

    # Synthetic row id — same convention and same caveat as the rest of Bronze:
    # NOT a physical file line number, just a stable unique id per file.
    per_file = Window.partitionBy("_FILENAME").orderBy(F.monotonically_increasing_id())

    out = (df.withColumn("_FILENAME", F.col("_metadata.file_path"))
             .withColumn("_FILE_ROW_NUMBER", F.row_number().over(per_file))
             .withColumn("_LOAD_TS", F.current_timestamp().cast("timestamp_ntz")))
    out = out.toDF(*[c.lower() for c in out.columns])

    (out.write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(target))
    return out


def audit_and_verify(session, target: str, audit: str) -> None:
    """Per-file audit derived by grouping the loaded table — same approach as
    02_bronze_load.py and 04_land_registry_load.sql (no COPY_HISTORY exists)."""
    session.sql(f"""
        INSERT INTO {audit}
            (TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED,
             ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE)
        SELECT 'RAW_ONSPD', _FILENAME, 'LOADED', COUNT(*), COUNT(*), 0, NULL, NULL
        FROM {target}
        GROUP BY _FILENAME
    """)
    # Verification is by INVARIANT, not by Snowflake parity — the Snowflake trial
    # expired 2026-07-28 and there is nothing left to compare against. See
    # databricks/verification_invariants.md.
    n, distinct_pcds, terminated = session.sql(f"""
        SELECT COUNT(*), COUNT(DISTINCT pcds), COUNT(doterm) FROM {target}
    """).collect()[0]
    print(f"   RAW_ONSPD: total {n:,} rows "
          f"({n - terminated:,} live, {terminated:,} terminated)")

    # 🔬 STRUCTURAL INVARIANT — one row per postcode. This is the real gate: it is
    # true by definition of the source and independent of edition or platform.
    # It is also what would catch a CSV mis-parse, which a row count alone cannot.
    if n != distinct_pcds:
        raise ValueError(
            f"GRAIN VIOLATION: {n:,} rows but {distinct_pcds:,} distinct pcds "
            f"({n - distinct_pcds:,} duplicates). ONSPD is one row per postcode — "
            f"a mismatch means the parse is wrong, not that the source is dirty."
        )
    print(f"   OK: count(*) == count(distinct pcds) == {n:,}")

    # Sanity band, NOT a gate. UK-wide ONSPD is ~2.7M rows (live + terminated);
    # ~1.8M is the LIVE subset only. Do not re-calibrate this to 1.7-1.8M — that was
    # the Code-Point Open (GB, live-only) figure and it would pass here for the
    # wrong reason.
    if not (2_000_000 <= n <= 3_500_000):
        print(f"   WARNING: {n:,} rows is outside the expected ~2.7M for UK ONSPD.")


def run(session) -> None:
    target = table("RAW_ONSPD", SCHEMA)
    audit = table("LOAD_AUDIT", SCHEMA)

    path = newest_csv(session, PREFIX)
    print(f"[RAW_ONSPD] loading {path}")
    out = load(session, path, target)
    print(f"   {len(out.columns)} columns (derived from the ONSPD header)")
    audit_and_verify(session, target, audit)


if __name__ == "__main__":
    run(get_session())
