-- Land Registry Price Paid — Bronze DDL (file format + external stage).
-- Co-authored with CoCo
-- ============================================================
-- LAND REGISTRY PRICE PAID  —  DDL (structural, run ONCE).
-- ------------------------------------------------------------
-- Creates the reusable objects the load step depends on:
--   1) a headerless CSV file format,
--   2) an external S3 stage (reuses the existing AIRBNB_S3_INT integration).
-- The RAW_PRICE_PAID table + COPY live in 04_land_registry_load.sql (run each load),
-- mirroring the Airbnb split (01_bronze_ddl.sql = structural, loader = per-run).
--
-- SOURCE: HM Land Registry Price Paid Data, one CSV per year (no header row),
--   landed in S3 at .../raw/hm_land_registry/price_paid/year=<YYYY>/pp-<YYYY>.csv.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Headerless CSV file format
--    Land Registry yearly files have NO header row and quote every field.
--    (The Airbnb CSV_HDR_FF uses PARSE_HEADER=TRUE and cannot be reused here.)
---------------------------------------------
CREATE FILE FORMAT IF NOT EXISTS BRONZE.CSV_NOHDR_FF
    TYPE = CSV
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'      -- LR quotes all fields; handles commas inside text
    NULL_IF = ('', 'NULL', 'null', 'N/A')   -- normalise common null markers
    EMPTY_FIELD_AS_NULL = TRUE
    TRIM_SPACE = TRUE
    ENCODING = 'UTF8'
    COMMENT = 'Headerless CSV parse for Land Registry Price Paid yearly files';

---------------------------------------------
-- 2. External stage (reuses AIRBNB_S3_INT) pointing at the Land Registry prefix.
--    CREATE OR ALTER so re-running this file is safe.
--
--    IAM NOTE: the AWS role snowflake-airbnb-s3-read must allow, in its
--    *permission* policy (not the trust policy):
--      s3:GetObject, s3:GetObjectVersion  on  arn:aws:s3:::<bucket>/raw/*
--      s3:ListBucket                       on  arn:aws:s3:::<bucket>   (Condition s3:prefix = raw/*)
--    A missing/narrow ListBucket grant surfaces as a 403 AccessDenied on LIST/COPY.
---------------------------------------------
CREATE OR ALTER STAGE BRONZE.LAND_REGISTRY_STAGE
    STORAGE_INTEGRATION = AIRBNB_S3_INT
    URL = 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry/price_paid/'
    COMMENT = 'External S3 landing zone for Land Registry Price Paid yearly CSVs';

-- Verify Snowflake can see the files (uncomment to run interactively):
--   LIST @BRONZE.LAND_REGISTRY_STAGE;
