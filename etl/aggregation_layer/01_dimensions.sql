-- Builds the GOLD conformed dimensions (DIM_LISTING with GEO_POINT + STRUCTURE_CLASS, DIM_HOST, DIM_NEIGHBOURHOOD, DIM_POI) and a generated DIM_DATE.
-- Co-authored with CoCo
-- ============================================================
-- GOLD — DIMENSIONS
-- ------------------------------------------------------------
-- Conformed dimensions for the star. All are DYNAMIC TABLES off
-- SILVER (auto-refreshing) except DIM_DATE, which is a generated
-- static table.
--
-- KEY DERIVATIONS:
--   * GEO_POINT      = ST_MAKEPOINT(lon, lat) on each listing so ANY
--                      future point dataset (transport, landmarks)
--                      joins spatially via ST_DWITHIN — independent
--                      of the borough-name path used for sale prices.
--   * STRUCTURE_CLASS= Airbnb PROPERTY_TYPE mapped to {Flat, House},
--                      the one axis shared with Land Registry
--                      (Flat/Maisonette vs Terraced/Semi/Detached).
--                      Ambiguous types (hotel/hostel/boat/etc.) -> NULL
--                      and are excluded from yield downstream.
--
-- v1 NOTE: TARGET_LAG is an explicit '1 day' on every dynamic table
-- so each layer materializes immediately for validation. Switching
-- upstream dims/facts to TARGET_LAG = DOWNSTREAM is a later refresh
-- optimization once the marts are the pacing consumers.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ------------------------------------------------------------
-- DIM_LISTING — grain: one row per listing.
-- Rich listing attributes + spatial point + structure class.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_LISTING
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Listing dimension: attributes, GEO_POINT for spatial joins, STRUCTURE_CLASS (Flat/House) for the sale-price yield join.'
AS
SELECT
    l.LISTING_ID,
    l.HOST_ID,
    l.NAME,
    l.ROOM_TYPE,
    l.PROPERTY_TYPE,
    -- Flat vs House: match building-type keywords in PROPERTY_TYPE.
    CASE
        WHEN l.PROPERTY_TYPE ILIKE ANY ('%rental unit%','%condo%','%apartment%','%loft%','%aparthotel%')
            THEN 'Flat'
        WHEN l.PROPERTY_TYPE ILIKE ANY ('%home%','%townhouse%','%house%','%cottage%','%villa%',
                                        '%bungalow%','%cabin%','%guesthouse%','%guest suite%','%vacation%')
            THEN 'House'
        ELSE NULL   -- hotel/hostel/boat/tiny home/etc.: excluded from yield
    END                                                    AS STRUCTURE_CLASS,
    l.ACCOMMODATES,
    l.BEDROOMS,
    l.BEDS,
    l.BATHROOMS,
    l.PRICE,
    l.NEIGHBOURHOOD,
    l.NEIGHBOURHOOD_GROUP_CLEANSED                          AS NEIGHBOURHOOD_GROUP,
    l.LATITUDE,
    l.LONGITUDE,
    ST_MAKEPOINT(l.LONGITUDE, l.LATITUDE)                   AS GEO_POINT,
    l.REVIEW_SCORES_RATING,
    l.NUMBER_OF_REVIEWS,
    l.REVIEWS_PER_MONTH,
    l.INSTANT_BOOKABLE,
    l.HAS_AVAILABILITY,
    l.ESTIMATED_OCCUPANCY_L365D,
    l.ESTIMATED_REVENUE_L365D,
    l.LICENSE,
    l.LISTING_URL,
    l.PICTURE_URL
FROM SILVER.LISTINGS_CLEANED l;

-- ------------------------------------------------------------
-- DIM_HOST — grain: one row per host.
-- Deduplicated from listings (latest scrape wins per host).
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_HOST
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Host dimension, one row per HOST_ID (latest scrape wins).'
AS
SELECT
    HOST_ID,
    HOST_NAME,
    HOST_SINCE,
    HOST_IS_SUPERHOST,
    HOST_IDENTITY_VERIFIED,
    HOST_RESPONSE_RATE_PCT,
    HOST_ACCEPTANCE_RATE_PCT,
    HOST_RESPONSE_TIME,
    HOST_LISTINGS_COUNT,
    HOST_TOTAL_LISTINGS_COUNT,
    HOST_LOCATION,
    HOST_URL
FROM SILVER.LISTINGS_CLEANED
QUALIFY ROW_NUMBER() OVER (PARTITION BY HOST_ID ORDER BY LAST_SCRAPED DESC NULLS LAST) = 1;

-- ------------------------------------------------------------
-- DIM_NEIGHBOURHOOD — grain: one row per borough.
-- Carries the GEOGRAPHY boundary for point-in-polygon attribution.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_NEIGHBOURHOOD
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Neighbourhood/borough dimension with GEOGRAPHY boundary + area_sqkm.'
AS
SELECT
    NEIGHBOURHOOD,
    NEIGHBOURHOOD_GROUP,
    BOUNDARY,
    AREA_SQKM
FROM SILVER.NEIGHBOURHOODS_GEO_CLEANED;

-- ------------------------------------------------------------
-- DIM_POI — grain: one row per point of interest.
-- Location as GEOGRAPHY point for proximity features.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_POI
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Point-of-interest dimension (LOCATION geography) for listing proximity features.'
AS
SELECT
    NAME,
    CATEGORY,
    AMENITY_GROUP,
    CONFIDENCE,
    LOCATION
FROM SILVER.POI_CLEANED
WHERE CONFIDENCE >= 0.5;   -- keep reasonably confident POIs only

-- ------------------------------------------------------------
-- DIM_DATE — generated calendar dimension.
-- Static table (GENERATOR isn't incremental-friendly), spanning a
-- buffer around the CALENDAR_CLEANED range (2025-09 .. 2026-09).
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE GOLD.DIM_DATE AS
WITH span AS (
    SELECT DATEADD(day, -30, MIN(CALENDAR_DATE)) AS start_d,
           DATEADD(day,  30, MAX(CALENDAR_DATE)) AS end_d
    FROM SILVER.CALENDAR_CLEANED
),
gen AS (
    SELECT DATEADD(day, SEQ4(), (SELECT start_d FROM span)) AS d
    FROM TABLE(GENERATOR(ROWCOUNT => 1000))
)
SELECT
    d                                    AS DATE_KEY,
    YEAR(d)                              AS YEAR,
    QUARTER(d)                           AS QUARTER,
    MONTH(d)                             AS MONTH,
    MONTHNAME(d)                         AS MONTH_NAME,
    DAY(d)                               AS DAY_OF_MONTH,
    DAYOFWEEK(d)                         AS DAY_OF_WEEK,
    DAYNAME(d)                           AS DAY_NAME,
    (DAYOFWEEK(d) IN (0,6))              AS IS_WEEKEND,
    WEEKOFYEAR(d)                        AS WEEK_OF_YEAR
FROM gen
WHERE d <= (SELECT end_d FROM span);
