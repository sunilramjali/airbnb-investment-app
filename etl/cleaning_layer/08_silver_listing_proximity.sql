-- Builds SILVER.LISTING_ATTRACTION_PROXIMITY: per-listing attraction proximity features for investment scoring.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — LISTING x ATTRACTION PROXIMITY FEATURES
-- ------------------------------------------------------------
-- The actual investment signal: for each listing, how close and how many
-- landmarks/attractions are nearby. Joins SILVER.LISTINGS_CLEANED
-- (lat/long) to SILVER.ATTRACTIONS_CLEANED (GEOGRAPHY points) by distance.
--
-- Grain: one row per listing (LEFT JOIN keeps listings with no nearby
-- attraction — their counts are 0 and NEAREST_* are NULL).
--
-- Approach:
--   * Build a GEOGRAPHY point per listing from LONGITUDE/LATITUDE
--     (ST_MAKEPOINT takes lon, lat order).
--   * Bound the join with ST_DWITHIN(..., 3000) so we only measure
--     pairs within 3 km — enough for "nearest" in dense UK cities while
--     keeping the join from becoming a full listings x attractions cross.
--   * Aggregate: nearest distance + counts inside 500 m / 1 km rings,
--     plus the nearest attraction's name/type via MIN_BY.
--
-- PREREQUISITE: SILVER.LISTINGS_CLEANED and SILVER.ATTRACTIONS_CLEANED.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.LISTING_ATTRACTION_PROXIMITY AS
WITH listing_pts AS (
    SELECT
        LISTING_ID,
        NEIGHBOURHOOD,
        ST_MAKEPOINT(LONGITUDE, LATITUDE) AS listing_location   -- lon, lat order
    FROM SILVER.LISTINGS_CLEANED
    WHERE LATITUDE IS NOT NULL
      AND LONGITUDE IS NOT NULL
),
pairs AS (
    SELECT
        l.LISTING_ID,
        l.NEIGHBOURHOOD,
        l.listing_location,
        a.NAME                                        AS attraction_name,
        a.ATTRACTION_TYPE                             AS attraction_type,
        ST_DISTANCE(l.listing_location, a.LOCATION)   AS dist_m       -- metres (GEOGRAPHY)
    FROM listing_pts l
    LEFT JOIN SILVER.ATTRACTIONS_CLEANED a
        ON ST_DWITHIN(l.listing_location, a.LOCATION, 3000)   -- bound the join to 3 km
)
SELECT
    LISTING_ID,
    ANY_VALUE(NEIGHBOURHOOD)                    AS NEIGHBOURHOOD,
    ANY_VALUE(listing_location)                 AS LISTING_LOCATION,
    MIN(dist_m)                                 AS NEAREST_ATTRACTION_M,       -- NULL if none within 3 km
    MIN_BY(attraction_name, dist_m)             AS NEAREST_ATTRACTION_NAME,
    MIN_BY(attraction_type, dist_m)             AS NEAREST_ATTRACTION_TYPE,
    COUNT_IF(dist_m <= 500)                     AS ATTRACTIONS_WITHIN_500M,    -- 0 when none (COUNT_IF ignores NULLs)
    COUNT_IF(dist_m <= 1000)                    AS ATTRACTIONS_WITHIN_1KM,
    COUNT_IF(dist_m <= 3000)                    AS ATTRACTIONS_WITHIN_3KM,
    CURRENT_TIMESTAMP()::TIMESTAMP_NTZ          AS _LOAD_TS
FROM pairs
GROUP BY LISTING_ID;
