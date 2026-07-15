-- ONS Price Index of Private Rents (PIPR) — Bronze load (table rebuild + COPY + audit).
-- Co-authored with CoCo
-- ============================================================
-- ONS PRIVATE RENT (PIPR)  —  LOAD (run EVERY load).
-- ------------------------------------------------------------
-- Depends on 07_ons_private_rent_ddl.sql (CSV_HDR_SKIP1_FF + ONS_PRIVATE_RENT_STAGE).
-- Rebuilds RAW_ONS_PRIVATE_RENT and COPYs the single cumulative file, so
-- re-running (e.g. after the monthly Lambda refresh) is idempotent — no
-- duplicate rows. Bronze stays faithful (all columns TEXT); typing happens
-- in SILVER (08_silver_ons_private_rent.sql).
--
-- Run steps 2 + 3 together: the audit INSERT reads COPY_HISTORY for this table.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Bronze table: the 5 tidy columns as TEXT + lineage columns.
--    Column order matches the Lambda's CSV header exactly (positional COPY):
--      period, geography_code, geography_name, bedroom_category, average_rent
--    Rebuilt each run (OR REPLACE) to keep the load idempotent.
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_ONS_PRIVATE_RENT (
    PERIOD            STRING,   -- $1  reporting month (ONS date, e.g. 'YYYY-MM' or 'Mon-YY')
    GEOGRAPHY_CODE    STRING,   -- $2  ONS geography code (e.g. E12000007, E11000001, E06000023)
    GEOGRAPHY_NAME    STRING,   -- $3  human-readable area name
    BEDROOM_CATEGORY  STRING,   -- $4  bedroom / property-type breakdown label
    AVERAGE_RENT      STRING,   -- $5  average monthly rent (GBP)
    _FILENAME         STRING,           -- lineage: source file
    _FILE_ROW_NUMBER  NUMBER,           -- lineage: row position within file
    _LOAD_TS          TIMESTAMP_NTZ     -- lineage: load timestamp
)
COMMENT = 'Bronze ONS PIPR average private rents — cumulative, all-TEXT, rebuilt each run.';

---------------------------------------------
-- 2. Load the cumulative file in one COPY (positional mapping + lineage metadata).
--    PATTERN restricts to the tidy CSV so stray/marker objects are ignored.
--    ON_ERROR = CONTINUE mirrors the other Bronze loaders; skipped rows are
--    recorded in LOAD_AUDIT below.
---------------------------------------------
COPY INTO BRONZE.RAW_ONS_PRIVATE_RENT
FROM (
    SELECT $1, $2, $3, $4, $5,
           METADATA$FILENAME, METADATA$FILE_ROW_NUMBER, METADATA$START_SCAN_TIME
    FROM @BRONZE.ONS_PRIVATE_RENT_STAGE
)
PATTERN = '.*pipr_average_rents\.csv'
FILE_FORMAT = (FORMAT_NAME = 'BRONZE.CSV_HDR_SKIP1_FF')
ON_ERROR = CONTINUE;

---------------------------------------------
-- 3. Audit the load into the shared BRONZE.LOAD_AUDIT (created by 01_bronze_ddl.sql)
--    so ONS loads appear in the same audit queries as the other sources.
--    Sourced from INFORMATION_SCHEMA.COPY_HISTORY (stable schema, order-independent,
--    robust to 0-file re-runs) rather than RESULT_SCAN of the COPY.
---------------------------------------------
INSERT INTO BRONZE.LOAD_AUDIT
    (TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED,
     ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE)
SELECT 'RAW_ONS_PRIVATE_RENT', FILE_NAME, STATUS, ROW_PARSED, ROW_COUNT,
       ERROR_COUNT, FIRST_ERROR_MESSAGE, FIRST_ERROR_LINE_NUMBER
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME => 'AIRBNB_INVESTMENT_DB.BRONZE.RAW_ONS_PRIVATE_RENT',
    START_TIME => DATEADD('hour', -1, CURRENT_TIMESTAMP())
));

---------------------------------------------
-- 4. Verify (uncomment to run interactively):
--   -- distinct geographies present (should include our 3 target codes)
--   SELECT DISTINCT GEOGRAPHY_CODE, GEOGRAPHY_NAME
--   FROM BRONZE.RAW_ONS_PRIVATE_RENT ORDER BY 1;
--
--   -- most recent ONS load outcome
--   SELECT * FROM BRONZE.LOAD_AUDIT
--   WHERE TABLE_NAME = 'RAW_ONS_PRIVATE_RENT' ORDER BY LOAD_TS DESC;
