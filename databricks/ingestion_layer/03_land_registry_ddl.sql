-- Land Registry Price Paid — Bronze DDL. Databricks port of etl/ingestion_layer/03_land_registry_ddl.sql.
-- ============================================================
-- LAND REGISTRY PRICE PAID  —  DDL (structural, run ONCE).
-- ------------------------------------------------------------
-- SOURCE: HM Land Registry Price Paid Data, one CSV per year (no header row),
--   landed in S3 at .../raw/hm_land_registry/price_paid/year=<YYYY>/pp-<YYYY>.csv.
--
-- ============================================================
-- THIS FILE CREATES NOTHING. Both objects the Snowflake original created have
-- no Databricks counterpart to write:
--
--   CREATE FILE FORMAT BRONZE.CSV_NOHDR_FF
--       Databricks has no named file-format object. The headerless parse options
--       are passed inline to read_files() in 04_land_registry_load.sql.
--
--   CREATE STAGE BRONZE.LAND_REGISTRY_STAGE
--       -> Unity Catalog EXTERNAL LOCATION `airbnb_raw_lr`
--          (s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry)
--
-- The file is kept rather than deleted so the Snowflake original has a 1:1
-- counterpart in the ported tree, and so the verification query below has a home.
--
-- ⚠️ WHY A SEPARATE EXTERNAL LOCATION, NOT ONE SHARED `raw/` LOCATION
-- Snowflake used ONE storage integration (STORAGE_ALLOWED_LOCATIONS = '.../raw/')
-- serving three stages. The obvious Databricks mirror — a single external location
-- at raw/ — DOES NOT WORK on this workspace. Creating it fails validation with:
--
--   AWS IAM role does not have READ permissions on url s3://<bucket>/raw
--
-- even though the attached IAM policy grants s3:GetObject on `raw/*` and
-- s3:ListBucket with condition s3:prefix IN ('raw/*','raw'). External locations at
-- the CHILD prefixes validate fine against the very same credential. So Unity
-- Catalog needs one external location per prefix:
--
--   airbnb_raw      -> raw/inside_airbnb     (Airbnb snapshots)
--   airbnb_raw_lr   -> raw/hm_land_registry  (this file)
--   airbnb_raw_ons  -> raw/ons               (private rents + ONSPD)
--
-- All three share the single storage credential `airbnb_s3_cred`, so this is a
-- Unity Catalog object-model difference, not an extra AWS grant.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA BRONZE;

-- Verify Databricks can see the files (the analogue of LIST @BRONZE.LAND_REGISTRY_STAGE).
-- Expect one year=<YYYY>/ folder per year, each holding a single pp-<YYYY>.csv.
LIST 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry/price_paid/';
