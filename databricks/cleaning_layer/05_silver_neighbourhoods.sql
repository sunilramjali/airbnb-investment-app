-- Builds SILVER.NEIGHBOURHOODS_CLEANED: deduped, validated borough lookup from BRONZE.RAW_NEIGHBOURHOODS.
-- Databricks port of etl/cleaning_layer/05_silver_neighbourhoods.sql.
-- ============================================================
-- SILVER — NEIGHBOURHOODS CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_NEIGHBOURHOODS (all-TEXT, 108 rows across the
-- three cities) and produces a clean borough lookup/dimension, one
-- row per neighbourhood.
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
-- ⚠️ IDENTIFIER QUOTING: the Snowflake original used "neighbourhood".
-- In Databricks double quotes are STRING LITERALS, not identifiers — see the
-- full explanation in 02_silver_listings.sql. Backticks here instead.
--
-- 📄 INVARIANT: 108 rows out, and all 108 names must match the Inside Airbnb
-- names exactly (docs/data_pipeline.md:88). This is one of only four Silver
-- invariants that survived the loss of Snowflake, so a miss here is a blocker,
-- not a note. See databricks/verification_invariants.md.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOODS_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- borough name (grain) ----
        NULLIF(TRIM(`neighbourhood`), '')   AS neighbourhood,

        -- ---- borough group ('None' literal -> NULL) ----
        NULLIF(NULLIF(TRIM(`neighbourhood_group`), ''), 'None')   AS neighbourhood_group,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_NEIGHBOURHOODS
)
SELECT *
FROM typed
WHERE neighbourhood IS NOT NULL          -- must have a usable borough name
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY neighbourhood
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per borough, latest load wins
