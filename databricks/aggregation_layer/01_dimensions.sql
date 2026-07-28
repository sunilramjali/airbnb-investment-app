-- Builds the GOLD conformed dimensions (DIM_LISTING with GEO_POINT + STRUCTURE_CLASS, DIM_HOST, DIM_NEIGHBOURHOOD with CITY, DIM_PROPERTY_GROUP, DIM_POI) and a generated DIM_DATE.
-- Databricks port of etl/aggregation_layer/01_dimensions.sql.
-- ============================================================
-- GOLD — DIMENSIONS
-- ------------------------------------------------------------
-- Single-schema aggregation layer: the whole star + consumer objects live in
-- GOLD, distinguished by name prefix (DIM_/FCT_/MART_).
--
-- KEY DERIVATIONS (unchanged):
--   * GEO_POINT       = point per listing so ANY future point dataset joins
--                       spatially, independent of the borough-name path.
--   * STRUCTURE_CLASS = Airbnb PROPERTY_TYPE mapped to {Flat, House}, the one
--                       axis shared with Land Registry. Ambiguous -> NULL and
--                       excluded from yield downstream.
--
-- ============================================================
-- 🔴 DYNAMIC TABLE -> PLAIN TABLE, NOT MATERIALIZED VIEW
-- ------------------------------------------------------------
-- Databricks materialized views ARE the closest analogue to Snowflake dynamic
-- tables and they work on Free Edition (verified: create, MV-on-MV, query,
-- COMMENT ON COLUMN, drop). They were rejected on COST, not capability:
--
--     CREATE MATERIALIZED VIEW (3-row object) ... 5m 39s
--     CREATE TABLE AS SELECT   (3-row object) ...     4.6s
--
-- 74x, and it is pure fixed overhead — each MV provisions its own backing
-- Lakeflow pipeline, so a trivial object costs the same as a real one. Twenty
-- Gold objects would be ~110 minutes per build, paid again on every
-- CREATE OR REPLACE during development.
--
-- Auto-refresh is what we give up. That is acceptable here: this pipeline is
-- Lambda-fed QUARTERLY and Bronze/Silver are already batch driver-run, so Gold
-- becomes consistent with them rather than the odd one out. The dependency DAG
-- is carried by the driver's STEPS ordering, exactly as it always was.
--
-- Reversible: CREATE OR REPLACE TABLE <-> CREATE OR REPLACE MATERIALIZED VIEW
-- is a find-and-replace if auto-refresh is ever wanted.
--
--   TARGET_LAG = DOWNSTREAM  -> dropped (no lag to declare)
--   WAREHOUSE  = COMPUTE_WH  -> dropped (serverless; no warehouse to pin)
--   COMMENT    = '...'       -> COMMENT '...'   (no equals sign)
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA GOLD;

-- ------------------------------------------------------------
-- DIM_LISTING — grain: one row per listing.
-- ------------------------------------------------------------
-- ⚠️ ST_MAKEPOINT(lon, lat) -> st_setsrid(st_point(lon, lat), 4326).
--    The SRID is asserted EXPLICITLY. Without it the point carries SRID 0 while
--    DIM_POI.LOCATION carries 4326, and ST_DWITHIN across them is semantically
--    undefined while still appearing to work — the exact bug caught in Bronze
--    (LOG.md session 3). FCT_LISTING_POI joins these two columns.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_LISTING
    COMMENT 'Listing dimension: attributes, GEO_POINT for spatial joins, STRUCTURE_CLASS (Flat/House) for the sale-price yield join.'
AS
SELECT
    l.LISTING_ID,
    l.HOST_ID,
    l.NAME,
    l.ROOM_TYPE,
    l.PROPERTY_TYPE,
    -- Flat vs House: single source of truth = SILVER.PROPERTY_GROUP_MAP.property_class,
    -- the same whitelist that bridges listings to HM Land Registry sale prices.
    -- Keeping STRUCTURE_CLASS = property_class guarantees the Airbnb (ST) side and the
    -- sale-price/LT side never disagree. NULL = no purchasable dwelling comparator.
    pg.PROPERTY_CLASS                                       AS STRUCTURE_CLASS,
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
    st_setsrid(st_point(l.LONGITUDE, l.LATITUDE), 4326)     AS GEO_POINT,
    l.REVIEW_SCORES_RATING,
    l.NUMBER_OF_REVIEWS,
    l.REVIEWS_PER_MONTH,
    l.INSTANT_BOOKABLE,
    l.HAS_AVAILABILITY,
    l.ESTIMATED_OCCUPANCY_L365D,
    l.ESTIMATED_REVENUE_L365D,
    l.LISTING_URL,
    l.PICTURE_URL
FROM AIRBNB_INVESTMENT.SILVER.LISTINGS_CLEANED l
LEFT JOIN AIRBNB_INVESTMENT.SILVER.PROPERTY_GROUP_MAP pg
    ON LOWER(TRIM(l.PROPERTY_TYPE)) = LOWER(TRIM(pg.PROPERTY_TYPE));

-- ------------------------------------------------------------
-- DIM_PROPERTY_GROUP — grain: one row per property group.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_PROPERTY_GROUP
    COMMENT 'Property-group dimension (normalised): selection key + display order + description for the app property selector.'
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
FROM (SELECT DISTINCT PROPERTY_GROUP FROM AIRBNB_INVESTMENT.SILVER.PROPERTY_GROUP_MAP);

-- ------------------------------------------------------------
-- DIM_HOST — grain: one row per host (latest scrape wins).
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_HOST
    COMMENT 'Host dimension, one row per HOST_ID (latest scrape wins).'
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
FROM AIRBNB_INVESTMENT.SILVER.LISTINGS_CLEANED
QUALIFY ROW_NUMBER() OVER (PARTITION BY HOST_ID ORDER BY LAST_SCRAPED DESC NULLS LAST) = 1;

-- ------------------------------------------------------------
-- DIM_NEIGHBOURHOOD — grain: one row per neighbourhood.
-- Carries the boundary geometry for point-in-polygon attribution.
-- ------------------------------------------------------------
-- 🔴 SPLIT_PART(_FILENAME,'/',3) NO LONGER YIELDS THE CITY. Snowflake stored a
--    stage-relative path; Databricks stores a full s3:// URL, so position 3 is
--    the BUCKET NAME and CITY would be NULL on every row — silently. Same fix as
--    SILVER files 12 and 14: a depth-independent regexp_extract, so a bucket
--    rename or an extra prefix level cannot reintroduce it.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD
    COMMENT 'Neighbourhood dimension with CITY, boundary geometry + area_sqkm.'
AS
SELECT
    NEIGHBOURHOOD,
    CASE regexp_extract(_FILENAME, 'inside_airbnb/([^/]+)/', 1)
        WHEN 'greater_manchester' THEN 'Greater Manchester'
        WHEN 'bristol'            THEN 'Bristol'
        WHEN 'london'             THEN 'London'
    END                                  AS CITY,
    BOUNDARY,
    AREA_SQKM
FROM AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOODS_GEO_CLEANED;

-- ------------------------------------------------------------
-- DIM_POI — grain: one row per point of interest.
-- ------------------------------------------------------------
-- ✅ ILIKE ANY (...) ports VERBATIM — verified on Databricks.
-- ✅ LOCATION needs no conversion: SILVER.POI_CLEANED already carries native
--    GEOMETRY at SRID 4326, matching DIM_LISTING.GEO_POINT above.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_POI
    COMMENT 'Point-of-interest dimension (LOCATION geometry) for listing proximity features, with IS_TRANSPORT / IS_DINING classification flags (single source for all POI counts).'
AS
SELECT
    NAME,
    CATEGORY,
    AMENITY_GROUP,
    CONFIDENCE,
    LOCATION,
    -- Single source of truth for POI classification. Consumed by FCT_LISTING_POI
    -- (02) and the area POI marts (03); previously copy-pasted in three places.
    (CATEGORY ILIKE ANY ('%station%','%bus%','%transit%','%subway%','%tram%')) AS IS_TRANSPORT,
    (AMENITY_GROUP ILIKE '%dining%')                                           AS IS_DINING
FROM AIRBNB_INVESTMENT.SILVER.POI_CLEANED
-- ⚠️ THIS IS THE SECOND POI FILTER, ONE LAYER ABOVE THE FIRST.
--    Silver 08_silver_poi.sql already applied the curated amenity allow-list
--    (634,958 -> 134,713). This trims a further 12,153 low-confidence records
--    (134,713 -> 122,560), so the POI count differs by layer BY DESIGN:
--      SILVER.POI_CLEANED = 134,713   (investment-relevant)
--      GOLD.DIM_POI       = 122,560   (relevant AND trustworthy)
--    Every POI figure in Gold — FCT_LISTING_POI, MART_AREA_POI,
--    MART_AREA_OVERVIEW.POI_COUNT — is on the 122,560 base. See the note in
--    08_silver_poi.sql for why the two filters were kept separate.
WHERE CONFIDENCE >= 0.5;   -- keep reasonably confident POIs only

-- ------------------------------------------------------------
-- DIM_CITY_ASSUMPTIONS — grain: one row per city.
-- Documented, configurable investment assumptions shared by the strategy marts,
-- centralised here so the values live in one place:
--   CAP_NIGHTS                 = legal short-let night cap. London 90; else 365.
--   ASSUMED_LT_GROSS_YIELD_PCT = BTL gross yield used as the LT fallback when
--                                observed ONS rent is unavailable.
--   REALISTIC_OCC_NIGHTS       = achievable ST occupancy nights for the AT_CAP
--                                ceiling. London = 90 (legal cap binds);
--                                uncapped cities ~70% market occupancy (255).
--   ST_COST_PCT / LT_COST_PCT  = flat per-city operating-cost approximations
--                                used to derive NET yields alongside gross.
-- Static reference table. Update the VALUES list when refreshing assumptions.
-- ------------------------------------------------------------
-- ⚠️ Snowflake auto-names VALUES columns column1..columnN. Databricks does not,
--    so `column1 AS CITY` would fail. Explicit aliases used instead, which also
--    removes the positional indirection.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS
    COMMENT 'Per-city investment assumptions: legal short-let cap, assumed LT gross yield, realistic ST occupancy, and ST/LT operating cost loads.'
AS
SELECT * FROM VALUES
    ('London',             90,  4.5, 90,  28, 18),
    ('Greater Manchester', 365, 6.0, 255, 28, 18),
    ('Bristol',            365, 5.0, 255, 28, 18)
AS t(CITY, CAP_NIGHTS, ASSUMED_LT_GROSS_YIELD_PCT, REALISTIC_OCC_NIGHTS, ST_COST_PCT, LT_COST_PCT);

COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS.CITY IS 'City name (London / Greater Manchester / Bristol); join key.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS.CAP_NIGHTS IS 'Legal short-let night cap for entire-home lets (London 90; else 365 = uncapped).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS.ASSUMED_LT_GROSS_YIELD_PCT IS 'Assumed long-term buy-to-let gross yield percent; LT fallback when ONS observed rent is unavailable.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS.REALISTIC_OCC_NIGHTS IS 'Realistic achievable ST occupancy nights for the AT_CAP ceiling (London 90 = legal cap; uncapped cities ~70% = 255).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS.ST_COST_PCT IS 'ST all-in operating cost as % of gross ST revenue (management, cleaning, voids, furnishing amortisation).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS.LT_COST_PCT IS 'LT operating cost as % of gross rent (letting/management, voids, maintenance).';

-- ------------------------------------------------------------
-- DIM_DATE — generated calendar dimension, spanning a 30-day buffer around the
-- CALENDAR_CLEANED range.
-- ------------------------------------------------------------
-- 🔴 IS_WEEKEND WOULD HAVE BEEN WRONG ON EVERY ROW.
--    Snowflake DAYOFWEEK returns 0=Sunday .. 6=Saturday, so the original tested
--    `IN (0,6)`. Databricks dayofweek returns 1=Sunday .. 7=Saturday — verified:
--        2026-08-02 (Sun) -> 1 | 2026-08-01 (Sat) -> 7 | 2026-08-03 (Mon) -> 2
--    Ported verbatim, 0 never occurs and 6 is FRIDAY, so IS_WEEKEND would be
--    TRUE for Fridays and FALSE for actual weekends — with no error, in a column
--    the seasonal marts consume. Corrected to IN (1,7).
--
--    GENERATOR(ROWCOUNT => 1000) + SEQ4 -> explode(sequence(start, end, 1 day)).
--    This also removes the magic 1000 and the trailing `WHERE d <= end_d` guard:
--    sequence() is bounded by the dates themselves, so the range can never
--    silently truncate if the calendar grows beyond 1000 days.
--
--    MONTHNAME / DAYNAME do not exist -> date_format(d,'MMMM') / (d,'EEEE').
--    QUARTER / WEEKOFYEAR / YEAR / MONTH / DAY port verbatim.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.DIM_DATE
    COMMENT 'Generated calendar dimension spanning a 30-day buffer around the CALENDAR_CLEANED range.'
AS
WITH span AS (
    SELECT date_add(MIN(CALENDAR_DATE), -30) AS start_d,
           date_add(MAX(CALENDAR_DATE),  30) AS end_d
    FROM AIRBNB_INVESTMENT.SILVER.CALENDAR_CLEANED
),
gen AS (
    SELECT explode(sequence(start_d, end_d, INTERVAL 1 DAY)) AS d
    FROM span
)
SELECT
    d                                    AS DATE_KEY,
    YEAR(d)                              AS YEAR,
    QUARTER(d)                           AS QUARTER,
    MONTH(d)                             AS MONTH,
    date_format(d, 'MMMM')               AS MONTH_NAME,
    DAY(d)                               AS DAY_OF_MONTH,
    DAYOFWEEK(d)                         AS DAY_OF_WEEK,
    date_format(d, 'EEEE')               AS DAY_NAME,
    (DAYOFWEEK(d) IN (1, 7))             AS IS_WEEKEND,   -- 1=Sun, 7=Sat. NOT (0,6).
    WEEKOFYEAR(d)                        AS WEEK_OF_YEAR
FROM gen;
