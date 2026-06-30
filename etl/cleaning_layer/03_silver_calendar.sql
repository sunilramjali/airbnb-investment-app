-- Builds SILVER.CALENDAR_CLEANED: typed, parsed, deduped, validated availability calendar from BRONZE.RAW_CALENDAR.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — CALENDAR CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_CALENDAR (all-TEXT, ~35M rows) and produces
-- a typed, parsed, deduplicated, validated table at the grain
-- of one row per (listing_id, date).
--
-- Principles (same as listings):
--   * TRY_CAST everywhere: a bad value becomes a countable NULL.
--   * Map availability flag 't'/'f' -> BOOLEAN.
--   * Deduplicate to one row per (listing_id, date); latest load wins.
--   * Validate: drop rows with no usable listing_id or date.
--   * Keep _FILENAME / _LOAD_TS lineage.
--
-- NOTE: this source's price / adjusted_price columns are the literal
-- string "None" for every row (no pricing in this scrape), so they
-- are intentionally NOT carried into silver. Use LISTINGS_CLEANED.PRICE
-- for nightly rate instead.
--
-- NOTE: bronze columns are case-sensitive lowercase identifiers
-- (PARSE_HEADER load) and MUST be double-quoted ("date").
-- "date" is also a reserved word, so quoting is doubly required.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.CALENDAR_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- grain keys ----
        TRY_CAST("listing_id" AS NUMBER(38,0))                                       AS listing_id,
        TRY_CAST("date" AS DATE)                                                      AS calendar_date,

        -- ---- availability flag: 't'/'f' -> TRUE/FALSE ----
        CASE LOWER(TRIM("available")) WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END      AS available,

        -- ---- stay limits ----
        TRY_CAST("minimum_nights" AS NUMBER(10,0))                                    AS minimum_nights,
        TRY_CAST("maximum_nights" AS NUMBER(10,0))                                    AS maximum_nights,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _LOAD_TS
    FROM BRONZE.RAW_CALENDAR
)
SELECT *
FROM typed
WHERE listing_id    IS NOT NULL          -- must have a usable listing id
  AND calendar_date IS NOT NULL          -- must have a usable date
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY listing_id, calendar_date
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per (listing, date), latest load wins
