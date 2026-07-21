-- Builds the GOLD facts: FCT_CALENDAR_DAILY (listing x date base), FCT_LISTING_SNAPSHOT (per-listing investment metrics), and FCT_LISTING_POI (per-listing POI proximity).
-- Co-authored with CoCo
-- ============================================================
-- GOLD — FACTS
-- ------------------------------------------------------------
-- Single-schema aggregation layer: the whole star + consumer objects
-- live in GOLD, distinguished by name prefix (DIM_/FCT_/AGG_/MART_/
-- VW_/FEATURE_). The GOLD schema is created by the setup layer
-- (setup/01_setup_database_and_warehouse.sql).
--
-- FCT_CALENDAR_DAILY   : grain listing x date. Lean projection of
--                        SILVER.CALENDAR_CLEANED (39M rows) kept
--                        incremental-friendly (no window fns).
--
-- FCT_LISTING_SNAPSHOT : grain listing. The investment-metrics fact.
--                        v1 uses the scraper's pre-computed
--                        ESTIMATED_OCCUPANCY_L365D / ESTIMATED_REVENUE_L365D
--                        (sidesteps the calendar booked-vs-blocked
--                        ambiguity). ADR = nightly PRICE.
--
-- FCT_LISTING_POI      : grain listing. POI proximity computed
--                        SEPARATELY from the snapshot so the expensive
--                        spatial join doesn't slow snapshot refresh.
--                        Bounded ST_DWITHIN (500m) join DIM_LISTING x DIM_POI.
--
-- Metrics:
--   OCCUPANCY_RATE = ESTIMATED_OCCUPANCY_L365D / 365
--   ANNUAL_REVENUE = ESTIMATED_REVENUE_L365D
--   REVPAR         = ANNUAL_REVENUE / 365
--
-- REFRESH DESIGN: FCT_LISTING_SNAPSHOT and FCT_LISTING_POI use
-- TARGET_LAG = DOWNSTREAM (they feed MART_LISTING, which anchors the
-- lag). FCT_CALENDAR_DAILY keeps an explicit '1 day' lag because no
-- mart consumes it yet — a DOWNSTREAM table with no downstream consumer
-- would never refresh.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ------------------------------------------------------------
-- FCT_CALENDAR_DAILY — daily availability per listing.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_CALENDAR_DAILY
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Daily availability per listing (grain: listing x date). Lean incremental projection of SILVER.CALENDAR_CLEANED.'
AS
SELECT
    LISTING_ID,
    CALENDAR_DATE,
    AVAILABLE,
    MINIMUM_NIGHTS,
    MAXIMUM_NIGHTS
FROM SILVER.CALENDAR_CLEANED;

-- ------------------------------------------------------------
-- FCT_LISTING_SNAPSHOT — per-listing investment metrics.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_LISTING_SNAPSHOT
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Per-listing investment metrics: ADR, occupancy rate, annual revenue, RevPAR. v1 uses scraper estimates.'
AS
SELECT
    LISTING_ID,
    HOST_ID,
    NEIGHBOURHOOD,
    NEIGHBOURHOOD_GROUP,
    ROOM_TYPE,
    STRUCTURE_CLASS,
    PROPERTY_GROUP,
    GEO_POINT,
    PRICE                                              AS ADR,
    ESTIMATED_OCCUPANCY_L365D                          AS OCCUPANCY_NIGHTS,
    ROUND(ESTIMATED_OCCUPANCY_L365D / 365.0, 4)        AS OCCUPANCY_RATE,
    ESTIMATED_REVENUE_L365D                            AS ANNUAL_REVENUE,
    ROUND(ESTIMATED_REVENUE_L365D / 365.0, 2)          AS REVPAR,
    REVIEW_SCORES_RATING,
    NUMBER_OF_REVIEWS
FROM GOLD.DIM_LISTING;

-- ------------------------------------------------------------
-- FCT_LISTING_POI — proximity features (bounded 500m spatial join).
-- Separate from the snapshot to keep that refresh cheap.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_LISTING_POI
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'POI proximity per listing: count of POIs within 500m, overall and for transport. Bounded ST_DWITHIN join.'
AS
SELECT
    l.LISTING_ID,
    COUNT(p.NAME)                                                       AS POI_COUNT_500M,
    COUNT(CASE WHEN p.IS_TRANSPORT THEN 1 END)                          AS TRANSPORT_COUNT_500M,
    COUNT(CASE WHEN p.IS_DINING    THEN 1 END)                          AS DINING_COUNT_500M
FROM GOLD.DIM_LISTING l
LEFT JOIN GOLD.DIM_POI p
    ON ST_DWITHIN(l.GEO_POINT, p.LOCATION, 500)
GROUP BY l.LISTING_ID;

-- ------------------------------------------------------------
-- FCT_AREA_SALE_PRICE — shared Land Registry sale-price fact.
-- Grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat / House / Other / All).
-- Single source of truth for every mart's sale-price benchmark, replacing
-- the per-mart inline area_cost CTEs (fragile DISTRICT/TOWN_CITY name-match).
--
--   STRUCTURE_CLASS:
--     'Flat'  = Land Registry Flat/Maisonette (code F)      [property_class]
--     'House' = Detached / Semi-Detached / Terraced (D/S/T) [property_class]
--     'Other' = code O. 100% of code-O sales are PPD category B (non_standard)
--               and are removed by quality_flag='ok', so this bucket is
--               currently always empty. Kept for forward-compatibility.
--     'All'   = pooled residential F,D,S,T (NOT Other) — the area-level median
--               consumed by MART_AREA_OVERVIEW.
--
-- AREA MAPPING: Price Paid is postcode-based; placed into an Airbnb
--   neighbourhood via SILVER.POSTCODE_NEIGHBOURHOOD_MAP (postcode centroid
--   point-in-polygon; validated 99.95% coverage, 108/108 name match).
-- QUALITY: quality_flag='ok' only (arm's-length market sales in sane bounds).
-- RENT-READY: this grain is where a future long-term rent benchmark
--   (e.g. MEDIAN_ANNUAL_RENT) will be added.
-- FULL refresh (MEDIAN is not incrementally trackable).
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_AREA_SALE_PRICE
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Shared Land Registry sale-price fact. Grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House/Other/All). Price Paid (quality_flag=ok) placed into neighbourhoods via SILVER.POSTCODE_NEIGHBOURHOOD_MAP spatial bridge; STRUCTURE_CLASS from PRICE_PAID_CLEANED.property_class (Other=code O; All=pooled F,D,S,T). Single source for all mart sale-price benchmarks. Rent-ready grain.'
AS
WITH sales AS (
    SELECT
        b.NEIGHBOURHOOD,
        b.CITY,
        p.price,
        p.property_type_code,
        CASE
            WHEN p.property_class IS NOT NULL THEN p.property_class   -- Flat / House
            WHEN p.property_type_code = 'O'   THEN 'Other'
        END AS structure_class
    FROM SILVER.PRICE_PAID_CLEANED p
    JOIN SILVER.POSTCODE_NEIGHBOURHOOD_MAP b
        ON UPPER(REPLACE(p.postcode, ' ', '')) = b.POSTCODE_KEY
    WHERE p.quality_flag = 'ok'
      AND p.postcode IS NOT NULL
)
SELECT
    NEIGHBOURHOOD, CITY, structure_class AS STRUCTURE_CLASS,
    MEDIAN(price)        AS MEDIAN_SALE_PRICE,
    ROUND(AVG(price), 0) AS AVG_SALE_PRICE,
    COUNT(*)             AS SALE_TXN_COUNT
FROM sales
WHERE structure_class IS NOT NULL
GROUP BY NEIGHBOURHOOD, CITY, structure_class
UNION ALL
SELECT
    NEIGHBOURHOOD, CITY, 'All' AS STRUCTURE_CLASS,
    MEDIAN(price)        AS MEDIAN_SALE_PRICE,
    ROUND(AVG(price), 0) AS AVG_SALE_PRICE,
    COUNT(*)             AS SALE_TXN_COUNT
FROM sales
WHERE property_type_code IN ('F', 'D', 'S', 'T')   -- pooled residential (excludes Other)
GROUP BY NEIGHBOURHOOD, CITY;

-- ------------------------------------------------------------
-- FCT_AREA_RENT — observed long-term rent benchmark (ONS PIPR).
-- Grain: NEIGHBOURHOOD x RENT_CATEGORY, with CATEGORY_TYPE:
--   'overall'   -> RENT_CATEGORY 'All'          (ONS "All property types")
--   'structure' -> RENT_CATEGORY 'Flat'/'House' (Flat = Flat/Maisonette;
--                  House = mean of Detached/Semi-detached/Terraced) — matches
--                  FCT_AREA_SALE_PRICE.STRUCTURE_CLASS for the strategy mart.
--   'bedroom'   -> RENT_CATEGORY '1'/'2'/'3'/'4+' (ONS 4+ covers 4 and 5+) —
--                  for the bedrooms mart. NOTE: ONS does NOT cross bedroom x
--                  structure, so bedroom rent is independent of structure_class.
--
-- Source: SILVER.ONS_PRIVATE_RENT_CLEANED (latest published month) placed into
--   Airbnb neighbourhoods via SILVER.NEIGHBOURHOOD_ONS_AREA_MAP. RENT_GRAIN
--   flags resolution: 'exact' (London borough / GM district) vs 'broadcast'
--   (Manchester wards -> Manchester; Bristol wards -> city). This is the
--   OBSERVED replacement for the per-city assumed yield in the strategy marts.
-- FULL refresh (single-period snapshot). TARGET_LAG DOWNSTREAM (mart-anchored).
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_AREA_RENT
    TARGET_LAG = DOWNSTREAM
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Observed ONS private-rent benchmark. Grain: NEIGHBOURHOOD x RENT_CATEGORY (overall/structure/bedroom). Latest ONS month, placed into neighbourhoods via SILVER.NEIGHBOURHOOD_ONS_AREA_MAP (RENT_GRAIN exact/broadcast). House = mean of Detached/Semi/Terraced. Feeds real LT rent into MART_AREA_STRATEGY(_BEDROOMS).'
AS
WITH latest AS (
    SELECT MAX(period) AS period FROM SILVER.ONS_PRIVATE_RENT_CLEANED
),
rent AS (
    SELECT r.area_code, r.period, r.category, r.category_type, r.property_class, r.rental_price
    FROM SILVER.ONS_PRIVATE_RENT_CLEANED r
    JOIN latest l ON r.period = l.period
    WHERE r.rental_price IS NOT NULL
),
joined AS (
    SELECT x.NEIGHBOURHOOD, x.CITY, x.RENT_GRAIN, r.period,
           r.category, r.category_type, r.property_class, r.rental_price
    FROM SILVER.NEIGHBOURHOOD_ONS_AREA_MAP x
    JOIN rent r ON r.area_code = x.ONS_AREA_CODE
    WHERE x.ONS_AREA_CODE IS NOT NULL
)
-- overall
SELECT NEIGHBOURHOOD, CITY, 'All' AS RENT_CATEGORY, 'overall' AS CATEGORY_TYPE,
       ROUND(rental_price, 0)      AS MONTHLY_RENT,
       ROUND(rental_price * 12, 0) AS ANNUAL_RENT,
       period                      AS RENT_PERIOD,
       RENT_GRAIN
FROM joined WHERE category = 'All property types'
UNION ALL
-- structure: Flat
SELECT NEIGHBOURHOOD, CITY, 'Flat', 'structure',
       ROUND(rental_price, 0), ROUND(rental_price * 12, 0), period, RENT_GRAIN
FROM joined WHERE category = 'Flat/Maisonette'
UNION ALL
-- structure: House = mean of Detached / Semi-detached / Terraced
SELECT NEIGHBOURHOOD, CITY, 'House', 'structure',
       ROUND(AVG(rental_price), 0), ROUND(AVG(rental_price) * 12, 0),
       ANY_VALUE(period), ANY_VALUE(RENT_GRAIN)
FROM joined WHERE property_class = 'House'
GROUP BY NEIGHBOURHOOD, CITY
UNION ALL
-- bedroom buckets (ONS 4+ covers buckets 4 and 5+)
SELECT NEIGHBOURHOOD, CITY,
       CASE category WHEN 'One bedroom'           THEN '1'
                     WHEN 'Two bedrooms'          THEN '2'
                     WHEN 'Three bedrooms'        THEN '3'
                     WHEN 'Four or more bedrooms' THEN '4+' END,
       'bedroom',
       ROUND(rental_price, 0), ROUND(rental_price * 12, 0), period, RENT_GRAIN
FROM joined WHERE category_type = 'bedroom';
