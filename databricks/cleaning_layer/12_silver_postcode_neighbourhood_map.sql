-- Builds SILVER.POSTCODE_NEIGHBOURHOOD_MAP: a postcode -> neighbourhood spatial bridge.
-- Databricks port of etl/cleaning_layer/12_silver_postcode_neighbourhood_map.sql.
-- ============================================================
-- SILVER — POSTCODE -> NEIGHBOURHOOD SPATIAL BRIDGE
-- ------------------------------------------------------------
-- Purpose: HM Land Registry Price Paid sales are located by POSTCODE only
-- (no lat/long, no neighbourhood), while Airbnb listings are located by
-- NEIGHBOURHOOD. This bridge assigns every postcode a neighbourhood so the
-- two sources can be aggregated on the SAME area grain.
--
-- Method: point-in-polygon.
--   CODE_POINT_CLEANED.GEOM (postcode centroid, SRID 4326)
--     ST_WITHIN
--   NEIGHBOURHOODS_GEO_CLEANED.BOUNDARY (Inside Airbnb polygon, SRID 4326)
--
-- Grain : one row per POSTCODE_KEY. 0 polygon overlaps observed in Snowflake;
--         the QUALIFY is defensive dedup so the grain is guaranteed regardless.
--
-- 📄 VALIDATED COVERAGE (Snowflake era): 157,638 / 157,725 = 99.95% of Price
--    Paid 'ok' postcodes mapped to a neighbourhood; 108/108 neighbourhood names
--    matched Airbnb exactly. The denominator comes from PRICE_PAID_CLEANED, not
--    from the postcode table, so it survives the Code-Point -> ONSPD swap.
--    ⚠️ It CANNOT be signed off on the Feb 2024 ONSPD currently loaded — see
--    databricks/verification_invariants.md.
--
-- Consumer: GOLD.FCT_AREA_SALE_PRICE.
--
-- ============================================================
-- 🔴 SPLIT_PART(_FILENAME,'/',3) NO LONGER YIELDS THE CITY
-- ------------------------------------------------------------
-- Snowflake stored a STAGE-RELATIVE path, so the city sat at position 3.
-- Databricks stores _metadata.file_path — a FULL s3:// URL — so position 3 is
-- the BUCKET NAME:
--
--   s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/london/...
--    1     3 (bucket)                                     4    5             6 (city)
--
-- Ported verbatim, the CASE would match nothing and set CITY = NULL on EVERY
-- row, silently. Fixed with a depth-independent regexp_extract rather than
-- simply changing 3 to 6, so a bucket rename or an extra prefix level cannot
-- reintroduce the bug. Verified: returns 'london'.
--
-- ⚠️ GOLD.DIM_NEIGHBOURHOOD and file 14 use "the same rule"
-- (docs/data_pipeline.md:111) and need the identical fix.
--
-- ============================================================
-- OTHER CHANGES
-- ------------------------------------------------------------
--   cp.GEOGRAPHY -> cp.GEOM. File 09 renamed the column: it is a Databricks
--   GEOMETRY, and GEOGRAPHY is a different, narrower type there — the old name
--   would have been actively misleading.
--
--   ✅ ST_WITHIN ports UNCHANGED. It is topological, not metric, so it avoids
--   the unit trap that hits st_area (file 06) and st_dwithin (Gold). Both
--   inputs are SRID 4326, asserted explicitly on each side.
--
--   ⚠️ Postcodes with no grid reference have GEOM = NULL (24,012 of them — see
--   file 09 section 3). ST_WITHIN drops them here, which is correct: they have
--   no location to attribute. They are distinguishable from genuine
--   outside-every-polygon misses via CODE_POINT_CLEANED.IS_GEOCODED.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.POSTCODE_NEIGHBOURHOOD_MAP AS
SELECT
    cp.POSTCODE_KEY,
    n.NEIGHBOURHOOD,
    -- city from the polygon's source path — see the header for why this is a
    -- regexp_extract and not SPLIT_PART(...,3)
    CASE regexp_extract(n._FILENAME, 'inside_airbnb/([^/]+)/', 1)
        WHEN 'greater_manchester' THEN 'Greater Manchester'
        WHEN 'bristol'            THEN 'Bristol'
        WHEN 'london'             THEN 'London'
    END AS CITY
FROM AIRBNB_INVESTMENT.SILVER.CODE_POINT_CLEANED cp
JOIN AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOODS_GEO_CLEANED n
    ON ST_WITHIN(cp.GEOM, n.BOUNDARY)
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY cp.POSTCODE_KEY
            ORDER BY n.NEIGHBOURHOOD
        ) = 1;
