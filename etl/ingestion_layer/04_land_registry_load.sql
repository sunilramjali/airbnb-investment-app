-- Land Registry Price Paid — Bronze load (table rebuild + COPY + audit).
-- Co-authored with CoCo
-- ============================================================
-- LAND REGISTRY PRICE PAID  —  LOAD (run EVERY load).
-- ------------------------------------------------------------
-- Depends on 03_land_registry_ddl.sql (CSV_NOHDR_FF + LAND_REGISTRY_STAGE).
-- Rebuilds RAW_PRICE_PAID and COPYs all year files, so re-running (e.g. after
-- the monthly current-year refresh) is idempotent — no duplicate rows. Bronze
-- stays faithful (all columns TEXT); typing happens in SILVER.
--
-- Run steps 2 + 3 together: the audit INSERT reads RESULT_SCAN(LAST_QUERY_ID())
-- and only works when it runs immediately after the COPY.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Bronze table: the 16 documented PPD columns as TEXT + lineage columns.
--    Column order matches the Land Registry file layout exactly (positional COPY).
--    Rebuilt each run (OR REPLACE) to keep the load idempotent.
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_PRICE_PAID (
    TRANSACTION_UID   STRING,   -- $1  transaction unique identifier (GUID)
    PRICE             STRING,   -- $2  sale price (GBP)
    DATE_OF_TRANSFER  STRING,   -- $3  date of transfer (YYYY-MM-DD HH:MM)
    POSTCODE          STRING,   -- $4
    PROPERTY_TYPE     STRING,   -- $5  D/S/T/F/O
    OLD_NEW           STRING,   -- $6  Y (new build) / N
    DURATION          STRING,   -- $7  F (freehold) / L (leasehold)
    PAON              STRING,   -- $8  primary addressable object name
    SAON              STRING,   -- $9  secondary addressable object name
    STREET            STRING,   -- $10
    LOCALITY          STRING,   -- $11
    TOWN_CITY         STRING,   -- $12
    DISTRICT          STRING,   -- $13
    COUNTY            STRING,   -- $14
    PPD_CATEGORY_TYPE STRING,   -- $15 A (standard) / B (additional)
    RECORD_STATUS     STRING,   -- $16 A / C / D (monthly file only)
    _FILENAME         STRING,           -- lineage: source file (encodes year=)
    _FILE_ROW_NUMBER  NUMBER,           -- lineage: row position within file
    _LOAD_TS          TIMESTAMP_NTZ     -- lineage: load timestamp
)
COMMENT = 'Bronze Land Registry Price Paid — all years, all-TEXT, rebuilt each run.';

---------------------------------------------
-- 2. Load ALL year files in one COPY (positional mapping + lineage metadata).
--    PATTERN restricts to pp-<YYYY>.csv so stray files are ignored.
--    ON_ERROR = CONTINUE mirrors the Airbnb Bronze loader; skipped rows are
--    recorded in LOAD_AUDIT below.
---------------------------------------------
COPY INTO BRONZE.RAW_PRICE_PAID
FROM (
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
           METADATA$FILENAME, METADATA$FILE_ROW_NUMBER, METADATA$START_SCAN_TIME
    FROM @BRONZE.LAND_REGISTRY_STAGE
)
PATTERN = '.*pp-[0-9]{4}\.csv'
FILE_FORMAT = (FORMAT_NAME = 'BRONZE.CSV_NOHDR_FF')
ON_ERROR = CONTINUE;

---------------------------------------------
-- 3. Audit the load into the shared BRONZE.LOAD_AUDIT (created by 01_bronze_ddl.sql)
--    so Land Registry loads appear in the same audit queries as Airbnb loads.
--    Sourced from INFORMATION_SCHEMA.COPY_HISTORY (stable schema) rather than
--    RESULT_SCAN of the COPY: COPY returns a STATUS-only result with no FILE
--    column when 0 files are processed (e.g. a re-run where files are already
--    loaded), which breaks a RESULT_SCAN-based insert with "invalid identifier
--    'FILE'". COPY_HISTORY is also order-independent (no LAST_QUERY_ID dependency).
---------------------------------------------
INSERT INTO BRONZE.LOAD_AUDIT
    (TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED,
     ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE)
SELECT 'RAW_PRICE_PAID', FILE_NAME, STATUS, ROW_PARSED, ROW_COUNT,
       ERROR_COUNT, FIRST_ERROR_MESSAGE, FIRST_ERROR_LINE_NUMBER
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME => 'AIRBNB_INVESTMENT_DB.BRONZE.RAW_PRICE_PAID',
    START_TIME => DATEADD('hour', -1, CURRENT_TIMESTAMP())
));

---------------------------------------------
-- 4. Verify (uncomment to run interactively):
--   -- rows loaded per transfer year
--   SELECT YEAR(TRY_TO_DATE(LEFT(DATE_OF_TRANSFER, 10))) AS transfer_year,
--          COUNT(*) AS rows
--   FROM BRONZE.RAW_PRICE_PAID
--   GROUP BY 1 ORDER BY 1;
--
--   -- most recent Land Registry load outcome
--   SELECT * FROM BRONZE.LOAD_AUDIT
--   WHERE TABLE_NAME = 'RAW_PRICE_PAID' ORDER BY LOAD_TS DESC;
