-- Builds SILVER.LISTINGS_CLEANED: typed, parsed, deduped, validated listings from BRONZE.RAW_LISTINGS.
-- Databricks port of etl/cleaning_layer/02_silver_listings.sql.
-- ============================================================
-- SILVER — LISTINGS CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_LISTINGS (all-TEXT, loaded faithfully) and
-- produces a typed, parsed, deduplicated, validated table.
--
-- Principles (unchanged from Snowflake):
--   * TRY_CAST everywhere: a bad value becomes a countable NULL,
--     never a lost row or a failed load.
--   * Parse dirty strings: price "$1,250.00", rates "95%", flags "t"/"f".
--   * Deduplicate to one row per listing id (latest load wins).
--   * Validate: drop rows with no usable id or impossible coordinates.
--   * Keep _FILENAME / _LOAD_TS lineage for traceability back to bronze.
--
-- ============================================================
-- 🔴 THE ONE CHANGE THAT WOULD SILENTLY DESTROY THIS TABLE
-- ------------------------------------------------------------
-- The Snowflake original quotes every bronze column as "id", "price", ...
-- because PARSE_HEADER made them case-sensitive lowercase identifiers.
--
-- IN DATABRICKS, "id" IS THE STRING LITERAL 'id', NOT THE COLUMN.
-- Verified 2026-07-28:  SELECT `id`, "id" FROM bronze.raw_listings
--                       -> 11551 | id
--
-- Ported verbatim, TRY_CAST("id" AS DECIMAL(38,0)) would cast the literal
-- text 'id' and return NULL for every row; WHERE listing_id IS NOT NULL
-- would then drop all 102,591 rows and leave an EMPTY table with no error.
-- Every identifier is therefore backticked here.
--
-- (Backticks are used rather than bare names because several bronze columns
-- collide with reserved words — "date", "source", "license".)
--
-- OTHER MECHANICAL CHANGES
--   USE DATABASE / two-level names -> USE CATALOG / three-level names
--   NUMBER(p,s)                    -> DECIMAL(p,s)
--   FLOAT                          -> DOUBLE
--       ⚠️ NOT a cosmetic rename. Snowflake FLOAT is 8-byte double precision;
--       Databricks FLOAT is 4-byte REAL (~7 significant digits). Latitude and
--       longitude at 4-byte precision lose sub-metre accuracy, which feeds the
--       point-in-polygon joins downstream. DOUBLE is the correct equivalent.
--   TRY_CAST, QUALIFY, REGEXP_REPLACE, NULLIF, TRIM, CASE -> unchanged.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.LISTINGS_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- identity ----
        TRY_CAST(`id` AS DECIMAL(38,0))                                           AS listing_id,
        TRY_CAST(`host_id` AS DECIMAL(38,0))                                      AS host_id,
        NULLIF(TRIM(`scrape_id`), '')                                             AS scrape_id,
        NULLIF(TRIM(`source`), '')                                                AS source,
        NULLIF(TRIM(`listing_url`), '')                                           AS listing_url,
        NULLIF(TRIM(`picture_url`), '')                                           AS picture_url,

        -- ---- descriptive text (trimmed; empty -> NULL) ----
        NULLIF(TRIM(`name`), '')                                                  AS name,
        NULLIF(TRIM(`description`), '')                                           AS description,
        NULLIF(TRIM(`neighborhood_overview`), '')                                 AS neighborhood_overview,
        NULLIF(TRIM(`amenities`), '')                                             AS amenities,
        -- ---- property_type: strip room-type prefixes, lowercase, trim ----
        TRIM(REGEXP_REPLACE(
            LOWER(NULLIF(TRIM(`property_type`), '')),
            '^(entire|private room in|shared room in|room in|private room|shared room)\\s*',
            ''
        ))                                                                        AS property_type,
        NULLIF(TRIM(`room_type`), '')                                             AS room_type,
        NULLIF(TRIM(`license`), '')                                               AS license,

        -- ---- neighbourhood ----
        NULLIF(TRIM(`neighbourhood`), '')                                         AS neighbourhood_raw,
        NULLIF(TRIM(`neighbourhood_cleansed`), '')                                AS neighbourhood,
        NULLIF(TRIM(`neighbourhood_group_cleansed`), '')                          AS neighbourhood_group_cleansed,

        -- ---- host ----
        NULLIF(TRIM(`host_name`), '')                                             AS host_name,
        NULLIF(TRIM(`host_url`), '')                                              AS host_url,
        NULLIF(TRIM(`host_location`), '')                                         AS host_location,
        NULLIF(TRIM(`host_about`), '')                                            AS host_about,
        NULLIF(TRIM(`host_response_time`), '')                                    AS host_response_time,
        NULLIF(TRIM(`host_neighbourhood`), '')                                    AS host_neighbourhood,
        NULLIF(TRIM(`host_verifications`), '')                                    AS host_verifications,
        NULLIF(TRIM(`host_thumbnail_url`), '')                                    AS host_thumbnail_url,
        NULLIF(TRIM(`host_picture_url`), '')                                      AS host_picture_url,
        TRY_CAST(`host_listings_count` AS DECIMAL(10,0))                          AS host_listings_count,
        TRY_CAST(`host_total_listings_count` AS DECIMAL(10,0))                    AS host_total_listings_count,

        -- ---- geo (validated in the outer query) ----
        TRY_CAST(`latitude` AS DOUBLE)                                            AS latitude,
        TRY_CAST(`longitude` AS DOUBLE)                                           AS longitude,

        -- ---- capacity ----
        TRY_CAST(`accommodates` AS DECIMAL(10,0))                                 AS accommodates,
        TRY_CAST(`bedrooms` AS DECIMAL(10,0))                                     AS bedrooms,
        TRY_CAST(`beds` AS DECIMAL(10,0))                                         AS beds,
        TRY_CAST(`bathrooms` AS DOUBLE)                                           AS bathrooms,
        NULLIF(TRIM(`bathrooms_text`), '')                                        AS bathrooms_text,

        -- ---- money: "$1,250.00" -> 1250.00 ----
        TRY_CAST(REPLACE(REPLACE(`price`, '$', ''), ',', '') AS DECIMAL(12,2))    AS price,

        -- ---- stay limits ----
        TRY_CAST(`minimum_nights` AS DECIMAL(10,0))                               AS minimum_nights,
        TRY_CAST(`maximum_nights` AS DECIMAL(10,0))                               AS maximum_nights,
        TRY_CAST(`minimum_minimum_nights` AS DECIMAL(10,0))                       AS minimum_minimum_nights,
        TRY_CAST(`maximum_minimum_nights` AS DECIMAL(10,0))                       AS maximum_minimum_nights,
        TRY_CAST(`minimum_maximum_nights` AS DECIMAL(10,0))                       AS minimum_maximum_nights,
        TRY_CAST(`maximum_maximum_nights` AS DECIMAL(10,0))                       AS maximum_maximum_nights,
        TRY_CAST(`minimum_nights_avg_ntm` AS DOUBLE)                              AS minimum_nights_avg_ntm,
        TRY_CAST(`maximum_nights_avg_ntm` AS DOUBLE)                              AS maximum_nights_avg_ntm,

        -- ---- availability ----
        NULLIF(TRIM(`calendar_updated`), '')                                      AS calendar_updated,
        TRY_CAST(`availability_30` AS DECIMAL(10,0))                              AS availability_30,
        TRY_CAST(`availability_60` AS DECIMAL(10,0))                              AS availability_60,
        TRY_CAST(`availability_90` AS DECIMAL(10,0))                              AS availability_90,
        TRY_CAST(`availability_365` AS DECIMAL(10,0))                             AS availability_365,
        TRY_CAST(`availability_eoy` AS DECIMAL(10,0))                             AS availability_eoy,

        -- ---- reviews ----
        TRY_CAST(`number_of_reviews` AS DECIMAL(10,0))                            AS number_of_reviews,
        TRY_CAST(`number_of_reviews_ltm` AS DECIMAL(10,0))                        AS number_of_reviews_ltm,
        TRY_CAST(`number_of_reviews_l30d` AS DECIMAL(10,0))                       AS number_of_reviews_l30d,
        TRY_CAST(`number_of_reviews_ly` AS DECIMAL(10,0))                         AS number_of_reviews_ly,
        TRY_CAST(`reviews_per_month` AS DOUBLE)                                   AS reviews_per_month,
        TRY_CAST(`review_scores_rating` AS DOUBLE)                                AS review_scores_rating,
        TRY_CAST(`review_scores_accuracy` AS DOUBLE)                              AS review_scores_accuracy,
        TRY_CAST(`review_scores_cleanliness` AS DOUBLE)                           AS review_scores_cleanliness,
        TRY_CAST(`review_scores_checkin` AS DOUBLE)                               AS review_scores_checkin,
        TRY_CAST(`review_scores_communication` AS DOUBLE)                         AS review_scores_communication,
        TRY_CAST(`review_scores_location` AS DOUBLE)                              AS review_scores_location,
        TRY_CAST(`review_scores_value` AS DOUBLE)                                 AS review_scores_value,

        -- ---- estimates (Inside Airbnb derived) ----
        TRY_CAST(`estimated_occupancy_l365d` AS DECIMAL(10,0))                                  AS estimated_occupancy_l365d,
        TRY_CAST(REPLACE(REPLACE(`estimated_revenue_l365d`, '$', ''), ',', '') AS DECIMAL(12,2)) AS estimated_revenue_l365d,

        -- ---- calculated host listing counts ----
        TRY_CAST(`calculated_host_listings_count` AS DECIMAL(10,0))               AS calculated_host_listings_count,
        TRY_CAST(`calculated_host_listings_count_entire_homes` AS DECIMAL(10,0))  AS calculated_host_listings_count_entire_homes,
        TRY_CAST(`calculated_host_listings_count_private_rooms` AS DECIMAL(10,0)) AS calculated_host_listings_count_private_rooms,
        TRY_CAST(`calculated_host_listings_count_shared_rooms` AS DECIMAL(10,0))  AS calculated_host_listings_count_shared_rooms,

        -- ---- rates: "95%" -> 95 ----
        TRY_CAST(REPLACE(`host_response_rate`, '%', '') AS DECIMAL(5,0))          AS host_response_rate_pct,
        TRY_CAST(REPLACE(`host_acceptance_rate`, '%', '') AS DECIMAL(5,0))        AS host_acceptance_rate_pct,

        -- ---- booleans: 't'/'f' -> TRUE/FALSE ----
        CASE LOWER(TRIM(`host_is_superhost`))      WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS host_is_superhost,
        CASE LOWER(TRIM(`host_identity_verified`)) WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS host_identity_verified,
        CASE LOWER(TRIM(`host_has_profile_pic`))   WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS host_has_profile_pic,
        CASE LOWER(TRIM(`instant_bookable`))       WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS instant_bookable,
        CASE LOWER(TRIM(`has_availability`))       WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS has_availability,

        -- ---- dates ----
        TRY_CAST(`last_scraped` AS DATE)                                          AS last_scraped,
        TRY_CAST(`calendar_last_scraped` AS DATE)                                 AS calendar_last_scraped,
        TRY_CAST(`host_since` AS DATE)                                            AS host_since,
        TRY_CAST(`first_review` AS DATE)                                          AS first_review,
        TRY_CAST(`last_review` AS DATE)                                           AS last_review,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_LISTINGS
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
