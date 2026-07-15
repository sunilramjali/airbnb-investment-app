-- ONS Price Index of Private Rents (PIPR) — Bronze DDL (file format + external stage).
-- Co-authored with CoCo
-- ============================================================
-- ONS PRIVATE RENT (PIPR)  —  DDL (structural, run ONCE).
-- ------------------------------------------------------------
-- Creates the reusable objects the load step depends on:
--   1) a HEADERED CSV file format (SKIP_HEADER = 1),
--   2) an external S3 stage (reuses the existing AIRBNB_S3_INT integration).
-- The RAW_ONS_PRIVATE_RENT table + COPY live in 08_ons_private_rent_load.sql
-- (run each load), mirroring the Land Registry split (03 = structural, 04 = per-run).
--
-- SOURCE: ONS Price Index of Private Rents (PIPR) "average rent values".
--   A monthly Lambda (ons_pipr) downloads the ONS spreadsheet, reshapes it to a
--   tidy long CSV, and lands ONE cumulative file at:
--     .../raw/ons/private_rent/pipr_average_rents.csv
--   Header (produced by the Lambda, stable):
--     period, geography_code, geography_name, bedroom_category, average_rent
-- Unlike the headerless Land Registry files, this file HAS a header row, so it
-- uses its own file format (SKIP_HEADER = 1) rather than BRONZE.CSV_NOHDR_FF.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Headered CSV file format
--    The Lambda emits a clean, quoted, header-first CSV; skip the header row and
--    let positional COPY map the 5 columns. Kept separate from CSV_NOHDR_FF
--    (Land Registry, no header) and CSV_HDR_FF (Airbnb, PARSE_HEADER/INFER_SCHEMA).
---------------------------------------------
CREATE FILE FORMAT IF NOT EXISTS BRONZE.CSV_HDR_SKIP1_FF
    TYPE = CSV
    SKIP_HEADER = 1                          -- Lambda writes a single header row
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'       -- pandas quotes fields containing commas
    NULL_IF = ('', 'NULL', 'null', 'N/A', 'NaN')  -- normalise common null markers
    EMPTY_FIELD_AS_NULL = TRUE
    TRIM_SPACE = TRUE
    ENCODING = 'UTF8'
    COMMENT = 'Headered CSV parse (skip 1 row) for ONS PIPR tidy long file';

---------------------------------------------
-- 2. External stage (reuses AIRBNB_S3_INT) pointing at the ONS prefix.
--    CREATE OR ALTER so re-running this file is safe.
--
--    IAM NOTE: reuses the existing snowflake-airbnb-s3-read role. No new
--    integration or trust handshake — the role's read policy already covers
--    raw/* (s3:GetObject on arn:aws:s3:::<bucket>/raw/*, s3:ListBucket on the
--    bucket with prefix raw/*), which includes this new raw/ons/... prefix.
---------------------------------------------
CREATE OR ALTER STAGE BRONZE.ONS_PRIVATE_RENT_STAGE
    STORAGE_INTEGRATION = AIRBNB_S3_INT
    URL = 's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/ons/private_rent/'
    COMMENT = 'External S3 landing zone for ONS PIPR average private rent CSV';

-- Verify Snowflake can see the file (uncomment to run interactively):
--   LIST @BRONZE.ONS_PRIVATE_RENT_STAGE;
