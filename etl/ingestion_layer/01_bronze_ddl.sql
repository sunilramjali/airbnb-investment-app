-- Bronze ingestion DDL: file formats, S3 storage integration + external stage, and load audit.
-- Co-authored with CoCo
-- ============================================================
-- BRONZE INGESTION — DDL (file formats + stage)
-- ------------------------------------------------------------
-- Run this ONCE to create the reusable file formats, the S3 storage
-- integration, and the external landing stage. The actual per-file /
-- per-city loading lives in etl/ingestion_layer/02_bronze_load.py (driven by
-- config/ingestion_manifest.py).
--
-- FLOW:
--   1) Run this file              -> file formats + S3 integration + RAW_STAGE.
--   2) A Lambda uploads files to  -> s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/<city>/snapshot_date=<YYYY-MM-DD>/.
--   3) Run etl/ingestion_layer/02_bronze_load.py  -> creates + loads every Bronze table.
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
-- 2. EXTERNAL STAGE (AWS S3)  —  raw files land here.
--     A Lambda (quarterly, via EventBridge) uploads each new Inside Airbnb
--     snapshot to:
--       s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/<city>/snapshot_date=<YYYY-MM-DD>/<dataset>/<file>
--     e.g. .../london/snapshot_date=2025-09-14/listings/listings.csv.gz
--     Snowflake reads it through a STORAGE INTEGRATION (no AWS keys stored).
--------------------------------------------------------

-- 2a. Storage integration: trust to assume the AWS read-only role.
--     Run once as ACCOUNTADMIN. The role itself stores no credentials in
--     Snowflake; access is brokered via STS using the role ARN below.
CREATE STORAGE INTEGRATION IF NOT EXISTS AIRBNB_S3_INT
    TYPE = EXTERNAL_STAGE
    STORAGE_PROVIDER = 'S3'
    ENABLED = TRUE
    STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::988261629236:role/snowflake-airbnb-s3-read'
    STORAGE_ALLOWED_LOCATIONS = ('s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/')
    COMMENT = 'Read-only access to the Airbnb raw S3 bucket';

-- 2b. External S3 stage. Named RAW_STAGE so 02_bronze_load.py keeps
--     referencing @BRONZE.RAW_STAGE unchanged. URL points at the
--     inside_airbnb/ prefix so loader paths begin at the city; the
--     per-file path (city/snapshot_date=.../dataset/file) is built there.
CREATE OR REPLACE STAGE BRONZE.RAW_STAGE
    STORAGE_INTEGRATION = AIRBNB_S3_INT
    URL = 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/'
    COMMENT = 'External S3 landing zone for raw Airbnb CSV + GeoJSON files';

-- 2c. ONE-TIME AWS HANDSHAKE (do this right after first creating 2a):
--       DESC INTEGRATION AIRBNB_S3_INT;
--     Copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID into the
--     TRUST POLICY of the IAM role snowflake-airbnb-s3-read, e.g.:
--       {
--         "Version": "2012-10-17",
--         "Statement": [{
--           "Effect": "Allow",
--           "Principal": { "AWS": "<STORAGE_AWS_IAM_USER_ARN>" },
--           "Action": "sts:AssumeRole",
--           "Condition": { "StringEquals": { "sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID>" } }
--         }]
--       }
--     The role's PERMISSION policy needs read-only S3 on the bucket:
--       s3:GetObject, s3:GetObjectVersion on  arn:aws:s3:::airbnb-investment-app-988261629236-eu-west-2-an/raw/*
--       s3:ListBucket                  on  arn:aws:s3:::airbnb-investment-app-988261629236-eu-west-2-an (prefix raw/*)
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
