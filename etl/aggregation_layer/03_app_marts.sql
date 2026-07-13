-- Builds the GOLD app-data consumer layer the Streamlit app reads directly:
-- MART_LISTING_CANDIDATES (per-listing denormalized), MART_AREA_OVERVIEW (per-area + map boundary),
-- MART_PROPERTY_GROUP (area x property group with median sale-price cost).
-- Co-authored with CoCo
-- ============================================================
-- GOLD — APP MARTS (consumer layer)
-- ------------------------------------------------------------
-- These are the ONLY objects the app queries (architecture rule:
-- "the app reads the GOLD schema only"). Fully denormalized so the
-- app performs zero joins at query time. They read from the star
-- (DIM_*/FCT_*); the star itself is untouched.
--
-- Investment scores / maximiser rankings are produced by the AI
-- layer downstream and are intentionally NOT computed here — this
-- layer supplies the underlying data only (area, mapping geometry,
-- revenue, cost benchmark, property attributes).
--
-- AREA KEY: NEIGHBOURHOOD (100% populated, 108 distinct) is the sole
-- area grain. CITY (Greater Manchester / Bristol / London), derived in
-- DIM_NEIGHBOURHOOD from the source file path, is carried into MART_AREA_OVERVIEW
-- for area-level grouping/filtering.
--
-- COST BENCHMARK: Land Registry median sale PRICE
-- (SILVER.PRICE_PAID_CLEANED) at area x structure grain. A listing's
-- NEIGHBOURHOOD is matched against Land Registry DISTRICT *or*
-- TOWN_CITY (unified name lookup) — ~80% of listings match. LR
-- PROPERTY_TYPE_CODE maps to STRUCTURE_CLASS: F -> Flat; D/S/T ->
-- House; O -> excluded.
--
-- REFRESH DESIGN: the marts are the leaf consumers and carry an
-- explicit TARGET_LAG = '1 day' — they define the freshness SLA that
-- anchors the whole chain. The upstream dims/facts they read use
-- TARGET_LAG = DOWNSTREAM and refresh only as needed to serve these.
-- Warehouse AIRBNB_APP_WH.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ============================================================
-- MART_LISTING_CANDIDATES — grain: one row per listing.
-- The app's single per-listing source (detail + comparison screens).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_LISTING_CANDIDATES
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready per-listing dataset: area (NEIGHBOURHOOD), mapping geo, property attributes, revenue metrics, and area x structure median sale-price cost benchmark.'
AS
WITH area_cost AS (
    -- Median LR sale price per area-name x structure. Area name is
    -- taken from BOTH district and town_city so listing NEIGHBOURHOOD
    -- can match either granularity.
    SELECT area_name, structure_class, MEDIAN(price) AS median_sale_price
    FROM (
        SELECT UPPER(TRIM(DISTRICT))  AS area_name, PROPERTY_TYPE_CODE, PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE DISTRICT IS NOT NULL
        UNION ALL
        SELECT UPPER(TRIM(TOWN_CITY)) AS area_name, PROPERTY_TYPE_CODE, PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE TOWN_CITY IS NOT NULL
    ) src
    CROSS JOIN LATERAL (
        SELECT CASE
                   WHEN src.PROPERTY_TYPE_CODE = 'F'            THEN 'Flat'
                   WHEN src.PROPERTY_TYPE_CODE IN ('D','S','T') THEN 'House'
               END AS structure_class
    ) m
    WHERE src.PROPERTY_TYPE_CODE IN ('F','D','S','T')
    GROUP BY area_name, structure_class
)
SELECT
    s.LISTING_ID,
    s.HOST_ID,
    d.NAME,
    d.NEIGHBOURHOOD,
    d.LATITUDE,
    d.LONGITUDE,
    d.GEO_POINT,
    d.ROOM_TYPE,
    d.PROPERTY_TYPE,
    d.STRUCTURE_CLASS,
    d.PROPERTY_GROUP,
    d.ACCOMMODATES,
    d.BEDROOMS,
    d.BEDS,
    d.BATHROOMS,
    s.ADR,
    s.OCCUPANCY_RATE,
    s.ANNUAL_REVENUE,
    s.REVPAR,
    (s.ANNUAL_REVENUE IS NOT NULL) AS HAS_REVENUE_DATA,
    c.median_sale_price AS AREA_MEDIAN_SALE_PRICE,
    s.REVIEW_SCORES_RATING,
    s.NUMBER_OF_REVIEWS,
    h.HOST_IS_SUPERHOST,
    p.POI_COUNT_500M,
    p.TRANSPORT_COUNT_500M,
    p.DINING_COUNT_500M,
    d.INSTANT_BOOKABLE,
    d.LISTING_URL,
    d.PICTURE_URL
FROM GOLD.FCT_LISTING_SNAPSHOT s
JOIN GOLD.DIM_LISTING d
    ON s.LISTING_ID = d.LISTING_ID
LEFT JOIN GOLD.DIM_HOST h
    ON s.HOST_ID = h.HOST_ID
LEFT JOIN GOLD.FCT_LISTING_POI p
    ON s.LISTING_ID = p.LISTING_ID
LEFT JOIN area_cost c
    ON UPPER(TRIM(d.NEIGHBOURHOOD)) = c.area_name
   AND d.STRUCTURE_CLASS           = c.structure_class;

-- ============================================================
-- MART_AREA_OVERVIEW — grain: one row per NEIGHBOURHOOD.
-- Area Overview screen: KPIs + GEOGRAPHY boundary for the map.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready per-neighbourhood summary: CITY, listing counts, revenue/occupancy aggregates, median sale price, in-area POI counts, and boundary GEOGRAPHY for mapping.'
AS
WITH area_cost AS (
    SELECT area_name, MEDIAN(price) AS median_sale_price
    FROM (
        SELECT UPPER(TRIM(DISTRICT))  AS area_name, PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE DISTRICT IS NOT NULL AND PROPERTY_TYPE_CODE IN ('F','D','S','T')
        UNION ALL
        SELECT UPPER(TRIM(TOWN_CITY)) AS area_name, PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE TOWN_CITY IS NOT NULL AND PROPERTY_TYPE_CODE IN ('F','D','S','T')
    ) src
    GROUP BY area_name
),
listing_agg AS (
    SELECT
        NEIGHBOURHOOD,
        COUNT(*)                       AS LISTING_COUNT,
        ROUND(AVG(ADR), 2)             AS AVG_ADR,
        MEDIAN(ADR)                    AS MEDIAN_ADR,
        ROUND(AVG(OCCUPANCY_RATE), 4)  AS AVG_OCCUPANCY_RATE,
        ROUND(AVG(ANNUAL_REVENUE), 2)  AS AVG_ANNUAL_REVENUE,
        MEDIAN(ANNUAL_REVENUE)         AS MEDIAN_ANNUAL_REVENUE,
        ROUND(AVG(BEDROOMS), 2)        AS AVG_BEDROOMS,
        ROUND(AVG(REVIEW_SCORES_RATING), 2) AS AVG_RATING
    FROM GOLD.MART_LISTING_CANDIDATES
    GROUP BY NEIGHBOURHOOD
),
area_poi AS (
    -- POIs falling inside each neighbourhood boundary (point-in-polygon).
    SELECT
        n.NEIGHBOURHOOD,
        COUNT(*)                                                           AS POI_COUNT,
        COUNT(CASE WHEN p.CATEGORY ILIKE ANY ('%station%','%bus%','%transit%','%subway%','%tram%')
                   THEN 1 END)                                             AS TRANSPORT_COUNT,
        COUNT(CASE WHEN p.AMENITY_GROUP ILIKE '%dining%' THEN 1 END)       AS DINING_COUNT
    FROM GOLD.DIM_NEIGHBOURHOOD n
    JOIN GOLD.DIM_POI p
        ON ST_CONTAINS(n.BOUNDARY, p.LOCATION)
    GROUP BY n.NEIGHBOURHOOD
)
SELECT
    la.NEIGHBOURHOOD,
    n.CITY,
    la.LISTING_COUNT,
    la.AVG_ADR,
    la.MEDIAN_ADR,
    la.AVG_OCCUPANCY_RATE,
    la.AVG_ANNUAL_REVENUE,
    la.MEDIAN_ANNUAL_REVENUE,
    la.AVG_BEDROOMS,
    la.AVG_RATING,
    c.median_sale_price AS MEDIAN_SALE_PRICE,
    COALESCE(ap.POI_COUNT, 0)       AS POI_COUNT,
    COALESCE(ap.TRANSPORT_COUNT, 0) AS TRANSPORT_COUNT,
    COALESCE(ap.DINING_COUNT, 0)    AS DINING_COUNT,
    ROUND(COALESCE(ap.POI_COUNT, 0) / NULLIF(n.AREA_SQKM, 0), 2) AS POI_DENSITY_SQKM,
    n.AREA_SQKM,
    n.BOUNDARY
FROM listing_agg la
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON la.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN area_cost c
    ON UPPER(TRIM(la.NEIGHBOURHOOD)) = c.area_name
LEFT JOIN area_poi ap
    ON la.NEIGHBOURHOOD = ap.NEIGHBOURHOOD;

-- ============================================================
-- MART_PROPERTY_GROUP — grain: NEIGHBOURHOOD x PROPERTY_GROUP.
-- Property selection screen: pick a neighbourhood, then see each of the
-- 7 property groups. Every (neighbourhood, group) combo is emitted via a
-- scaffold, so groups with no listings in the area still appear
-- (LISTING_COUNT = 0, HAS_LOCAL_DATA = FALSE) instead of vanishing.
--
-- Three tiers of averages, kept as SEPARATE columns so the app never
-- shows a wider figure disguised as a local one:
--   * AVG_*      — true neighbourhood x group average (primary), always
--                  paired with LISTING_COUNT so reliability is visible.
--   * CITY_AVG_* — city x group benchmark (Greater Manchester / Bristol /
--                  London), for fallback when local data is thin/absent.
--   * ALL_AVG_*  — group benchmark across all neighbourhoods.
-- The app shows AVG_* (LISTING_COUNT) as headline and falls back to
-- CITY_AVG_* / ALL_AVG_* with an explicit "wider area" label when
-- HAS_LOCAL_DATA is FALSE or the count is low.
--
-- Median sale-price cost is joined where the group maps to a Land
-- Registry structure (Apartment/Flat -> Flat, House -> House); other
-- groups have no sale-price basis (NULL cost). PROPERTY_GROUP is the
-- selection key; group details live in DIM_PROPERTY_GROUP (normalised).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_PROPERTY_GROUP
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready neighbourhood x property group summary: all 7 groups per neighbourhood with true local averages + count, city and all-areas benchmark averages, HAS_LOCAL_DATA flag, and Land Registry median sale price where the group maps to Flat/House.'
AS
WITH area_cost AS (
    SELECT area_name, structure_class, MEDIAN(price) AS median_sale_price, COUNT(*) AS sale_count
    FROM (
        SELECT UPPER(TRIM(DISTRICT))  AS area_name, PROPERTY_TYPE_CODE, PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE DISTRICT IS NOT NULL
        UNION ALL
        SELECT UPPER(TRIM(TOWN_CITY)) AS area_name, PROPERTY_TYPE_CODE, PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE TOWN_CITY IS NOT NULL
    ) src
    CROSS JOIN LATERAL (
        SELECT CASE
                   WHEN src.PROPERTY_TYPE_CODE = 'F'            THEN 'Flat'
                   WHEN src.PROPERTY_TYPE_CODE IN ('D','S','T') THEN 'House'
               END AS structure_class
    ) m
    WHERE src.PROPERTY_TYPE_CODE IN ('F','D','S','T')
    GROUP BY area_name, structure_class
),
-- All neighbourhood x group combinations (108 x 7). CITY carried through
-- for the city-level benchmark join and app filtering.
scaffold AS (
    SELECT n.NEIGHBOURHOOD, n.CITY, g.PROPERTY_GROUP
    FROM GOLD.DIM_NEIGHBOURHOOD n
    CROSS JOIN GOLD.DIM_PROPERTY_GROUP g
),
-- Tier 1: true neighbourhood x group aggregates.
local_agg AS (
    SELECT
        m.NEIGHBOURHOOD,
        m.PROPERTY_GROUP,
        COUNT(*)                        AS LISTING_COUNT,
        ROUND(AVG(m.ADR), 2)            AS AVG_ADR,
        MEDIAN(m.ADR)                   AS MEDIAN_ADR,
        ROUND(AVG(m.OCCUPANCY_RATE), 4) AS AVG_OCCUPANCY_RATE,
        ROUND(AVG(m.ANNUAL_REVENUE), 2) AS AVG_ANNUAL_REVENUE,
        MEDIAN(m.ANNUAL_REVENUE)        AS MEDIAN_ANNUAL_REVENUE,
        ROUND(AVG(m.BEDROOMS), 2)       AS AVG_BEDROOMS,
        ROUND(AVG(m.REVIEW_SCORES_RATING), 2) AS AVG_RATING
    FROM GOLD.MART_LISTING_CANDIDATES m
    WHERE m.PROPERTY_GROUP IS NOT NULL
    GROUP BY m.NEIGHBOURHOOD, m.PROPERTY_GROUP
),
-- Tier 2: city x group benchmark (CITY sourced from DIM_NEIGHBOURHOOD).
city_agg AS (
    SELECT
        n.CITY,
        m.PROPERTY_GROUP,
        COUNT(*)                        AS CITY_LISTING_COUNT,
        ROUND(AVG(m.ADR), 2)            AS CITY_AVG_ADR,
        ROUND(AVG(m.OCCUPANCY_RATE), 4) AS CITY_AVG_OCCUPANCY_RATE,
        ROUND(AVG(m.ANNUAL_REVENUE), 2) AS CITY_AVG_ANNUAL_REVENUE
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON m.NEIGHBOURHOOD = n.NEIGHBOURHOOD
    WHERE m.PROPERTY_GROUP IS NOT NULL
    GROUP BY n.CITY, m.PROPERTY_GROUP
),
-- Tier 3: group benchmark across all neighbourhoods.
all_agg AS (
    SELECT
        m.PROPERTY_GROUP,
        COUNT(*)                        AS ALL_LISTING_COUNT,
        ROUND(AVG(m.ADR), 2)            AS ALL_AVG_ADR,
        ROUND(AVG(m.OCCUPANCY_RATE), 4) AS ALL_AVG_OCCUPANCY_RATE,
        ROUND(AVG(m.ANNUAL_REVENUE), 2) AS ALL_AVG_ANNUAL_REVENUE
    FROM GOLD.MART_LISTING_CANDIDATES m
    WHERE m.PROPERTY_GROUP IS NOT NULL
    GROUP BY m.PROPERTY_GROUP
)
SELECT
    s.NEIGHBOURHOOD,
    s.CITY,
    s.PROPERTY_GROUP,
    -- Tier 1: local (primary)
    COALESCE(la.LISTING_COUNT, 0)   AS LISTING_COUNT,
    (COALESCE(la.LISTING_COUNT, 0) > 0) AS HAS_LOCAL_DATA,
    la.AVG_ADR,
    la.MEDIAN_ADR,
    la.AVG_OCCUPANCY_RATE,
    la.AVG_ANNUAL_REVENUE,
    la.MEDIAN_ANNUAL_REVENUE,
    la.AVG_BEDROOMS,
    la.AVG_RATING,
    -- Tier 2: city benchmark
    ca.CITY_LISTING_COUNT,
    ca.CITY_AVG_ADR,
    ca.CITY_AVG_OCCUPANCY_RATE,
    ca.CITY_AVG_ANNUAL_REVENUE,
    -- Tier 3: all-areas benchmark
    aa.ALL_LISTING_COUNT,
    aa.ALL_AVG_ADR,
    aa.ALL_AVG_OCCUPANCY_RATE,
    aa.ALL_AVG_ANNUAL_REVENUE,
    -- Cost benchmark (Flat/House only)
    c.median_sale_price             AS MEDIAN_SALE_PRICE,
    c.sale_count                    AS SALE_TXN_COUNT
FROM scaffold s
LEFT JOIN local_agg la
    ON s.NEIGHBOURHOOD = la.NEIGHBOURHOOD
   AND s.PROPERTY_GROUP = la.PROPERTY_GROUP
LEFT JOIN city_agg ca
    ON s.CITY = ca.CITY
   AND s.PROPERTY_GROUP = ca.PROPERTY_GROUP
LEFT JOIN all_agg aa
    ON s.PROPERTY_GROUP = aa.PROPERTY_GROUP
LEFT JOIN area_cost c
    ON UPPER(TRIM(s.NEIGHBOURHOOD)) = c.area_name
   AND CASE
           WHEN s.PROPERTY_GROUP = 'Apartment / Flat' THEN 'Flat'
           WHEN s.PROPERTY_GROUP = 'House'            THEN 'House'
       END = c.structure_class;

-- ============================================================
-- MART_AREA_POI — grain: one row per POI inside a neighbourhood.
-- Map-marker feed for the Area Overview screen. Consistent with
-- MART_AREA_OVERVIEW's POI counts (same point-in-polygon join). Reads
-- with a simple WHERE NEIGHBOURHOOD = :area filter.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_POI
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready POI markers per neighbourhood (point-in-polygon): name, category, amenity group, transport/dining flags, and lat/lon for map plotting.'
AS
SELECT
    n.NEIGHBOURHOOD,
    n.CITY,
    p.NAME                                                             AS POI_NAME,
    p.CATEGORY,
    p.AMENITY_GROUP,
    (p.CATEGORY ILIKE ANY ('%station%','%bus%','%transit%','%subway%','%tram%')) AS IS_TRANSPORT,
    (p.AMENITY_GROUP ILIKE '%dining%')                                 AS IS_DINING,
    ST_Y(p.LOCATION)                                                   AS LATITUDE,
    ST_X(p.LOCATION)                                                   AS LONGITUDE
FROM GOLD.DIM_NEIGHBOURHOOD n
JOIN GOLD.DIM_POI p
    ON ST_CONTAINS(n.BOUNDARY, p.LOCATION);

