-- Builds SILVER.LISTINGS_CLEANED: typed, parsed, deduped, validated listings from BRONZE.RAW_LISTINGS.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — LISTINGS CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_LISTINGS (all-TEXT, loaded faithfully) and
-- produces a typed, parsed, deduplicated, validated table.
--
-- Principles:
--   * TRY_CAST everywhere: a bad value becomes a countable NULL,
--     never a lost row or a failed load.
--   * Parse dirty strings: price "$1,250.00", rates "95%", flags "t"/"f".
--   * Deduplicate to one row per listing id (latest load wins).
--   * Validate: drop rows with no usable id or impossible coordinates.
--   * Keep _FILENAME / _LOAD_TS lineage for traceability back to bronze.
--
-- NOTE: bronze columns were loaded with PARSE_HEADER, so they are
-- case-sensitive lowercase identifiers and MUST be double-quoted
-- ("id", "price", ...). Lineage columns (_FILENAME, _LOAD_TS) are
-- unquoted uppercase.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.LISTINGS_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- identity ----
        TRY_CAST("id" AS NUMBER(38,0))                                            AS listing_id,
        TRY_CAST("host_id" AS NUMBER(38,0))                                       AS host_id,

        -- ---- descriptive text (trimmed; empty -> NULL) ----
        NULLIF(TRIM("name"), '')                                                  AS name,
        NULLIF(TRIM("property_type"), '')                                         AS property_type,
        NULLIF(TRIM("room_type"), '')                                             AS room_type,
        NULLIF(TRIM("neighbourhood_cleansed"), '')                                AS neighbourhood,
        NULLIF(TRIM("host_name"), '')                                             AS host_name,
        NULLIF(TRIM("host_response_time"), '')                                    AS host_response_time,

        -- ---- geo (validated in the outer query) ----
        TRY_CAST("latitude" AS FLOAT)                                             AS latitude,
        TRY_CAST("longitude" AS FLOAT)                                            AS longitude,

        -- ---- capacity ----
        TRY_CAST("accommodates" AS NUMBER(10,0))                                  AS accommodates,
        TRY_CAST("bedrooms" AS NUMBER(10,0))                                      AS bedrooms,
        TRY_CAST("beds" AS NUMBER(10,0))                                          AS beds,
        TRY_CAST("bathrooms" AS FLOAT)                                            AS bathrooms,

        -- ---- money: "$1,250.00" -> 1250.00 ----
        TRY_CAST(REPLACE(REPLACE("price", '$', ''), ',', '') AS NUMBER(12,2))     AS price,

        -- ---- stay limits ----
        TRY_CAST("minimum_nights" AS NUMBER(10,0))                                AS minimum_nights,
        TRY_CAST("maximum_nights" AS NUMBER(10,0))                                AS maximum_nights,

        -- ---- availability ----
        TRY_CAST("availability_30" AS NUMBER(10,0))                               AS availability_30,
        TRY_CAST("availability_60" AS NUMBER(10,0))                               AS availability_60,
        TRY_CAST("availability_90" AS NUMBER(10,0))                               AS availability_90,
        TRY_CAST("availability_365" AS NUMBER(10,0))                              AS availability_365,

        -- ---- reviews ----
        TRY_CAST("number_of_reviews" AS NUMBER(10,0))                             AS number_of_reviews,
        TRY_CAST("number_of_reviews_ltm" AS NUMBER(10,0))                         AS number_of_reviews_ltm,
        TRY_CAST("reviews_per_month" AS FLOAT)                                    AS reviews_per_month,
        TRY_CAST("review_scores_rating" AS FLOAT)                                 AS review_scores_rating,
        TRY_CAST("review_scores_accuracy" AS FLOAT)                               AS review_scores_accuracy,
        TRY_CAST("review_scores_cleanliness" AS FLOAT)                            AS review_scores_cleanliness,
        TRY_CAST("review_scores_checkin" AS FLOAT)                                AS review_scores_checkin,
        TRY_CAST("review_scores_communication" AS FLOAT)                          AS review_scores_communication,
        TRY_CAST("review_scores_location" AS FLOAT)                               AS review_scores_location,
        TRY_CAST("review_scores_value" AS FLOAT)                                  AS review_scores_value,

        -- ---- rates: "95%" -> 95 ----
        TRY_CAST(REPLACE("host_response_rate", '%', '') AS NUMBER(5,0))           AS host_response_rate_pct,
        TRY_CAST(REPLACE("host_acceptance_rate", '%', '') AS NUMBER(5,0))         AS host_acceptance_rate_pct,

        -- ---- booleans: 't'/'f' -> TRUE/FALSE ----
        CASE LOWER(TRIM("host_is_superhost"))      WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS host_is_superhost,
        CASE LOWER(TRIM("host_identity_verified")) WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS host_identity_verified,
        CASE LOWER(TRIM("instant_bookable"))       WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS instant_bookable,
        CASE LOWER(TRIM("has_availability"))       WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS has_availability,

        -- ---- dates ----
        TRY_CAST("last_scraped" AS DATE)                                          AS last_scraped,
        TRY_CAST("host_since" AS DATE)                                            AS host_since,
        TRY_CAST("first_review" AS DATE)                                          AS first_review,
        TRY_CAST("last_review" AS DATE)                                           AS last_review,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _LOAD_TS
    FROM BRONZE.RAW_LISTINGS
)
SELECT *
FROM typed
WHERE listing_id IS NOT NULL                              -- must have a usable id
  AND latitude  BETWEEN -90  AND 90                       -- drop impossible coordinates
  AND longitude BETWEEN -180 AND 180
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY listing_id
            ORDER BY _LOAD_TS DESC, last_scraped DESC NULLS LAST
        ) = 1;                                            -- one row per listing, latest load wins
