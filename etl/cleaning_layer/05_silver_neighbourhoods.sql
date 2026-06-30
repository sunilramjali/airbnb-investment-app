-- Builds SILVER.NEIGHBOURHOODS_CLEANED: deduped, validated borough lookup from BRONZE.RAW_NEIGHBOURHOODS.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — NEIGHBOURHOODS CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_NEIGHBOURHOODS (all-TEXT, 33 rows) and
-- produces a clean borough lookup/dimension, one row per
-- neighbourhood (London borough).
--
-- Principles (same as the other layers):
--   * Trim text; empty -> NULL.
--   * Deduplicate to one row per neighbourhood; latest load wins.
--   * Validate: drop rows with no usable neighbourhood.
--   * Keep _FILENAME / _LOAD_TS lineage.
--
-- NOTE: source "neighbourhood_group" is the literal string "None"
-- for some cities (e.g. London groups boroughs flat) but carries a
-- real value for others, so it IS carried into silver with 'None'
-- normalised to NULL.
--
-- NOTE: bronze columns are case-sensitive lowercase identifiers
-- (PARSE_HEADER load) and MUST be double-quoted ("neighbourhood").
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.NEIGHBOURHOODS_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- borough name (grain) ----
        NULLIF(TRIM("neighbourhood"), '')   AS neighbourhood,

        -- ---- borough group ('None' literal -> NULL) ----
        NULLIF(NULLIF(TRIM("neighbourhood_group"), ''), 'None')   AS neighbourhood_group,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM BRONZE.RAW_NEIGHBOURHOODS
)
SELECT *
FROM typed
WHERE neighbourhood IS NOT NULL          -- must have a usable borough name
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY neighbourhood
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per borough, latest load wins
