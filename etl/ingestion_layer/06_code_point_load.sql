-- Code-Point Open (GB postcodes) — Bronze load (Marketplace share -> faithful Bronze snapshot).
-- Co-authored with CoCo
-- ============================================================
-- CODE-POINT OPEN  —  LOAD (run each refresh).
-- ------------------------------------------------------------
-- SOURCE: the Ordnance Survey "Code-Point Open" Marketplace share,
--   mounted as the shared database
--   POSTCODE_UNITS__GREAT_BRITAIN_CODEPOINT_OPEN. Its single view
--   PRS_CODE_POINT_OPEN_SCH.PRS_CODE_POINT_OPEN_VW holds ~1.7M GB
--   postcode units, each with a GEOGRAPHY point + admin area codes.
--
-- This Bronze step is a FAITHFUL FULL SNAPSHOT (no filtering): all
-- source columns are carried as-is. At ~1.7M rows the whole of GB is
-- cheap to hold, keeps Bronze true to the raw source, and future-proofs
-- adding cities. Any spatial scoping / postcode->neighbourhood
-- attribution is deliberately deferred to the SILVER cleaning step, so
-- Bronze stays derivation-free.
--
-- Unlike the S3-based sources there is no stage or file format to create
-- (the data is a live share), so this single file is the whole load.
-- CREATE OR REPLACE keeps it idempotent: re-running after Ordnance
-- Survey refreshes the share simply rebuilds the snapshot with no
-- duplicates.
--
-- PREREQUISITE:
--   The Code-Point Open Marketplace share is acquired (Get Data; terms
--   accepted) and mounted as
--   POSTCODE_UNITS__GREAT_BRITAIN_CODEPOINT_OPEN.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- Bronze table: faithful full copy of the shared view (all source
--   columns) + lineage. Rebuilt each run (OR REPLACE) so the load
--   stays idempotent.
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_CODE_POINT AS
SELECT
    v.POSTCODE,                          -- e.g. 'CW9 8PF' (single-space UK format)
    v.POSITIONAL_QUALITY_INDICATOR,      -- OS positional accuracy flag
    v.COUNTRY_CODE,                      -- country (E/W/S) code
    v.NHS_REGIONAL_HA_CODE,              -- NHS regional health authority code
    v.NHS_HA_CODE,                       -- NHS health authority code
    v.ADMIN_COUNTY_CODE,                 -- administrative county code
    v.ADMIN_DISTRICT_CODE,               -- administrative district / borough code
    v.ADMIN_WARD_CODE,                   -- administrative ward code (sub-borough)
    v.GEOMETRY,                          -- planar geometry (point)
    v.GEOGRAPHY,                         -- spherical GEOGRAPHY point (used downstream)
    'POSTCODE_UNITS__GREAT_BRITAIN_CODEPOINT_OPEN.PRS_CODE_POINT_OPEN_SCH.PRS_CODE_POINT_OPEN_VW'
                                         AS _SOURCE,   -- lineage: originating share object
    CURRENT_TIMESTAMP()::TIMESTAMP_NTZ   AS _LOAD_TS   -- lineage: load timestamp
FROM POSTCODE_UNITS__GREAT_BRITAIN_CODEPOINT_OPEN.PRS_CODE_POINT_OPEN_SCH.PRS_CODE_POINT_OPEN_VW v;

---------------------------------------------
-- Verify (uncomment to run interactively):
--   SELECT COUNT(*) AS postcode_rows FROM BRONZE.RAW_CODE_POINT;
--   SELECT * FROM BRONZE.RAW_CODE_POINT LIMIT 10;
---------------------------------------------
