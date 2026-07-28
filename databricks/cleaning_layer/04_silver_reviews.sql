-- Builds SILVER.REVIEWS_CLEANED: typed, deduped, validated guest reviews from BRONZE.RAW_REVIEWS.
-- Databricks port of etl/cleaning_layer/04_silver_reviews.sql.
-- ============================================================
-- SILVER — REVIEWS CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_REVIEWS (all-TEXT, 2,676,100 rows) and produces
-- a typed, deduplicated, validated table at the grain of one row
-- per review id.
--
-- Principles (same as listings/calendar):
--   * TRY_CAST everywhere: a bad value becomes a countable NULL.
--   * Trim free text; empty -> NULL.
--   * Deduplicate to one row per review_id; latest load wins.
--   * Validate: drop rows with no usable review_id or listing_id.
--   * Keep _FILENAME / _LOAD_TS lineage.
--
-- ⚠️ IDENTIFIER QUOTING: the Snowflake original used "id" / "date".
-- In Databricks double quotes are STRING LITERALS, not identifiers — see the
-- full explanation in 02_silver_listings.sql. Backticks here instead.
--
-- Other changes: USE CATALOG + three-level names; NUMBER(38,0) -> DECIMAL(38,0).
-- QUALIFY and TRY_CAST are unchanged.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.REVIEWS_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- identity / grain ----
        TRY_CAST(`id` AS DECIMAL(38,0))               AS review_id,
        TRY_CAST(`listing_id` AS DECIMAL(38,0))       AS listing_id,
        TRY_CAST(`reviewer_id` AS DECIMAL(38,0))      AS reviewer_id,

        -- ---- date ----
        TRY_CAST(`date` AS DATE)                      AS review_date,

        -- ---- free text (trimmed; empty -> NULL) ----
        NULLIF(TRIM(`reviewer_name`), '')             AS reviewer_name,
        NULLIF(TRIM(`comments`), '')                  AS comments,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_REVIEWS
)
SELECT *
FROM typed
WHERE review_id  IS NOT NULL          -- must have a usable review id
  AND listing_id IS NOT NULL          -- must tie back to a listing
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY review_id
            ORDER BY _LOAD_TS DESC
        ) = 1;                        -- one row per review, latest load wins
