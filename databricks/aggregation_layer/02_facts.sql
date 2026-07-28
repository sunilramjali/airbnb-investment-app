-- Builds the GOLD facts: FCT_CALENDAR_DAILY (listing x date base), FCT_LISTING_SNAPSHOT (per-listing investment metrics), FCT_LISTING_POI (per-listing POI proximity), FCT_AREA_SALE_PRICE, FCT_AREA_RENT.
-- Databricks port of etl/aggregation_layer/02_facts.sql.
-- ============================================================
-- GOLD — FACTS
-- ------------------------------------------------------------
-- FCT_CALENDAR_DAILY   : grain listing x date. Lean projection of
--                        SILVER.CALENDAR_CLEANED (37.5M rows).
-- FCT_LISTING_SNAPSHOT : grain listing. The investment-metrics fact. v1 uses
--                        the scraper's pre-computed ESTIMATED_* columns
--                        (sidesteps the calendar booked-vs-blocked ambiguity).
-- FCT_LISTING_POI      : grain listing. POI proximity, computed SEPARATELY
--                        from the snapshot so the spatial join doesn't slow
--                        snapshot rebuilds. Bounded 500m join.
-- FCT_AREA_SALE_PRICE  : grain neighbourhood x structure_class.
-- FCT_AREA_RENT        : grain neighbourhood x rent_category.
--
-- Metrics: OCCUPANCY_RATE = ESTIMATED_OCCUPANCY_L365D / 365
--          ANNUAL_REVENUE = ESTIMATED_REVENUE_L365D
--          REVPAR         = ANNUAL_REVENUE / 365
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE
-- ------------------------------------------------------------
--   CREATE OR REPLACE DYNAMIC TABLE -> CREATE OR REPLACE TABLE (see 01_dimensions.sql
--       for the full rationale: materialized views work on Free Edition but cost
--       5m39s each vs 4.6s for a CTAS, ~110 min per Gold build).
--   TARGET_LAG / WAREHOUSE          -> dropped, no serverless analogue.
--   COMMENT = '...'                 -> COMMENT '...'
--
-- ✅ Verified to port verbatim: MEDIAN (matches Snowflake's interpolated
--    median), ANY_VALUE, COUNT(CASE WHEN ...), UNION ALL, COMMENT ON COLUMN.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA GOLD;

-- ------------------------------------------------------------
-- FCT_CALENDAR_DAILY — daily availability per listing.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.FCT_CALENDAR_DAILY
    COMMENT 'Daily availability per listing (grain: listing x date). Lean projection of SILVER.CALENDAR_CLEANED.'
AS
SELECT
    LISTING_ID,
    CALENDAR_DATE,
    AVAILABLE,
    MINIMUM_NIGHTS,
    MAXIMUM_NIGHTS
FROM AIRBNB_INVESTMENT.SILVER.CALENDAR_CLEANED;

-- ------------------------------------------------------------
-- FCT_LISTING_SNAPSHOT — per-listing investment metrics.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.FCT_LISTING_SNAPSHOT
    COMMENT 'Per-listing investment metrics: ADR, occupancy rate, annual revenue, RevPAR. v1 uses scraper estimates.'
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
    (ESTIMATED_OCCUPANCY_L365D >= 30)                  AS IS_ACTIVE,
    ROUND(ESTIMATED_OCCUPANCY_L365D / 365.0, 4)        AS OCCUPANCY_RATE,
    ESTIMATED_REVENUE_L365D                            AS ANNUAL_REVENUE,
    ROUND(ESTIMATED_REVENUE_L365D / 365.0, 2)          AS REVPAR,
    REVIEW_SCORES_RATING,
    NUMBER_OF_REVIEWS
FROM AIRBNB_INVESTMENT.GOLD.DIM_LISTING;

COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.FCT_LISTING_SNAPSHOT.IS_ACTIVE IS 'TRUE if OCCUPANCY_NIGHTS (estimated booked nights, L365D) >= 30. The single conformed active-listing definition; marts read this flag rather than re-deriving the >=30 threshold.';

-- ------------------------------------------------------------
-- FCT_LISTING_POI — proximity features (bounded 500m spatial join).
-- ------------------------------------------------------------
-- 🔴 ST_DWITHIN IS A UNIT TRAP — THE SINGLE MOST DANGEROUS LINE IN GOLD.
--
-- Snowflake's ST_DWITHIN takes GEOGRAPHY and measures METRES. Databricks'
-- measures in the SRID's units — DEGREES at 4326. Measured on one Westminster
-- listing, 2026-07-28:
--
--     st_dwithin(st_transform(...,27700), 500)  ->        831 POIs   [correct]
--     st_dwithin(geo_4326, loc_4326, 500)       ->    122,560 POIs
--     total POIs with confidence >= 0.5         ->    122,560
--
-- The naive figure EQUALS the total POI count: 500 degrees exceeds the Earth's
-- circumference, so every POI matches every listing. That is not a subtly wrong
-- number — it is a 12.6 BILLION-row cross product (102,591 x 122,560) before the
-- GROUP BY, versus 19.3M pairs when projected correctly. A 650x difference.
--
-- Fixed by reprojecting to EPSG:27700 (British National Grid), whose units are
-- metres. Full-scale verified: 102,591 listings, 19,337,214 pairs, avg 188.5
-- POIs within 500m, max 2,044, 44 listings with zero — in ~14 seconds.
--
-- ⚠️ The transforms are done ONCE per row in CTEs, not inline in the ON clause,
--    so they are not re-evaluated per candidate pair. This is the shape that was
--    performance-tested; do not "simplify" it back into the join condition.
--
-- ⚠️ Do NOT replace this with st_distance/st_distancesphere without re-testing:
--    st_dwithin can use a spatial index in a projected CRS, which is why 19.3M
--    pairs resolve in seconds.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.FCT_LISTING_POI
    COMMENT 'POI proximity per listing: count of POIs within 500m, overall and for transport/dining. Bounded st_dwithin join, reprojected to EPSG:27700 so the radius is in metres.'
AS
WITH l AS (
    SELECT LISTING_ID,
           st_transform(GEO_POINT, 27700) AS pt_bng
    FROM AIRBNB_INVESTMENT.GOLD.DIM_LISTING
),
p AS (
    SELECT NAME, IS_TRANSPORT, IS_DINING,
           st_transform(LOCATION, 27700) AS loc_bng
    FROM AIRBNB_INVESTMENT.GOLD.DIM_POI
)
SELECT
    l.LISTING_ID,
    COUNT(p.NAME)                                                       AS POI_COUNT_500M,
    COUNT(CASE WHEN p.IS_TRANSPORT THEN 1 END)                          AS TRANSPORT_COUNT_500M,
    COUNT(CASE WHEN p.IS_DINING    THEN 1 END)                          AS DINING_COUNT_500M
FROM l
LEFT JOIN p
    ON st_dwithin(l.pt_bng, p.loc_bng, 500)
GROUP BY l.LISTING_ID;

-- ------------------------------------------------------------
-- FCT_AREA_SALE_PRICE — shared Land Registry sale-price fact.
-- Grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat / House / Other / All).
-- Single source of truth for every mart's sale-price benchmark.
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
--   point-in-polygon).
--   ⚠️ Coverage is currently 99.783%, not the documented 99.95% — the loaded
--   ONSPD edition is Feb 2024 while the current release is May 2026, so 298
--   postcodes from post-Feb-2024 sales do not resolve. Fully attributed in
--   databricks/verification_invariants.md. Landing the current edition should
--   take it to ~99.97%.
-- QUALITY: quality_flag='ok' only (arm's-length market sales in sane bounds).
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.FCT_AREA_SALE_PRICE
    COMMENT 'Shared Land Registry sale-price fact. Grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House/Other/All). Price Paid (quality_flag=ok) placed into neighbourhoods via SILVER.POSTCODE_NEIGHBOURHOOD_MAP spatial bridge; STRUCTURE_CLASS from PRICE_PAID_CLEANED.property_class (Other=code O; All=pooled F,D,S,T). Single source for all mart sale-price benchmarks.'
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
    FROM AIRBNB_INVESTMENT.SILVER.PRICE_PAID_CLEANED p
    JOIN AIRBNB_INVESTMENT.SILVER.POSTCODE_NEIGHBOURHOOD_MAP b
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
--   'structure' -> RENT_CATEGORY 'Flat'/'House' (House = mean of Detached/
--                  Semi-detached/Terraced) — matches
--                  FCT_AREA_SALE_PRICE.STRUCTURE_CLASS for the strategy mart.
--   'bedroom'   -> RENT_CATEGORY '1'/'2'/'3'/'4+' (ONS 4+ covers 4 and 5+).
--                  NOTE: ONS does NOT cross bedroom x structure, so bedroom rent
--                  is independent of structure_class.
--
-- Source: SILVER.ONS_PRIVATE_RENT_CLEANED (latest published month) placed into
--   Airbnb neighbourhoods via SILVER.NEIGHBOURHOOD_ONS_AREA_MAP. RENT_GRAIN
--   flags resolution: 'exact' (London borough / GM district) vs 'broadcast'
--   (Manchester wards -> Manchester; Bristol wards -> city).
--
-- ⚠️ City of London has ONS_AREA_CODE = NULL by design, so it is excluded here
--    by `WHERE x.ONS_AREA_CODE IS NOT NULL` and will have no rent row. That is
--    the documented Snowflake behaviour, not a port regression.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.FCT_AREA_RENT
    COMMENT 'Observed ONS private-rent benchmark. Grain: NEIGHBOURHOOD x RENT_CATEGORY (overall/structure/bedroom). Latest ONS month, placed into neighbourhoods via SILVER.NEIGHBOURHOOD_ONS_AREA_MAP (RENT_GRAIN exact/broadcast). House = mean of Detached/Semi/Terraced.'
AS
WITH latest AS (
    SELECT MAX(period) AS period FROM AIRBNB_INVESTMENT.SILVER.ONS_PRIVATE_RENT_CLEANED
),
rent AS (
    SELECT r.area_code, r.period, r.category, r.category_type, r.property_class, r.rental_price
    FROM AIRBNB_INVESTMENT.SILVER.ONS_PRIVATE_RENT_CLEANED r
    JOIN latest l ON r.period = l.period
    WHERE r.rental_price IS NOT NULL
),
joined AS (
    SELECT x.NEIGHBOURHOOD, x.CITY, x.RENT_GRAIN, r.period,
           r.category, r.category_type, r.property_class, r.rental_price
    FROM AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOOD_ONS_AREA_MAP x
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
