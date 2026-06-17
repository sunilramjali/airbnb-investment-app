-- ============================================================
-- BRONZE INGESTION — DDL (file formats + stage)
-- ------------------------------------------------------------
-- Run this ONCE to create the reusable file formats and the
-- internal landing stage. The actual per-file / per-city loading
-- lives in etl/02_bronze_load.py (driven by config/ingestion_manifest.py).
--
-- FLOW:
--   1) Run this file              -> file formats + RAW_STAGE.
--   2) Upload files to            -> @BRONZE.RAW_STAGE/<city>/.
--   3) Run etl/02_bronze_load.py     -> creates + loads every Bronze table.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Create file formats
---------------------------------------------

-- 1a. CSV files (single header-aware CSV format used by ALL csv loads)
CREATE FILE FORMAT IF NOT EXISTS BRONZE.CSV_HDR_FF
    TYPE = CSV
    PARSE_HEADER = TRUE                     -- column names come from row 1 (do NOT use SKIP_HEADER)
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'      -- handles commas/newlines inside quoted text fields
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE  -- tolerate ragged rows (ignored when MATCH_BY_COLUMN_NAME is set)
    NULL_IF = ('', 'NULL', 'null', 'N/A')   -- normalise common null markers
    EMPTY_FIELD_AS_NULL = TRUE
    TRIM_SPACE = TRUE
    ENCODING = 'UTF8'
    COMMENT = 'Header-name CSV parse for all Airbnb CSV files';

-- 1b. GeoJSON files (one FeatureCollection object = one VARIANT row; flattened in SILVER)
CREATE FILE FORMAT IF NOT EXISTS BRONZE.GEOJSON_FF
    TYPE = JSON
    STRIP_OUTER_ARRAY = FALSE               -- FeatureCollection loads as one VARIANT row
    COMMENT = 'JSON parse rules for GeoJSON FeatureCollection files';

--------------------------------------------------------
-- 2. Create stage for raw files (format-neutral stage)
--------------------------------------------------------
CREATE STAGE IF NOT EXISTS BRONZE.RAW_STAGE
    COMMENT = 'Landing zone for raw Airbnb CSV files and GeoJSON files';

--------------------------------------------------------
-- 2b. EXTERNAL STAGE (AWS S3)  —  Step 2.
--     STORAGE INTEGRATION + external stage go here later.
--     02_bronze_load.py points at @BRONZE.RAW_STAGE today; swapping to
--     an S3 external stage is a one-line change there.
--------------------------------------------------------

--------------------------------------------------------
-- 3. LOAD AUDIT  —  durable record of every COPY.
--     One row per file per load: rows parsed/loaded and (critically)
--     ERRORS_SEEN, so rows silently skipped by ON_ERROR = CONTINUE
--     leave a queryable trace instead of vanishing with the notebook.
--     IF NOT EXISTS (not OR REPLACE) so audit HISTORY accumulates across
--     runs — unlike the RAW_* tables, which are rebuilt each load.
--
--     Inspect after a run:
--       SELECT * FROM BRONZE.LOAD_AUDIT WHERE ERRORS_SEEN > 0 ORDER BY LOAD_TS DESC;
--------------------------------------------------------
CREATE TABLE IF NOT EXISTS BRONZE.LOAD_AUDIT (
    AUDIT_ID         NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    TABLE_NAME       STRING,          -- target RAW_* table
    FILE_NAME        STRING,          -- source file on the stage
    STATUS           STRING,          -- COPY status (e.g. LOADED / PARTIALLY_LOADED)
    ROWS_PARSED      NUMBER,          -- rows the parser saw
    ROWS_LOADED      NUMBER,          -- rows that actually landed
    ERRORS_SEEN      NUMBER,          -- rows skipped (the silent-loss counter)
    FIRST_ERROR      STRING,          -- first failure message, if any
    FIRST_ERROR_LINE NUMBER,          -- file line of the first failure
    LOAD_TS          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Per-file COPY outcome for every Bronze load; history accumulates.';
