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
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_OVERVIEW
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

-- ============================================================
-- MART_AREA_SEASONAL — grain: NEIGHBOURHOOD x MONTH (1-12).
-- Area-COMPARISON screen: seasonal popularity/occupancy trend for the
-- up-to-3 boroughs a user pins. Reads with WHERE NEIGHBOURHOOD IN (...).
--
-- METRIC: OCCUPANCY_RATE = BOOKED_NIGHTS / TOTAL_NIGHTS per (area, month),
-- where a booked night is AVAILABLE = FALSE in the calendar. This is the
-- honest seasonal signal for the trend chart.
--
-- NO REVENUE COLUMN — deliberately. The calendar carries no nightly price
-- (SILVER.CALENDAR_CLEANED price/adjusted_price are all-NULL in this scrape),
-- so any monthly revenue would be BOOKED_NIGHTS x a *static* scrape-time ADR
-- and its seasonal shape would just mirror OCCUPANCY_RATE, adding no signal.
-- Revenue is surfaced as an ANNUAL figure in MART_AREA_STRATEGY instead.
--
-- MONTH grain collapses the year: the scrape window (~Sep 2025 -> Sep 2026)
-- spans 13 months, so the boundary month is observed across two partial
-- years. Acceptable for a seasonality curve; not a same-year comparison.
-- OCCUPANCY is derived from FORWARD-LOOKING availability at scrape time.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_SEASONAL
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready seasonal occupancy trend per neighbourhood x month (1-12): booked/total nights and occupancy rate from calendar availability. Occupancy-only by design (no monthly price exists); revenue lives in MART_AREA_STRATEGY.'
AS
SELECT
    d.NEIGHBOURHOOD,
    n.CITY,
    MONTH(c.CALENDAR_DATE)                                                       AS MONTH,
    COUNT(DISTINCT c.LISTING_ID)                                                 AS LISTING_COUNT,
    COUNT(*)                                                                     AS TOTAL_NIGHTS,
    COUNT(CASE WHEN c.AVAILABLE = FALSE THEN 1 END)                              AS BOOKED_NIGHTS,
    ROUND(COUNT(CASE WHEN c.AVAILABLE = FALSE THEN 1 END) / NULLIF(COUNT(*), 0), 4) AS OCCUPANCY_RATE
FROM GOLD.FCT_CALENDAR_DAILY c
JOIN GOLD.DIM_LISTING d
    ON c.LISTING_ID = d.LISTING_ID
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON d.NEIGHBOURHOOD = n.NEIGHBOURHOOD
GROUP BY d.NEIGHBOURHOOD, n.CITY, MONTH(c.CALENDAR_DATE);

-- ============================================================
-- MART_AREA_STRATEGY — grain: NEIGHBOURHOOD x STRUCTURE_CLASS.
-- Area-COMPARISON screen: short-term (Airbnb) vs long-term (traditional
-- let) investment comparison — the ST-vs-LT grouped bar chart + the basis
-- for the AI-generated ST-vs-LT text (which is produced downstream).
--
-- Both strategies are normalised to GROSS RENTAL YIELD against the Land
-- Registry median purchase price so they sit on one comparable axis:
--     gross yield % = annual rental income / purchase price
--
-- PURCHASE PRICE is normalised PER AREA x STRUCTURE_CLASS (not a blunt
-- area-wide median), matching the house pattern used by MART_LISTING_-
-- CANDIDATES / MART_PROPERTY_GROUP. HM Land Registry PROPERTY_TYPE_CODE is
-- collapsed to the grain the Airbnb side can actually match:
--     F           -> Flat
--     D, S, T     -> House   (Detached / Semi-detached / Terraced)
--     O           -> Other   (commercial / land / non-standard sales)
-- Airbnb listings expose STRUCTURE_CLASS = Flat / House / NULL (hotel,
-- boat, tiny home, ...); NULL is bucketed as 'Other' via COALESCE.
--
-- YIELD_COMPARABLE: TRUE only for Flat / House, where BOTH the Airbnb
-- revenue and the LR price describe the same kind of home. For 'Other'
-- the two sides are unlike (LR 'O' = commercial/land vs Airbnb hotel/boat),
-- so the price is carried as CONTEXT only and every yield column is NULL.
--
--   SHORT-TERM (ST): income = median Airbnb ANNUAL_REVENUE for the
--     (area, structure) segment (scraper estimate, ESTIMATED_REVENUE_L365D).
--
--   LONG-TERM (LT): NO rent dataset is ingested (Land Registry is SALES
--     only). LT annual rent is therefore MODELLED as
--         purchase_price x ASSUMED_LT_GROSS_YIELD_PCT
--     using a per-city assumed gross yield constant. These are documented,
--     configurable ASSUMPTIONS (not observed rents) — approximate market
--     buy-to-let gross yields, city-level:
--         London              4.5%   (high prices -> low yields)
--         Greater Manchester  6.0%   (strong rental yields)
--         Bristol             5.0%
--     Source basis: published UK buy-to-let gross-yield reporting (e.g.
--     Zoopla Rental Market Report / Paragon regional yields). Update the
--     VALUES list when refreshing. Upgrade path: ingest ONS Private Rental
--     Market Statistics for observed rents and replace the assumption.
--
-- CAVEATS (document in the app): ST income = scrape estimates; LT income =
-- assumption; BOTH are GROSS (before mortgage, management, voids, and any
-- short-let regulation). Directional comparison, not a full return model.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_STRATEGY
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST (Airbnb) vs LT (let) yield comparison per neighbourhood x structure_class (Flat/House/Other). Purchase price normalised per area x structure; yields only for Flat/House (YIELD_COMPARABLE), Other is price context only. All figures gross.'
AS
WITH area_cost AS (
    -- Median LR sale price per area x structure_class, matched on district
    -- OR town/city so NEIGHBOURHOOD can hit either. F->Flat, D/S/T->House,
    -- O->Other. Same normalisation basis as the other consumer marts.
    SELECT area_name, structure_class, MEDIAN(price) AS median_sale_price
    FROM (
        SELECT UPPER(TRIM(DISTRICT))  AS area_name,
               CASE PROPERTY_TYPE_CODE WHEN 'F' THEN 'Flat' WHEN 'O' THEN 'Other' ELSE 'House' END AS structure_class,
               PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE DISTRICT IS NOT NULL AND PROPERTY_TYPE_CODE IN ('F','D','S','T','O')
        UNION ALL
        SELECT UPPER(TRIM(TOWN_CITY)) AS area_name,
               CASE PROPERTY_TYPE_CODE WHEN 'F' THEN 'Flat' WHEN 'O' THEN 'Other' ELSE 'House' END AS structure_class,
               PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE TOWN_CITY IS NOT NULL AND PROPERTY_TYPE_CODE IN ('F','D','S','T','O')
    ) src
    GROUP BY area_name, structure_class
),
-- Short-term (Airbnb) income per area x structure_class, from the fact.
area_rev AS (
    SELECT
        NEIGHBOURHOOD,
        COALESCE(STRUCTURE_CLASS, 'Other') AS STRUCTURE_CLASS,
        COUNT(*)                           AS LISTING_COUNT,
        MEDIAN(ANNUAL_REVENUE)             AS MEDIAN_ST_ANNUAL_REVENUE
    FROM GOLD.FCT_LISTING_SNAPSHOT
    WHERE ANNUAL_REVENUE IS NOT NULL
    GROUP BY NEIGHBOURHOOD, COALESCE(STRUCTURE_CLASS, 'Other')
),
-- Per-city assumed long-term GROSS rental yield (documented assumption).
lt_yield AS (
    SELECT column1 AS CITY, column2 AS ASSUMED_LT_GROSS_YIELD_PCT
    FROM VALUES
        ('London',             4.5),
        ('Greater Manchester', 6.0),
        ('Bristol',            5.0)
)
SELECT
    ar.NEIGHBOURHOOD,
    n.CITY,
    ar.STRUCTURE_CLASS,
    (ar.STRUCTURE_CLASS IN ('Flat', 'House'))                                    AS YIELD_COMPARABLE,
    ar.LISTING_COUNT,
    c.median_sale_price                                                          AS MEDIAN_SALE_PRICE,
    -- ---- Short-term (Airbnb) ----
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.median_sale_price, 0) * 100, 2) END AS ST_GROSS_YIELD_PCT,
    -- ---- Long-term (modelled; NULL for non-comparable 'Other') ----
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS ASSUMED_LT_GROSS_YIELD_PCT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(c.median_sale_price * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0) END           AS LT_ANNUAL_RENT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS LT_GROSS_YIELD_PCT
FROM area_rev ar
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON ar.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN area_cost c
    ON UPPER(TRIM(ar.NEIGHBOURHOOD)) = c.area_name
   AND ar.STRUCTURE_CLASS = c.structure_class
LEFT JOIN lt_yield y
    ON n.CITY = y.CITY;


-- ============================================================
-- MART_AREA_STRATEGY_BEDROOMS — grain: NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET.
-- Like-for-like refinement of MART_AREA_STRATEGY. Segmenting Airbnb
-- income by property size removes the median-depression caused by the
-- large tail of barely-booked listings, so a 2-bed is compared with a
-- 2-bed. Feeds a bedroom-faceted ST-vs-LT grouped bar chart.
--
-- STRUCTURE_CLASS: Flat / House / Other (see MART_AREA_STRATEGY header for
-- the F/D/S/T/O -> Flat/House/Other mapping and the YIELD_COMPARABLE rule).
-- BEDROOM_BUCKET: Studio(0) / 1 / 2 / 3 / 4 / 5+ / Unknown(NULL).
-- BEDROOMS comes from GOLD.DIM_LISTING (already carried up from silver);
-- revenue stays sourced from the FCT_LISTING_SNAPSHOT investment fact.
--
-- PRICE GRANULARITY: purchase price is normalised per AREA x STRUCTURE_CLASS
-- (as in MART_AREA_STRATEGY). It is therefore SHARED across bedroom buckets
-- within a structure — HM Land Registry has property type but NO bedroom
-- count, so a bedroom-specific price is impossible. This is far tighter than
-- a single area-wide price: a 3-bed House yield uses the House price, not a
-- flat-dominated area blend. ST_ANNUAL_REVENUE remains bedroom-specific.
-- YIELD_COMPARABLE is FALSE for 'Other' (yield columns NULL there).
-- All figures GROSS (see MART_AREA_STRATEGY caveats).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_STRATEGY_BEDROOMS
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST-vs-LT yield comparison per neighbourhood x structure_class x bedroom bucket. ST annual revenue is bedroom-specific; purchase price is per area x structure (shared across bedroom buckets); yields only for Flat/House. All figures gross.'
AS
WITH area_cost AS (
    -- Median LR sale price per area x structure_class. F->Flat, D/S/T->House,
    -- O->Other. Matched on district OR town/city.
    SELECT area_name, structure_class, MEDIAN(price) AS median_sale_price
    FROM (
        SELECT UPPER(TRIM(DISTRICT))  AS area_name,
               CASE PROPERTY_TYPE_CODE WHEN 'F' THEN 'Flat' WHEN 'O' THEN 'Other' ELSE 'House' END AS structure_class,
               PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE DISTRICT IS NOT NULL AND PROPERTY_TYPE_CODE IN ('F','D','S','T','O')
        UNION ALL
        SELECT UPPER(TRIM(TOWN_CITY)) AS area_name,
               CASE PROPERTY_TYPE_CODE WHEN 'F' THEN 'Flat' WHEN 'O' THEN 'Other' ELSE 'House' END AS structure_class,
               PRICE
        FROM SILVER.PRICE_PAID_CLEANED WHERE TOWN_CITY IS NOT NULL AND PROPERTY_TYPE_CODE IN ('F','D','S','T','O')
    ) src
    GROUP BY area_name, structure_class
),
-- Short-term (Airbnb) income per area x structure_class x bedroom bucket.
seg_rev AS (
    SELECT
        f.NEIGHBOURHOOD,
        COALESCE(f.STRUCTURE_CLASS, 'Other')                    AS STRUCTURE_CLASS,
        CASE
            WHEN d.BEDROOMS IS NULL THEN 'Unknown'
            WHEN d.BEDROOMS = 0      THEN 'Studio'
            WHEN d.BEDROOMS >= 5     THEN '5+'
            ELSE d.BEDROOMS::STRING
        END                                                     AS BEDROOM_BUCKET,
        CASE
            WHEN d.BEDROOMS IS NULL THEN 99             -- Unknown sorts last
            ELSE LEAST(d.BEDROOMS, 5)
        END                                                     AS BEDROOM_SORT,
        COUNT(*)                    AS LISTING_COUNT,
        MEDIAN(f.ANNUAL_REVENUE)    AS MEDIAN_ST_ANNUAL_REVENUE
    FROM GOLD.FCT_LISTING_SNAPSHOT f
    JOIN GOLD.DIM_LISTING d
        ON f.LISTING_ID = d.LISTING_ID
    WHERE f.ANNUAL_REVENUE IS NOT NULL
    GROUP BY f.NEIGHBOURHOOD, COALESCE(f.STRUCTURE_CLASS, 'Other'), BEDROOM_BUCKET, BEDROOM_SORT
),
lt_yield AS (
    SELECT column1 AS CITY, column2 AS ASSUMED_LT_GROSS_YIELD_PCT
    FROM VALUES
        ('London',             4.5),
        ('Greater Manchester', 6.0),
        ('Bristol',            5.0)
)
SELECT
    sr.NEIGHBOURHOOD,
    n.CITY,
    sr.STRUCTURE_CLASS,
    (sr.STRUCTURE_CLASS IN ('Flat', 'House'))                                    AS YIELD_COMPARABLE,
    sr.BEDROOM_BUCKET,
    sr.BEDROOM_SORT,
    sr.LISTING_COUNT,
    c.median_sale_price                                                          AS MEDIAN_SALE_PRICE,
    -- ---- Short-term (Airbnb), bedroom-specific ----
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.median_sale_price, 0) * 100, 2) END AS ST_GROSS_YIELD_PCT,
    -- ---- Long-term (area x structure assumption; NULL for 'Other') ----
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS ASSUMED_LT_GROSS_YIELD_PCT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(c.median_sale_price * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0) END           AS LT_ANNUAL_RENT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS LT_GROSS_YIELD_PCT
FROM seg_rev sr
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON sr.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN area_cost c
    ON UPPER(TRIM(sr.NEIGHBOURHOOD)) = c.area_name
   AND sr.STRUCTURE_CLASS = c.structure_class
LEFT JOIN lt_yield y
    ON n.CITY = y.CITY;

