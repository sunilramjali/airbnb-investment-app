-- Builds SILVER.NEIGHBOURHOOD_ONS_AREA_MAP: bridges each Airbnb neighbourhood to its ONS PIPR area.
-- Databricks port of etl/cleaning_layer/14_silver_neighbourhood_ons_area_map.sql.
-- ============================================================
-- SILVER — NEIGHBOURHOOD -> ONS AREA CROSSWALK
-- ------------------------------------------------------------
-- Purpose: ONS Price Index of Private Rents is published at LOCAL-AUTHORITY
-- grain, while Airbnb/Price Paid aggregate at NEIGHBOURHOOD grain. This bridge
-- assigns every neighbourhood the ONS area whose rent applies to it, so
-- SILVER.ONS_PRIVATE_RENT_CLEANED can join to the neighbourhood-grain facts
-- (FCT_AREA_SALE_PRICE / MART_AREA_STRATEGY) on the SAME area key.
--
-- Grain : one row per (neighbourhood, city), from SILVER.NEIGHBOURHOODS_GEO_CLEANED
--         (city derived from the source filename — same rule as DIM_NEIGHBOURHOOD).
--
-- Mapping rules (verified against the data):
--   * London  : Inside Airbnb neighbourhoods ARE the boroughs, and match ONS
--               area_name 1:1 (32/32) -> map neighbourhood -> itself. EXACT.
--   * Greater Manchester:
--       - "<X> District" neighbourhoods (Bolton District, Salford District, ...)
--         -> ONS district X (strip " District"). EXACT.
--       - all other GM neighbourhoods are Manchester wards (Ancoats, Didsbury,
--         Hulme, ...) -> ONS "Manchester" (E08000003). BROADCAST.
--   * Bristol : ONS has a single "Bristol, City of" row; the 34 Airbnb wards
--               all map to it. BROADCAST.
--
-- rent_grain flags the resolution so consumers know when rent is shared:
--   'exact'     = neighbourhood maps 1:1 to its own ONS area (London boroughs,
--                 GM "District" rows).
--   'broadcast' = many neighbourhoods share one ONS area (Manchester wards ->
--                 Manchester; Bristol wards -> Bristol). Rent is identical
--                 across those neighbourhoods; yield spread there comes only
--                 from sale-price / Airbnb-revenue variation.
--
-- ons_area_code is attached by matching the mapped name back to the distinct
-- ONS areas (district rows only; the London region roll-up E12000007 is excluded).
--
-- 📄 INVARIANT: London must resolve 32/32 as 'exact' (docs/data_pipeline.md:96).
--    One of only four Silver invariants that survived the loss of Snowflake.
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE
-- ------------------------------------------------------------
-- 🔴 SPLIT_PART(_FILENAME,'/',3) NO LONGER YIELDS THE CITY — the same bug as
--    file 12. Snowflake stored a stage-relative path (city at position 3);
--    Databricks stores a full s3:// URL, where position 3 is the BUCKET NAME.
--
--    Ported verbatim, every CITY would be NULL. Every neighbourhood would then
--    fall through the CASE below to ons_area_name = NULL, the LEFT JOIN would
--    match nothing, and the table would come out fully populated with a NULL
--    ons_area_code on every row — no error, and the 32/32 invariant would fail
--    for a reason that has nothing to do with the crosswalk logic.
--
--    Fixed with a depth-independent regexp_extract, identical to file 12.
--
--   ALTER TABLE ... SET CHANGE_TRACKING = TRUE -> DELETED. See file 10.
--
-- ✅ ILIKE ports unchanged (verified: 'Bolton District' ILIKE '% District').
-- ✅ LEFT / LENGTH / TRIM / LOWER port unchanged.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOOD_ONS_AREA_MAP AS
WITH ons_areas AS (
    -- distinct ONS district areas (exclude region roll-ups like E12000007)
    SELECT DISTINCT area_code, area_name
    FROM AIRBNB_INVESTMENT.SILVER.ONS_PRIVATE_RENT_CLEANED
    WHERE geo_level = 'district'
),
neighbourhoods AS (
    -- neighbourhood + city from the silver polygon source. City comes from the
    -- source path — see the header for why this is regexp_extract, not
    -- SPLIT_PART(...,3). GOLD.DIM_NEIGHBOURHOOD must use the identical rule.
    SELECT DISTINCT
        NEIGHBOURHOOD AS neighbourhood,
        CASE regexp_extract(_FILENAME, 'inside_airbnb/([^/]+)/', 1)
            WHEN 'greater_manchester' THEN 'Greater Manchester'
            WHEN 'bristol'            THEN 'Bristol'
            WHEN 'london'             THEN 'London'
        END AS city
    FROM AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOODS_GEO_CLEANED
),
mapped AS (
    SELECT
        n.neighbourhood,
        n.city,
        CASE
            WHEN n.city = 'London'
                THEN n.neighbourhood                                   -- borough = ONS area
            WHEN n.city = 'Greater Manchester' AND n.neighbourhood ILIKE '% District'
                THEN TRIM(LEFT(n.neighbourhood, LENGTH(n.neighbourhood) - LENGTH(' District')))
            WHEN n.city = 'Greater Manchester'
                THEN 'Manchester'                                      -- Manchester wards
            WHEN n.city = 'Bristol'
                THEN 'Bristol, City of'
        END AS ons_area_name,
        CASE
            WHEN n.city = 'London'                                             THEN 'exact'
            WHEN n.city = 'Greater Manchester' AND n.neighbourhood ILIKE '% District' THEN 'exact'
            ELSE 'broadcast'                                                    -- Manchester wards, Bristol wards
        END AS rent_grain
    FROM neighbourhoods n
)
SELECT
    m.neighbourhood,
    m.city,
    m.ons_area_name,
    a.area_code AS ons_area_code,
    m.rent_grain
FROM mapped m
LEFT JOIN ons_areas a
    ON LOWER(TRIM(a.area_name)) = LOWER(TRIM(m.ons_area_name));

-- Verify (uncomment to run interactively):
--   -- any neighbourhood that failed to resolve to an ONS area code?
--   SELECT * FROM AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOOD_ONS_AREA_MAP WHERE ons_area_code IS NULL;
--   -- coverage + grain split per city
--   SELECT city, rent_grain, COUNT(*) FROM AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOOD_ONS_AREA_MAP GROUP BY 1,2 ORDER BY 1,2;
