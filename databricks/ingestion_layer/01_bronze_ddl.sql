-- Bronze ingestion DDL: load audit table. Databricks port of etl/ingestion_layer/01_bronze_ddl.sql.
-- ============================================================
-- BRONZE INGESTION — DDL (load audit only)
-- ------------------------------------------------------------
-- Run this ONCE. The actual per-file / per-city loading lives in
-- databricks/ingestion_layer/02_bronze_load.py (driven by config/ingestion_manifest.py).
--
-- FLOW:
--   1) Run this file              -> LOAD_AUDIT.
--   2) A Lambda uploads files to  -> s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/<city>/snapshot_date=<YYYY-MM-DD>/.
--   3) Run databricks/ingestion_layer/02_bronze_load.py  -> creates + loads every Bronze table.
--
-- ============================================================
-- WHAT THE SNOWFLAKE ORIGINAL HAD THAT THIS FILE DOES NOT
-- ------------------------------------------------------------
-- Sections 1 and 2 of etl/ingestion_layer/01_bronze_ddl.sql are OBSOLETE here.
-- They are not missing — they have no Databricks counterpart to write:
--
--   CREATE FILE FORMAT CSV_HDR_FF / GEOJSON_FF
--       Databricks has no named, reusable file-format object. The equivalent parse
--       options are passed inline to read_files() at each call site in
--       02_bronze_load.py, which keeps them next to the read they configure.
--
--   CREATE STORAGE INTEGRATION AIRBNB_S3_INT
--       -> Unity Catalog STORAGE CREDENTIAL `airbnb_s3_cred`
--          (arn:aws:iam::988261629236:role/databricks-airbnb-s3-read)
--
--   CREATE STAGE BRONZE.RAW_STAGE
--       -> Unity Catalog EXTERNAL LOCATION `airbnb_raw`
--          (s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb)
--
-- Both UC objects already exist — created in Session 2, see setup/databricks/README.md
-- for the IAM handshake runbook. Loader paths are plain s3:// URLs, so there is no
-- @STAGE indirection to recreate.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA BRONZE;

--------------------------------------------------------
-- LOAD AUDIT  —  durable record of every load.
--     One row per COPY INTO statement: rows parsed/loaded and (critically)
--     ERRORS_SEEN, so rows silently skipped by a permissive read leave a
--     queryable trace instead of vanishing with the notebook.
--     IF NOT EXISTS (not OR REPLACE) so audit HISTORY accumulates across
--     runs — unlike the RAW_* tables, which are rebuilt each load.
--
--     Inspect after a run:
--       SELECT * FROM BRONZE.LOAD_AUDIT WHERE ERRORS_SEEN > 0 ORDER BY LOAD_TS DESC;
--
--     ⚠️ GRANULARITY DIFFERS FROM SNOWFLAKE. Snowflake's COPY INTO returned one
--     result row PER FILE, so LOAD_AUDIT held per-file outcomes. Databricks
--     COPY INTO returns one summary row PER STATEMENT. Where the loader already
--     iterates file-by-file (02_bronze_load.py loops city x dataset) the two are
--     equivalent. Where a single statement ingests many files (04_land_registry_load,
--     which reads every year= partition at once) one audit row covers them all and
--     FILE_NAME records the glob, not an individual file. Do not read this table
--     expecting per-file rows in every case.
--------------------------------------------------------
CREATE TABLE IF NOT EXISTS BRONZE.LOAD_AUDIT (
    AUDIT_ID         BIGINT GENERATED ALWAYS AS IDENTITY,  -- was NUMBER AUTOINCREMENT
    TABLE_NAME       STRING,          -- target RAW_* table
    FILE_NAME        STRING,          -- source file, or the glob when a statement spans many
    STATUS           STRING,          -- load status (e.g. LOADED / PARTIALLY_LOADED)
    ROWS_PARSED      BIGINT,          -- rows the parser saw
    ROWS_LOADED      BIGINT,          -- rows that actually landed
    ERRORS_SEEN      BIGINT,          -- rows skipped or rescued (the silent-loss counter)
    FIRST_ERROR      STRING,          -- first failure message, if any
    FIRST_ERROR_LINE BIGINT,          -- file line of the first failure
    LOAD_TS          TIMESTAMP_NTZ DEFAULT current_timestamp()
)
COMMENT 'Per-statement load outcome for every Bronze load; history accumulates.'
-- Delta refuses a column DEFAULT unless this table feature is enabled first
-- (WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED). Snowflake needed no
-- equivalent opt-in for the DEFAULT CURRENT_TIMESTAMP() on this column.
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');
