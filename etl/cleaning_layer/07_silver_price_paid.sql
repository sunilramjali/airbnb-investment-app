-- Builds SILVER.PRICE_PAID_CLEANED: typed, decoded, deduped HM Land Registry sales for the target counties.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — PRICE PAID (LAND REGISTRY) CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_PRICE_PAID (all-TEXT, ~5.25M rows, standard
-- HM Land Registry "Price Paid Data" schema) and produces typed,
-- validated property sales restricted to the investment areas.
--
-- Principles (same as the other layers):
--   * TRY_CAST numerics/dates; TRIM text; empty -> NULL.
--   * Decode single-letter code fields into readable labels
--     (raw code kept alongside the decoded label).
--   * Restrict to the target counties (all of London, Greater
--     Manchester, Bristol).
--   * Validate: drop rows with no transaction id, non-positive
--     price, or unparseable transfer date.
--   * Deduplicate to one row per transaction id; latest load wins.
--   * Keep _FILENAME / _FILE_ROW_NUMBER / _LOAD_TS lineage.
--
-- COUNTY SCOPE (verified distinct values in bronze):
--   * CITY OF BRISTOL      -> Bristol
--   * GREATER MANCHESTER   -> Greater Manchester
--   * GREATER LONDON       -> ALL of London. There is no separate
--                            "City of London" county in this data;
--                            City of London is a DISTRICT within
--                            GREATER LONDON, so it is included here.
--
-- DATE_OF_TRANSFER arrives as 'YYYY-MM-DD HH:MI' (time always 00:00);
-- cast to DATE.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.PRICE_PAID_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- transaction id (grain); strip the {curly braces} ----
        NULLIF(TRIM(TRANSLATE(TRANSACTION_UID, '{}', '')), '')   AS transaction_uid,

        -- ---- price & transfer date ----
        TRY_CAST(TRIM(PRICE) AS NUMBER(12, 0))                   AS price,
        TRY_CAST(TRIM(DATE_OF_TRANSFER) AS DATE)                 AS date_of_transfer,

        -- ---- address components ----
        NULLIF(TRIM(POSTCODE), '')   AS postcode,
        NULLIF(TRIM(PAON), '')       AS paon,          -- primary addressable object name (house no./name)
        NULLIF(TRIM(SAON), '')       AS saon,          -- secondary addressable object name (flat/unit)
        NULLIF(TRIM(STREET), '')     AS street,
        NULLIF(TRIM(LOCALITY), '')   AS locality,
        NULLIF(TRIM(TOWN_CITY), '')  AS town_city,
        NULLIF(TRIM(DISTRICT), '')   AS district,
        NULLIF(TRIM(COUNTY), '')     AS county,

        -- ---- coded fields: raw code + decoded label ----
        UPPER(TRIM(PROPERTY_TYPE))   AS property_type_code,
        CASE UPPER(TRIM(PROPERTY_TYPE))
            WHEN 'D' THEN 'Detached'
            WHEN 'S' THEN 'Semi-Detached'
            WHEN 'T' THEN 'Terraced'
            WHEN 'F' THEN 'Flat/Maisonette'
            WHEN 'O' THEN 'Other'
        END                          AS property_type,

        UPPER(TRIM(OLD_NEW))         AS old_new_code,
        CASE UPPER(TRIM(OLD_NEW))
            WHEN 'Y' THEN 'New Build'
            WHEN 'N' THEN 'Established'
        END                          AS build_status,

        UPPER(TRIM(DURATION))        AS duration_code,
        CASE UPPER(TRIM(DURATION))
            WHEN 'F' THEN 'Freehold'
            WHEN 'L' THEN 'Leasehold'
            WHEN 'U' THEN 'Unknown'
        END                          AS tenure,

        UPPER(TRIM(PPD_CATEGORY_TYPE))   AS ppd_category_code,
        CASE UPPER(TRIM(PPD_CATEGORY_TYPE))
            WHEN 'A' THEN 'Standard Price Paid'
            WHEN 'B' THEN 'Additional Price Paid'
        END                          AS ppd_category,

        UPPER(TRIM(RECORD_STATUS))   AS record_status_code,
        CASE UPPER(TRIM(RECORD_STATUS))
            WHEN 'A' THEN 'Addition'
            WHEN 'C' THEN 'Change'
            WHEN 'D' THEN 'Delete'
        END                          AS record_status,

        -- ---- data-quality flag (deterministic; nothing dropped) ----
        --   non_standard  : PPD category B (repossessions, portfolio/company
        --                   transfers, sales incl. multiple properties, etc.) —
        --                   NOT arm's-length market sales; ~20% of rows.
        --   price_suspect : standard sale but price outside fixed sanity bounds
        --                   (< 10,000 or > 20,000,000) — likely data error.
        --   ok            : arm's-length market sale within bounds.
        -- Bounds are FIXED round numbers (not percentiles) so the flag is
        -- reproducible on every reload. Filter WHERE quality_flag = 'ok' for
        -- true market price stats; keep the rest for investor/repossession views.
        CASE
            WHEN UPPER(TRIM(PPD_CATEGORY_TYPE)) = 'B'                     THEN 'non_standard'
            WHEN TRY_CAST(TRIM(PRICE) AS NUMBER(12,0)) < 10000
              OR TRY_CAST(TRIM(PRICE) AS NUMBER(12,0)) > 20000000        THEN 'price_suspect'
            ELSE 'ok'
        END                          AS quality_flag,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM BRONZE.RAW_PRICE_PAID
    -- county filter pushed down here so validation/dedup only touch target rows
    WHERE UPPER(TRIM(COUNTY)) IN ('CITY OF BRISTOL', 'GREATER MANCHESTER', 'GREATER LONDON')
)
SELECT *
FROM typed
WHERE transaction_uid  IS NOT NULL       -- must have a usable transaction id
  AND price            > 0               -- drop non-positive / unparseable prices
  AND date_of_transfer IS NOT NULL       -- drop unparseable transfer dates
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY transaction_uid
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per transaction, latest load wins
