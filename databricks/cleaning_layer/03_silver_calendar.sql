-- Builds SILVER.CALENDAR_CLEANED: typed, parsed, deduped, validated availability calendar from BRONZE.RAW_CALENDAR.
-- Databricks port of etl/cleaning_layer/03_silver_calendar.sql.
-- ============================================================
-- SILVER — CALENDAR CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_CALENDAR (all-TEXT, 37,510,686 rows) and produces
-- a typed, deduplicated, validated table at the grain of one row per
-- (listing_id, date).
--
-- Principles (same as listings):
--   * TRY_CAST everywhere: a bad value becomes a countable NULL.
--   * Map availability flag 't'/'f' -> BOOLEAN.
--   * Deduplicate to one row per (listing_id, date); latest load wins.
--   * Validate: drop rows with no usable listing_id or date.
--   * Keep _FILENAME / _LOAD_TS lineage.
--
-- NOTE: this source has no price / adjusted_price columns (no pricing
-- in this scrape); use LISTINGS_CLEANED.PRICE for nightly rate instead.
--
-- ⚠️ IDENTIFIER QUOTING: the Snowflake original used "date" / "listing_id".
-- In Databricks double quotes are STRING LITERALS, not identifiers — see the
-- full explanation in 02_silver_listings.sql. Backticks here instead. `date`
-- is also a reserved word, so quoting of some kind is doubly required.
--
-- Other changes: USE CATALOG + three-level names; NUMBER(p,s) -> DECIMAL(p,s).
-- QUALIFY and TRY_CAST are unchanged.
--
-- 🔬 INVARIANT: rows_out should be ~365 per listing per city (the Bronze
-- ratio was london 365.6 / manchester 365.9 / bristol 365.0). A large drop
-- here means the date parse failed, not that the source is sparse.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.CALENDAR_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- grain keys ----
        TRY_CAST(`listing_id` AS DECIMAL(38,0))                                      AS listing_id,
        TRY_CAST(`date` AS DATE)                                                     AS calendar_date,

        -- ---- availability flag: 't'/'f' -> TRUE/FALSE ----
        CASE LOWER(TRIM(`available`)) WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END     AS available,

        -- ---- stay limits ----
        TRY_CAST(`minimum_nights` AS DECIMAL(10,0))                                  AS minimum_nights,
        TRY_CAST(`maximum_nights` AS DECIMAL(10,0))                                  AS maximum_nights,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_CALENDAR
)
SELECT *
FROM typed
WHERE listing_id    IS NOT NULL          -- must have a usable listing id
  AND calendar_date IS NOT NULL          -- must have a usable date
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY listing_id, calendar_date
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per (listing, date), latest load wins
