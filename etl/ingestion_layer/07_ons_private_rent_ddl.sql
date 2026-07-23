-- ONS Price Index of Private Rents (PIPR) — Bronze DDL (external stage + xlsx parse proc).
-- Co-authored with CoCo
-- ============================================================
-- ONS PRIVATE RENT (PIPR)  —  DDL (structural, run ONCE).
-- ------------------------------------------------------------
-- Creates the reusable objects the load step (08) depends on:
--   1) an external S3 stage with a directory table (reuses AIRBNB_S3_INT), and
--   2) a Python stored proc that parses the RAW .xlsx with openpyxl.
--
-- SOURCE / DESIGN (Path B — parse in Snowflake):
--   A monthly Lambda (ons_pipr) downloads the ONS workbook UNCHANGED and lands
--   the raw spreadsheet at:
--     .../raw/ons/private-rents/pipruk_<YYYYMMDD>.xlsx
--   Snowflake parses it here — no CSV conversion in the Lambda, so the Lambda
--   needs no third-party packages. Because ONS workbooks carry multi-row titles
--   and merged headers, Bronze stays FAITHFUL: every non-empty row is landed as
--   an ARRAY of TEXT cells + lineage. Typing/reshaping happens later in SILVER.
--
--   xlsx is not COPY-loadable, so this source uses a Python proc instead of the
--   COPY pattern used by Land Registry / Airbnb. openpyxl ships in Snowflake's
--   Anaconda channel — no packaging.
--
--   IAM NOTE: reuses the existing snowflake-airbnb-s3-read role via AIRBNB_S3_INT.
--   No new integration or trust handshake — its read policy already covers raw/*
--   (s3:GetObject on arn:aws:s3:::<bucket>/raw/*, s3:ListBucket on the bucket with
--   prefix raw/*), which includes this raw/ons/private-rents/ prefix.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. External stage (reuses AIRBNB_S3_INT) pointing at the ONS prefix.
--    DIRECTORY = (ENABLE = TRUE) so the proc can list files and pick the newest.
--    CREATE OR ALTER so re-running this file is safe.
---------------------------------------------
CREATE OR ALTER STAGE BRONZE.ONS_PRIVATE_RENT_STAGE
    STORAGE_INTEGRATION = AIRBNB_S3_INT
    URL = 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/ons/private-rents/'
    DIRECTORY = (ENABLE = TRUE)
    COMMENT = 'External S3 landing zone for raw ONS PIPR .xlsx workbooks';

-- Verify Snowflake can see the file (uncomment to run interactively):
--   ALTER STAGE BRONZE.ONS_PRIVATE_RENT_STAGE REFRESH;
--   SELECT * FROM DIRECTORY(@BRONZE.ONS_PRIVATE_RENT_STAGE);

---------------------------------------------
-- 2. Parse proc: read the NEWEST .xlsx from the stage with openpyxl and append
--    faithful rows into BRONZE.RAW_ONS_PRIVATE_RENT, skipping the leading
--    title rows. Also writes one BRONZE.LOAD_AUDIT row (a Python load has no
--    COPY_HISTORY).
--      SHEET_NAME : workbook tab to read (matched case-insensitively / trimmed);
--                   NULL -> auto-pick first non-Contents/Notes sheet.
--      SKIP_ROWS  : number of leading rows to drop (ONS puts 2 title rows above
--                   the header). _FILE_ROW_NUMBER keeps the ORIGINAL sheet row
--                   number, so the header row stays identifiable downstream.
--    The target table is (re)created in 08_ons_private_rent_load.sql before CALL.
---------------------------------------------
CREATE OR REPLACE PROCEDURE BRONZE.LOAD_ONS_PRIVATE_RENT(SHEET_NAME STRING, SKIP_ROWS NUMBER)
    RETURNS STRING
    LANGUAGE PYTHON
    RUNTIME_VERSION = '3.11'
    PACKAGES = ('snowflake-snowpark-python', 'openpyxl')
    HANDLER = 'main'
AS
$$
import os
from openpyxl import load_workbook
from snowflake.snowpark.types import (
    StructType, StructField, StringType, ArrayType, LongType,
)

STAGE = "AIRBNB_INVESTMENT_DB.BRONZE.ONS_PRIVATE_RENT_STAGE"
TABLE = "AIRBNB_INVESTMENT_DB.BRONZE.RAW_ONS_PRIVATE_RENT"
SKIP = {"contents", "notes", "cover", "metadata"}


def _pick_sheet(wb, requested):
    if requested:
        want = requested.strip().lower()
        for name in wb.sheetnames:
            if name.strip().lower() == want:   # tolerant match (case / trailing spaces)
                return wb[name]
        raise ValueError(f"Sheet '{requested}' not found. Tabs: {wb.sheetnames}")
    for name in wb.sheetnames:
        if name.strip().lower() not in SKIP:
            return wb[name]
    return wb[wb.sheetnames[0]]


def _audit(session, file_name, parsed, loaded, status, err=None):
    session.sql(
        "INSERT INTO AIRBNB_INVESTMENT_DB.BRONZE.LOAD_AUDIT "
        "(TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED, ERRORS_SEEN, "
        " FIRST_ERROR, FIRST_ERROR_LINE) "
        "SELECT 'RAW_ONS_PRIVATE_RENT', ?, ?, ?, ?, ?, ?, NULL",
        params=[file_name, status, parsed, loaded, 0 if err is None else 1, err],
    ).collect()


def main(session, sheet_name, skip_rows):
    skip_rows = int(skip_rows or 0)

    # refresh the directory table, then take the newest .xlsx
    session.sql(f"ALTER STAGE {STAGE} REFRESH").collect()
    rows = session.sql(
        f"SELECT RELATIVE_PATH FROM DIRECTORY(@{STAGE}) "
        "WHERE RELATIVE_PATH ILIKE '%.xlsx' "
        "ORDER BY LAST_MODIFIED DESC LIMIT 1"
    ).collect()
    if not rows:
        return "No .xlsx files found in stage."
    rel_path = rows[0]["RELATIVE_PATH"]

    local_dir = "/tmp/ons_dl"
    os.makedirs(local_dir, exist_ok=True)
    session.file.get(f"@{STAGE}/{rel_path}", local_dir)
    local_file = os.path.join(local_dir, os.path.basename(rel_path))

    wb = load_workbook(local_file, read_only=True, data_only=True)
    ws = _pick_sheet(wb, sheet_name)

    records = []
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i <= skip_rows:                     # drop leading title rows
            continue
        if all(c is None for c in row):
            continue
        cells = [None if c is None else str(c) for c in row]
        records.append([ws.title, cells, rel_path, i])   # keep ORIGINAL row number

    if not records:
        _audit(session, rel_path, 0, 0, "LOADED")
        return f"File {rel_path}: no data rows after skipping {skip_rows}."

    schema = StructType([
        StructField("SHEET", StringType()),
        StructField("CELLS", ArrayType(StringType())),
        StructField("_FILENAME", StringType()),
        StructField("_FILE_ROW_NUMBER", LongType()),
    ])
    df = session.create_dataframe(records, schema)
    df.write.mode("append").save_as_table(TABLE, column_order="name")

    _audit(session, rel_path, len(records), len(records), "LOADED")
    return (
        f"Loaded {len(records)} rows from {rel_path} "
        f"(sheet {ws.title}, skipped first {skip_rows} rows)."
    )
$$;
