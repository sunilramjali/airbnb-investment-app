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
-- COST BENCHMARK: Land Registry median sale PRICE now comes from the
-- shared GOLD.FCT_AREA_SALE_PRICE fact (grain NEIGHBOURHOOD x
-- STRUCTURE_CLASS: Flat/House/Other/All). That fact places postcode-based
-- Price Paid sales into neighbourhoods via the SILVER.POSTCODE_NEIGHBOURHOOD_MAP
-- spatial bridge (99.95% coverage, quality_flag='ok'). Marts join it directly
-- on NEIGHBOURHOOD (+ STRUCTURE_CLASS), replacing the old fragile
-- DISTRICT/TOWN_CITY name-match + inline per-mart aggregation.
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
    c.MEDIAN_SALE_PRICE AS AREA_MEDIAN_SALE_PRICE,
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
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = d.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = d.STRUCTURE_CLASS;

-- ============================================================
-- MART_AREA_OVERVIEW — grain: one row per NEIGHBOURHOOD.
-- Area Overview screen: KPIs + GEOGRAPHY boundary for the map.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_OVERVIEW
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready per-neighbourhood summary: CITY, listing counts, revenue/occupancy aggregates, median sale price, in-area POI counts, and boundary GEOGRAPHY for mapping.'
AS
WITH listing_agg AS (
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
    c.MEDIAN_SALE_PRICE AS MEDIAN_SALE_PRICE,
    COALESCE(ap.POI_COUNT, 0)       AS POI_COUNT,
    COALESCE(ap.TRANSPORT_COUNT, 0) AS TRANSPORT_COUNT,
    COALESCE(ap.DINING_COUNT, 0)    AS DINING_COUNT,
    ROUND(COALESCE(ap.POI_COUNT, 0) / NULLIF(n.AREA_SQKM, 0), 2) AS POI_DENSITY_SQKM,
    n.AREA_SQKM,
    n.BOUNDARY
FROM listing_agg la
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON la.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = la.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = 'All'
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
WITH
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
    c.MEDIAN_SALE_PRICE             AS MEDIAN_SALE_PRICE,
    c.SALE_TXN_COUNT                    AS SALE_TXN_COUNT
FROM scaffold s
LEFT JOIN local_agg la
    ON s.NEIGHBOURHOOD = la.NEIGHBOURHOOD
   AND s.PROPERTY_GROUP = la.PROPERTY_GROUP
LEFT JOIN city_agg ca
    ON s.CITY = ca.CITY
   AND s.PROPERTY_GROUP = ca.PROPERTY_GROUP
LEFT JOIN all_agg aa
    ON s.PROPERTY_GROUP = aa.PROPERTY_GROUP
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD = s.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = CASE
           WHEN s.PROPERTY_GROUP = 'Apartment / Flat' THEN 'Flat'
           WHEN s.PROPERTY_GROUP = 'House'            THEN 'House'
       END;

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
WITH
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
    c.MEDIAN_SALE_PRICE                                                          AS MEDIAN_SALE_PRICE,
    -- ---- Short-term (Airbnb) ----
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END AS ST_GROSS_YIELD_PCT,
    -- ---- Long-term: OBSERVED ONS rent where available, else modelled assumption ----
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS ASSUMED_LT_GROSS_YIELD_PCT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN COALESCE(rr.ANNUAL_RENT,
                       ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0)) END  AS LT_ANNUAL_RENT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(COALESCE(rr.ANNUAL_RENT,
                             c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
                    / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END                              AS LT_GROSS_YIELD_PCT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN CASE WHEN rr.ANNUAL_RENT IS NOT NULL THEN 'observed' ELSE 'assumed' END END       AS LT_RENT_SOURCE
FROM area_rev ar
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON ar.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = ar.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = ar.STRUCTURE_CLASS
LEFT JOIN GOLD.FCT_AREA_RENT rr
    ON rr.NEIGHBOURHOOD = ar.NEIGHBOURHOOD
   AND rr.CATEGORY_TYPE = 'structure'
   AND rr.RENT_CATEGORY = ar.STRUCTURE_CLASS
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
WITH
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
    c.MEDIAN_SALE_PRICE                                                          AS MEDIAN_SALE_PRICE,
    -- ---- Short-term (Airbnb), bedroom-specific ----
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END AS ST_GROSS_YIELD_PCT,
    -- ---- Long-term: OBSERVED ONS bedroom-specific rent where available, else modelled ----
    --   ONS bedroom rent is independent of structure_class (ONS does not cross
    --   bedroom x property type), so the same bedroom rent applies to Flat/House
    --   rows; the yield still differs via the structure-specific sale price.
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS ASSUMED_LT_GROSS_YIELD_PCT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN COALESCE(rr.ANNUAL_RENT,
                       ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0)) END  AS LT_ANNUAL_RENT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(COALESCE(rr.ANNUAL_RENT,
                             c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
                    / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END                              AS LT_GROSS_YIELD_PCT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN CASE WHEN rr.ANNUAL_RENT IS NOT NULL THEN 'observed' ELSE 'assumed' END END       AS LT_RENT_SOURCE
FROM seg_rev sr
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON sr.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = sr.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = sr.STRUCTURE_CLASS
LEFT JOIN GOLD.FCT_AREA_RENT rr
    ON rr.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
   AND rr.CATEGORY_TYPE = 'bedroom'
   AND rr.RENT_CATEGORY = CASE sr.BEDROOM_BUCKET
                              WHEN '1' THEN '1' WHEN '2' THEN '2' WHEN '3' THEN '3'
                              WHEN '4' THEN '4+' WHEN '5+' THEN '4+' END   -- Studio/Unknown -> no match -> assumption
LEFT JOIN lt_yield y
    ON n.CITY = y.CITY;

-- ============================================================
-- MART_AREA_AMENITIES — grain: NEIGHBOURHOOD x AMENITY_GROUP.
-- Area-COMPARISON screen: how well-equipped an area's listings are, by
-- amenity group. PCT_LISTINGS_WITH_GROUP = share of the area's listings
-- offering AT LEAST ONE amenity in that group. Long form (one row per
-- area x group) so the app can facet / grouped-bar the 3 pinned boroughs
-- across the ~13 curated groups. Filter with WHERE NEIGHBOURHOOD IN (...).
--
-- Source: SILVER.LISTING_AMENITIES (exploded listing x amenity, already
-- classified into AMENITY_GROUP) joined to GOLD.DIM_LISTING for the
-- listing's NEIGHBOURHOOD / CITY. AREA_LISTINGS is the denominator: the
-- count of DISTINCT listings in the area that have any amenities at all
-- (i.e. appear in LISTING_AMENITIES), so PCT is a clean 0..1 share.
--
-- This is DELIBERATELY decoupled from the persona investment scores and
-- AI narratives — it adds amenity insight without invalidating either.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_AMENITIES
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready amenity-group coverage per neighbourhood x amenity_group: listings offering >=1 amenity in the group, area listing base, and the coverage percentage. Long form for faceted area comparison.'
AS
WITH area_base AS (
    -- Denominator: distinct listings per area that have any amenities.
    SELECT
        d.NEIGHBOURHOOD,
        COUNT(DISTINCT la.LISTING_ID) AS AREA_LISTINGS
    FROM SILVER.LISTING_AMENITIES la
    JOIN GOLD.DIM_LISTING d
        ON la.LISTING_ID = d.LISTING_ID
    GROUP BY d.NEIGHBOURHOOD
),
group_cov AS (
    -- Numerator: distinct listings per area offering >=1 amenity in each group.
    SELECT
        d.NEIGHBOURHOOD,
        n.CITY,
        la.AMENITY_GROUP,
        COUNT(DISTINCT la.LISTING_ID) AS LISTINGS_WITH_GROUP
    FROM SILVER.LISTING_AMENITIES la
    JOIN GOLD.DIM_LISTING d
        ON la.LISTING_ID = d.LISTING_ID
    LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON d.NEIGHBOURHOOD = n.NEIGHBOURHOOD
    GROUP BY d.NEIGHBOURHOOD, n.CITY, la.AMENITY_GROUP
)
SELECT
    g.NEIGHBOURHOOD,
    g.CITY,
    g.AMENITY_GROUP,
    g.LISTINGS_WITH_GROUP,
    b.AREA_LISTINGS,
    ROUND(g.LISTINGS_WITH_GROUP / NULLIF(b.AREA_LISTINGS, 0), 4) AS PCT_LISTINGS_WITH_GROUP
FROM group_cov g
JOIN area_base b
    ON g.NEIGHBOURHOOD = b.NEIGHBOURHOOD;

-- ============================================================
-- MART_AREA_AMENITY_GAP — grain: NEIGHBOURHOOD x AMENITY_GROUP.
-- Area-COMPARISON / fit-out signal: within an area, how much more likely
-- are the TOP-earning listings to offer each amenity group than the rest?
-- GAP = PCT_TOP - PCT_REST. A big positive GAP flags an amenity group that
-- distinguishes local winners — a candidate "add this to compete here".
--
-- Population: ACTIVE listings only (ANNUAL_REVENUE > 0) that also appear in
-- SILVER.LISTING_AMENITIES, so the coverage % is well-defined and the
-- dormant-listing tail (revenue 0, few amenities) doesn't distort the split.
-- Segment: NTILE(4) by ANNUAL_REVENUE DESC within the area -> quartile 1 is
-- 'top', quartiles 2-4 are 'rest'.
--
-- CAVEAT (document in the app): ASSOCIATIONAL, NOT CAUSAL. Top earners tend
-- to list more amenities partly because they are professionally managed, so
-- a gap is a strong HINT of what to add, not a guaranteed revenue uplift.
-- SUFFICIENT_SAMPLE flags areas too small for the quartile split to be
-- trustworthy (top quartile < 5 or rest < 15 active listings).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_AMENITY_GAP
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready amenity fit-out signal per neighbourhood x amenity_group: coverage among top-revenue-quartile listings vs the rest, and the gap. Active listings only; associational not causal. SUFFICIENT_SAMPLE guards small areas.'
AS
WITH seg AS (
    -- Active listings with amenities, segmented into top revenue quartile vs rest, per area.
    SELECT
        f.LISTING_ID,
        f.NEIGHBOURHOOD,
        CASE WHEN NTILE(4) OVER (PARTITION BY f.NEIGHBOURHOOD ORDER BY f.ANNUAL_REVENUE DESC) = 1
             THEN 'top' ELSE 'rest' END AS segment
    FROM GOLD.FCT_LISTING_SNAPSHOT f
    WHERE f.ANNUAL_REVENUE > 0
      AND EXISTS (SELECT 1 FROM SILVER.LISTING_AMENITIES la WHERE la.LISTING_ID = f.LISTING_ID)
),
seg_size AS (
    SELECT
        NEIGHBOURHOOD,
        COUNT(DISTINCT CASE WHEN segment = 'top'  THEN LISTING_ID END) AS TOP_N,
        COUNT(DISTINCT CASE WHEN segment = 'rest' THEN LISTING_ID END) AS REST_N
    FROM seg
    GROUP BY NEIGHBOURHOOD
),
listing_group AS (
    -- One row per (area, segment, listing, group) the listing offers.
    SELECT DISTINCT s.NEIGHBOURHOOD, s.segment, s.LISTING_ID, la.AMENITY_GROUP
    FROM seg s
    JOIN SILVER.LISTING_AMENITIES la
        ON s.LISTING_ID = la.LISTING_ID
),
grp AS (
    SELECT
        NEIGHBOURHOOD,
        AMENITY_GROUP,
        COUNT(DISTINCT CASE WHEN segment = 'top'  THEN LISTING_ID END) AS TOP_WITH,
        COUNT(DISTINCT CASE WHEN segment = 'rest' THEN LISTING_ID END) AS REST_WITH
    FROM listing_group
    GROUP BY NEIGHBOURHOOD, AMENITY_GROUP
)
SELECT
    g.NEIGHBOURHOOD,
    n.CITY,
    g.AMENITY_GROUP,
    ss.TOP_N,
    ss.REST_N,
    ROUND(g.TOP_WITH  / NULLIF(ss.TOP_N, 0),  4)                                      AS PCT_TOP,
    ROUND(g.REST_WITH / NULLIF(ss.REST_N, 0), 4)                                      AS PCT_REST,
    ROUND(g.TOP_WITH / NULLIF(ss.TOP_N, 0) - g.REST_WITH / NULLIF(ss.REST_N, 0), 4)   AS GAP,
    (ss.TOP_N + ss.REST_N)                                                            AS AREA_ACTIVE_LISTINGS,
    (ss.TOP_N >= 5 AND ss.REST_N >= 15)                                               AS SUFFICIENT_SAMPLE
FROM grp g
JOIN seg_size ss
    ON g.NEIGHBOURHOOD = ss.NEIGHBOURHOOD
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON g.NEIGHBOURHOOD = n.NEIGHBOURHOOD;

-- ============================================================
-- COLUMN COMMENTS
-- ------------------------------------------------------------
-- Per-column documentation for the app marts, kept as COMMENT ON COLUMN
-- (rather than inline column lists) so they can be maintained without
-- re-running the mart bodies. Re-applied on every run AFTER the CREATE OR
-- REPLACE statements above, so they persist across rebuilds. Column names
-- must match the mart projections above.
-- ============================================================

-- ---- MART_LISTING_CANDIDATES ----
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LISTING_ID IS 'Airbnb listing id; row grain (unique per listing).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.HOST_ID IS 'Airbnb host id that owns the listing.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.NAME IS 'Listing title.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.NEIGHBOURHOOD IS 'Area name; the app area grain.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LATITUDE IS 'Listing latitude (WGS84).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LONGITUDE IS 'Listing longitude (WGS84).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.GEO_POINT IS 'Geospatial point for map plotting and spatial joins.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ROOM_TYPE IS 'Airbnb room type (Entire home, Private room, etc.).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.PROPERTY_TYPE IS 'Raw Airbnb property type text.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.STRUCTURE_CLASS IS 'Flat or House (NULL for hotel/boat/etc.); used for sale-price yield match.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.PROPERTY_GROUP IS 'Higher-level property grouping for the selection UI.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ACCOMMODATES IS 'Maximum guests the listing sleeps.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.BEDROOMS IS 'Number of bedrooms (NULL if unknown).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.BEDS IS 'Number of beds.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.BATHROOMS IS 'Number of bathrooms (may be fractional).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ADR IS 'Average daily rate = nightly price at scrape time.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.OCCUPANCY_RATE IS 'Estimated occupancy (0..1) = estimated booked nights / 365.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ANNUAL_REVENUE IS 'Estimated trailing-12-month revenue (scraper estimate).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.REVPAR IS 'Revenue per available night = ANNUAL_REVENUE / 365.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.HAS_REVENUE_DATA IS 'TRUE if ANNUAL_REVENUE is populated.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.AREA_MEDIAN_SALE_PRICE IS 'Land Registry median sale price for the area x structure (purchase-cost benchmark).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.REVIEW_SCORES_RATING IS 'Overall guest review rating.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.NUMBER_OF_REVIEWS IS 'Total review count.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.HOST_IS_SUPERHOST IS 'Whether the host holds Superhost status.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.POI_COUNT_500M IS 'Count of points of interest within 500m.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.TRANSPORT_COUNT_500M IS 'Transport POIs within 500m.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.DINING_COUNT_500M IS 'Dining POIs within 500m.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.INSTANT_BOOKABLE IS 'Whether the listing allows instant booking.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LISTING_URL IS 'Airbnb listing URL.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.PICTURE_URL IS 'Listing cover photo URL.';

-- ---- MART_AREA_OVERVIEW ----
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.NEIGHBOURHOOD IS 'Area name; row grain.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.CITY IS 'City the neighbourhood belongs to (London / Greater Manchester / Bristol).';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.LISTING_COUNT IS 'Number of listings in the area.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_ADR IS 'Mean nightly rate across the area listings.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.MEDIAN_ADR IS 'Median nightly rate.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_OCCUPANCY_RATE IS 'Mean estimated occupancy (0..1).';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_ANNUAL_REVENUE IS 'Mean estimated annual revenue.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.MEDIAN_ANNUAL_REVENUE IS 'Median estimated annual revenue.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_BEDROOMS IS 'Mean bedrooms per listing.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_RATING IS 'Mean guest review rating.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.MEDIAN_SALE_PRICE IS 'Land Registry median sale price for the area (purchase benchmark).';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.POI_COUNT IS 'POIs inside the neighbourhood boundary.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.TRANSPORT_COUNT IS 'Transport POIs inside the boundary.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.DINING_COUNT IS 'Dining POIs inside the boundary.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.POI_DENSITY_SQKM IS 'POIs per square km.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AREA_SQKM IS 'Neighbourhood area in square km.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.BOUNDARY IS 'Neighbourhood boundary polygon (GEOGRAPHY) for mapping.';

-- ---- MART_PROPERTY_GROUP ----
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.PROPERTY_GROUP IS 'Property group; grain with neighbourhood and the selection key.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.LISTING_COUNT IS 'Local listings in this area x group (0 if none).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.HAS_LOCAL_DATA IS 'TRUE if the area x group has at least one listing.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_ADR IS 'Local mean nightly rate for the group.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.MEDIAN_ADR IS 'Local median nightly rate.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_OCCUPANCY_RATE IS 'Local mean occupancy (0..1).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_ANNUAL_REVENUE IS 'Local mean annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.MEDIAN_ANNUAL_REVENUE IS 'Local median annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_BEDROOMS IS 'Local mean bedrooms.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_RATING IS 'Local mean rating.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_LISTING_COUNT IS 'Listings behind the city x group benchmark.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_AVG_ADR IS 'City x group mean nightly rate (fallback benchmark).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_AVG_OCCUPANCY_RATE IS 'City x group mean occupancy.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_AVG_ANNUAL_REVENUE IS 'City x group mean annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_LISTING_COUNT IS 'Listings behind the all-areas group benchmark.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_AVG_ADR IS 'All-areas group mean nightly rate.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_AVG_OCCUPANCY_RATE IS 'All-areas group mean occupancy.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_AVG_ANNUAL_REVENUE IS 'All-areas group mean annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.MEDIAN_SALE_PRICE IS 'Land Registry median sale price where the group maps to Flat/House (else NULL).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.SALE_TXN_COUNT IS 'Number of sale transactions behind MEDIAN_SALE_PRICE.';

-- ---- MART_AREA_POI ----
COMMENT ON COLUMN GOLD.MART_AREA_POI.NEIGHBOURHOOD IS 'Area the POI falls within.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.POI_NAME IS 'Point-of-interest name.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.CATEGORY IS 'POI category (raw).';
COMMENT ON COLUMN GOLD.MART_AREA_POI.AMENITY_GROUP IS 'Curated POI amenity group.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.IS_TRANSPORT IS 'TRUE if the POI is a transport category.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.IS_DINING IS 'TRUE if the POI is a dining amenity.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.LATITUDE IS 'POI latitude for map plotting.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.LONGITUDE IS 'POI longitude for map plotting.';

-- ---- MART_AREA_SEASONAL ----
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.MONTH IS 'Calendar month 1-12 (year collapsed for seasonality).';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.LISTING_COUNT IS 'Distinct listings contributing in the month.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.TOTAL_NIGHTS IS 'Listing-nights observed in the month.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.BOOKED_NIGHTS IS 'Nights not available (proxy for booked).';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.OCCUPANCY_RATE IS 'BOOKED_NIGHTS / TOTAL_NIGHTS (0..1); the seasonal signal.';

-- ---- MART_AREA_STRATEGY ----
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.STRUCTURE_CLASS IS 'Flat / House / Other property-type bucket.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.YIELD_COMPARABLE IS 'TRUE for Flat/House where ST vs LT yields are like-for-like; FALSE for Other.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LISTING_COUNT IS 'Active listings in the area x structure.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.MEDIAN_SALE_PRICE IS 'Land Registry median purchase price for the area x structure.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.ST_ANNUAL_REVENUE IS 'Median short-term (Airbnb) annual revenue.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.ST_GROSS_YIELD_PCT IS 'Short-term gross yield percent = ST revenue / sale price (NULL for Other).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LT_ANNUAL_RENT IS 'Long-term annual rent: observed ONS PIPR rent x 12 where available, else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LT_GROSS_YIELD_PCT IS 'Long-term gross yield percent = LT_ANNUAL_RENT / median sale price (NULL for Other). Real when LT_RENT_SOURCE=observed.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LT_RENT_SOURCE IS 'observed = real ONS PIPR rent; assumed = modelled fallback (no ONS coverage, e.g. City of London). NULL for Other.';

-- ---- MART_AREA_STRATEGY_BEDROOMS ----
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.STRUCTURE_CLASS IS 'Flat / House / Other property-type bucket.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.YIELD_COMPARABLE IS 'TRUE for Flat/House where yields are like-for-like; FALSE for Other.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.BEDROOM_BUCKET IS 'Bedroom bucket: Studio / 1 / 2 / 3 / 4 / 5+ / Unknown.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.BEDROOM_SORT IS 'Sort key for BEDROOM_BUCKET (Unknown sorts last).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LISTING_COUNT IS 'Active listings in the area x structure x bedroom bucket.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.MEDIAN_SALE_PRICE IS 'Area x structure median purchase price (shared across bedroom buckets).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.ST_ANNUAL_REVENUE IS 'Median short-term annual revenue for the bucket (bedroom-specific).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.ST_GROSS_YIELD_PCT IS 'Short-term gross yield percent (NULL for Other).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LT_ANNUAL_RENT IS 'Long-term annual rent: observed ONS PIPR bedroom-specific rent x 12 where available, else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LT_GROSS_YIELD_PCT IS 'Long-term gross yield percent = LT_ANNUAL_RENT / median sale price (NULL for Other). Real when LT_RENT_SOURCE=observed.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LT_RENT_SOURCE IS 'observed = real ONS PIPR bedroom rent (independent of structure_class); assumed = modelled fallback (Studio/Unknown/no ONS coverage). NULL for Other.';

-- ---- MART_AREA_AMENITIES ----
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.AMENITY_GROUP IS 'Curated amenity group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.LISTINGS_WITH_GROUP IS 'Listings offering at least one amenity in the group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.AREA_LISTINGS IS 'Area listings that have any amenities (the denominator).';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.PCT_LISTINGS_WITH_GROUP IS 'Share (0..1) of the area listings offering >=1 amenity in this group.';

-- ---- MART_AREA_AMENITY_GAP ----
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.AMENITY_GROUP IS 'Curated amenity group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.TOP_N IS 'Active listings in the top revenue quartile.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.REST_N IS 'Active listings in revenue quartiles 2-4.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.PCT_TOP IS 'Share (0..1) of top-quartile listings offering the group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.PCT_REST IS 'Share (0..1) of the rest offering the group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.GAP IS 'PCT_TOP minus PCT_REST; positive = winners over-index on this group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.AREA_ACTIVE_LISTINGS IS 'Total active listings (TOP_N + REST_N).';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.SUFFICIENT_SAMPLE IS 'TRUE if TOP_N >= 5 AND REST_N >= 15 (quartile split trustworthy).';
