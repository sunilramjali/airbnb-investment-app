-- Builds the GOLD conformed dimensions (DIM_LISTING with GEO_POINT + STRUCTURE_CLASS, DIM_HOST, DIM_NEIGHBOURHOOD with CITY, DIM_PROPERTY_GROUP, DIM_POI) and a generated DIM_DATE.
-- Co-authored with CoCo
-- ============================================================
-- GOLD — DIMENSIONS
-- ------------------------------------------------------------
-- Single-schema aggregation layer: the whole star + consumer objects
-- live in GOLD, distinguished by name prefix (DIM_/FCT_/AGG_/MART_/
-- VW_/FEATURE_). The GOLD schema itself is created by the setup layer
-- (setup/01_setup_database_and_warehouse.sql), so there is no separate
-- DDL file here.
--
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
-- REFRESH DESIGN: dimensions use TARGET_LAG = DOWNSTREAM — they refresh
-- only as needed to satisfy their downstream consumers (facts/marts).
-- The pacing anchor is the app marts (03_app_marts.sql), which carry an
-- explicit TARGET_LAG. Note DIM_DATE is a static generated table with no
-- lag.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ------------------------------------------------------------
-- DIM_LISTING — grain: one row per listing.
-- Rich listing attributes + spatial point + structure class.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_LISTING
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Listing dimension: attributes, GEO_POINT for spatial joins, STRUCTURE_CLASS (Flat/House) for the sale-price yield join.'
AS
SELECT
    l.LISTING_ID,
    l.HOST_ID,
    l.NAME,
    l.ROOM_TYPE,
    l.PROPERTY_TYPE,
    -- Flat vs House: single source of truth = SILVER.PROPERTY_GROUP_MAP.property_class,
    -- the same whitelist that bridges listings to HM Land Registry sale prices
    -- (07_silver_price_paid.sql). Keeping STRUCTURE_CLASS = property_class guarantees the
    -- Airbnb (ST) side and the sale-price/LT side never disagree. NULL = no purchasable
    -- dwelling comparator (hotels/guest accommodation/unique stays/etc.) -> excluded from yield.
    pg.PROPERTY_CLASS                                      AS STRUCTURE_CLASS,
    pg.PROPERTY_GROUP,
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
    l.LISTING_URL,
    l.PICTURE_URL
FROM SILVER.LISTINGS_CLEANED l
LEFT JOIN SILVER.PROPERTY_GROUP_MAP pg
    ON LOWER(TRIM(l.PROPERTY_TYPE)) = LOWER(TRIM(pg.PROPERTY_TYPE));

-- ------------------------------------------------------------
-- DIM_PROPERTY_GROUP — grain: one row per property group.
-- Normalised lookup for the property-selection control in the app.
-- PROPERTY_GROUP is the key; DISPLAY_ORDER drives selector ordering
-- and DESCRIPTION provides a short blurb per group.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_PROPERTY_GROUP
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Property-group dimension (normalised): selection key + display order + description for the app property selector.'
AS
SELECT
    PROPERTY_GROUP,
    CASE PROPERTY_GROUP
        WHEN 'Apartment / Flat'     THEN 1
        WHEN 'House'                THEN 2
        WHEN 'Guest Accommodation'  THEN 3
        WHEN 'Hotel / Hospitality'  THEN 4
        WHEN 'Unique Stay'          THEN 5
        WHEN 'Outdoor / Land'       THEN 6
        WHEN 'Other / Unknown'      THEN 7
        ELSE 99
    END                                                    AS DISPLAY_ORDER,
    CASE PROPERTY_GROUP
        WHEN 'Apartment / Flat'     THEN 'Apartments, condos, serviced apartments and aparthotels.'
        WHEN 'House'                THEN 'Houses, townhouses, bungalows, cottages, cabins and villas.'
        WHEN 'Guest Accommodation'  THEN 'Bed & breakfasts, guest suites, guesthouses and lofts.'
        WHEN 'Hotel / Hospitality'  THEN 'Hotels, boutique hotels, hostels, resorts and lodges.'
        WHEN 'Unique Stay'          THEN 'Distinctive stays: boats, cabins, treehouses, yurts and more.'
        WHEN 'Outdoor / Land'       THEN 'Campsites and tents.'
        WHEN 'Other / Unknown'      THEN 'Uncategorised or ambiguous property types.'
        ELSE NULL
    END                                                    AS DESCRIPTION
FROM (SELECT DISTINCT PROPERTY_GROUP FROM SILVER.PROPERTY_GROUP_MAP);

-- ------------------------------------------------------------
-- DIM_HOST — grain: one row per host.
-- Deduplicated from listings (latest scrape wins per host).
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_HOST
    TARGET_LAG = DOWNSTREAM
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
-- DIM_NEIGHBOURHOOD — grain: one row per neighbourhood (unique).
-- Carries the GEOGRAPHY boundary for point-in-polygon attribution.
-- CITY is derived from the source file path (region segment).
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_NEIGHBOURHOOD
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Neighbourhood dimension with CITY, GEOGRAPHY boundary + area_sqkm.'
AS
SELECT
    NEIGHBOURHOOD,
    CASE SPLIT_PART(_FILENAME, '/', 3)
        WHEN 'greater_manchester' THEN 'Greater Manchester'
        WHEN 'bristol'            THEN 'Bristol'
        WHEN 'london'             THEN 'London'
    END                                  AS CITY,
    BOUNDARY,
    AREA_SQKM
FROM SILVER.NEIGHBOURHOODS_GEO_CLEANED;

-- ------------------------------------------------------------
-- DIM_POI — grain: one row per point of interest.
-- Location as GEOGRAPHY point for proximity features.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.DIM_POI
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Point-of-interest dimension (LOCATION geography) for listing proximity features, with IS_TRANSPORT / IS_DINING classification flags (single source for all POI counts).'
AS
SELECT
    NAME,
    CATEGORY,
    AMENITY_GROUP,
    CONFIDENCE,
    LOCATION,
    -- Single source of truth for POI classification. Consumed by
    -- FCT_LISTING_POI (02) and the area POI marts (03); previously the
    -- ILIKE keyword lists were copy-pasted in three places.
    (CATEGORY ILIKE ANY ('%station%','%bus%','%transit%','%subway%','%tram%')) AS IS_TRANSPORT,
    (AMENITY_GROUP ILIKE '%dining%')                                           AS IS_DINING
FROM SILVER.POI_CLEANED
WHERE CONFIDENCE >= 0.5;   -- keep reasonably confident POIs only

-- ------------------------------------------------------------
-- DIM_CITY_ASSUMPTIONS — grain: one row per city.
-- Documented, configurable investment assumptions shared by the strategy
-- marts (05_app_marts_strategy.sql), centralised HERE so the values live in
-- one place instead of inline VALUES lists duplicated across each mart:
--   CAP_NIGHTS                 = legal short-let night cap (entire-home
--                                planning rule). London 90; else 365 (uncapped).
--   ASSUMED_LT_GROSS_YIELD_PCT = approximate buy-to-let gross yield used as the
--                                LT fallback when observed ONS rent (FCT_AREA_RENT)
--                                is unavailable. Basis: published UK BTL gross-yield
--                                reporting (e.g. Zoopla / Paragon regional yields).
--   REALISTIC_OCC_NIGHTS       = achievable ST occupancy nights used for the
--                                AT_CAP ceiling scenario. London = 90 (the legal
--                                cap binds); uncapped cities ~70% market occupancy
--                                (255) since 365-night full occupancy is unrealistic.
--   ST_COST_PCT                = ST all-in operating cost as % of gross ST revenue
--                                (management, cleaning, voids, furnishing amortisation).
--   LT_COST_PCT                = LT operating cost as % of gross rent
--                                (letting/management, voids, maintenance).
-- ST/LT cost loads are flat per-city approximations (not segment-specific) used to
-- derive NET yields alongside the gross figures. Static reference table: a VALUES
-- list has no change-tracking source, so it cannot be a dynamic table. Update the
-- VALUES list when refreshing assumptions.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE GOLD.DIM_CITY_ASSUMPTIONS AS
SELECT
    column1 AS CITY,
    column2 AS CAP_NIGHTS,
    column3 AS ASSUMED_LT_GROSS_YIELD_PCT,
    column4 AS REALISTIC_OCC_NIGHTS,
    column5 AS ST_COST_PCT,
    column6 AS LT_COST_PCT
FROM VALUES
    ('London',             90,  4.5, 90,  28, 18),
    ('Greater Manchester', 365, 6.0, 255, 28, 18),
    ('Bristol',            365, 5.0, 255, 28, 18);

COMMENT ON COLUMN GOLD.DIM_CITY_ASSUMPTIONS.CITY IS 'City name (London / Greater Manchester / Bristol); join key.';
COMMENT ON COLUMN GOLD.DIM_CITY_ASSUMPTIONS.CAP_NIGHTS IS 'Legal short-let night cap for entire-home lets (London 90; else 365 = uncapped).';
COMMENT ON COLUMN GOLD.DIM_CITY_ASSUMPTIONS.ASSUMED_LT_GROSS_YIELD_PCT IS 'Assumed long-term buy-to-let gross yield percent; LT fallback when ONS observed rent is unavailable.';
COMMENT ON COLUMN GOLD.DIM_CITY_ASSUMPTIONS.REALISTIC_OCC_NIGHTS IS 'Realistic achievable ST occupancy nights for the AT_CAP ceiling (London 90 = legal cap; uncapped cities ~70% = 255).';
COMMENT ON COLUMN GOLD.DIM_CITY_ASSUMPTIONS.ST_COST_PCT IS 'ST all-in operating cost as % of gross ST revenue (management, cleaning, voids, furnishing amortisation).';
COMMENT ON COLUMN GOLD.DIM_CITY_ASSUMPTIONS.LT_COST_PCT IS 'LT operating cost as % of gross rent (letting/management, voids, maintenance).';

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
