-- Builds the GOLD app-data consumer layer the Streamlit app reads directly:
-- MART_LISTING (per-listing denormalized), MART_AREA (per-area + map boundary),
-- MART_AREA_STRUCTURE (area x Flat/House with median sale-price cost).
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
-- area grain. NEIGHBOURHOOD_GROUP (borough) is NULL for ~93% of
-- listings in SILVER and is intentionally NOT carried into these marts.
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
-- MART_LISTING — grain: one row per listing.
-- The app's single per-listing source (detail + comparison screens).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_LISTING
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
-- MART_AREA — grain: one row per NEIGHBOURHOOD.
-- Area Overview screen: KPIs + GEOGRAPHY boundary for the map.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready per-neighbourhood summary: listing counts, revenue/occupancy aggregates, median sale price, and boundary GEOGRAPHY for mapping.'
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
    FROM GOLD.MART_LISTING
    GROUP BY NEIGHBOURHOOD
)
SELECT
    la.NEIGHBOURHOOD,
    la.LISTING_COUNT,
    la.AVG_ADR,
    la.MEDIAN_ADR,
    la.AVG_OCCUPANCY_RATE,
    la.AVG_ANNUAL_REVENUE,
    la.MEDIAN_ANNUAL_REVENUE,
    la.AVG_BEDROOMS,
    la.AVG_RATING,
    c.median_sale_price AS MEDIAN_SALE_PRICE,
    n.AREA_SQKM,
    n.BOUNDARY
FROM listing_agg la
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON la.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN area_cost c
    ON UPPER(TRIM(la.NEIGHBOURHOOD)) = c.area_name;

-- ============================================================
-- MART_AREA_STRUCTURE — grain: NEIGHBOURHOOD x structure class.
-- Property Type screen: aggregates + median sale-price cost.
-- Listings with STRUCTURE_CLASS = NULL are excluded (no cost basis).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_STRUCTURE
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready neighbourhood x structure (Flat/House) summary: revenue/occupancy aggregates plus Land Registry median sale price (cost).'
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
)
SELECT
    m.NEIGHBOURHOOD,
    m.STRUCTURE_CLASS,
    COUNT(*)                        AS LISTING_COUNT,
    ROUND(AVG(m.ADR), 2)            AS AVG_ADR,
    MEDIAN(m.ADR)                   AS MEDIAN_ADR,
    ROUND(AVG(m.OCCUPANCY_RATE), 4) AS AVG_OCCUPANCY_RATE,
    ROUND(AVG(m.ANNUAL_REVENUE), 2) AS AVG_ANNUAL_REVENUE,
    MEDIAN(m.ANNUAL_REVENUE)        AS MEDIAN_ANNUAL_REVENUE,
    ROUND(AVG(m.BEDROOMS), 2)       AS AVG_BEDROOMS,
    ROUND(AVG(m.REVIEW_SCORES_RATING), 2) AS AVG_RATING,
    c.median_sale_price             AS MEDIAN_SALE_PRICE,
    c.sale_count                    AS SALE_TXN_COUNT
FROM GOLD.MART_LISTING m
LEFT JOIN area_cost c
    ON UPPER(TRIM(m.NEIGHBOURHOOD)) = c.area_name
   AND m.STRUCTURE_CLASS            = c.structure_class
WHERE m.STRUCTURE_CLASS IS NOT NULL
GROUP BY m.NEIGHBOURHOOD, m.STRUCTURE_CLASS, c.median_sale_price, c.sale_count;
