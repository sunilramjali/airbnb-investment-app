-- Builds SILVER.NEIGHBOURHOODS_GEO_CLEANED: flattens the GeoJSON FeatureCollection into one GEOGRAPHY polygon per borough.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — NEIGHBOURHOODS GEO CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_NEIGHBOURHOODS_GEO (1 VARIANT row holding a
-- GeoJSON FeatureCollection) and FLATTENs it into one row per
-- borough polygon, casting each geometry to native GEOGRAPHY.
--
-- This is a 1 -> 33 fan-out (one document, 33 features), unlike
-- the row-preserving transforms in the other files.
--
-- Principles:
--   * FLATTEN the features array; one output row per feature.
--   * Cast geometry to GEOGRAPHY for spatial joins (point-in-polygon
--     to map a listing's lat/long to its borough, distance, etc.).
--   * Validate: drop features with no usable neighbourhood.
--   * Deduplicate to one row per neighbourhood; latest load wins.
--   * Keep _FILENAME / _LOAD_TS lineage.
--
-- NOTE: feature "neighbourhood_group" is null for every borough
-- (London groups all boroughs flat), so it is intentionally NOT
-- carried into silver.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.NEIGHBOURHOODS_GEO_CLEANED AS
WITH flattened AS (
    SELECT
        -- ---- borough name (grain) ----
        NULLIF(TRIM(f.value:properties:neighbourhood::string), '')   AS neighbourhood,

        -- ---- geometry as native GEOGRAPHY (MultiPolygon boundary) ----
        TO_GEOGRAPHY(f.value:geometry)                               AS boundary,

        -- ---- convenience metric: borough area in km^2 ----
        ST_AREA(TO_GEOGRAPHY(f.value:geometry)) / 1e6                AS area_sqkm,

        -- ---- lineage (carried from bronze) ----
        g._FILENAME,
        g._LOAD_TS
    FROM BRONZE.RAW_NEIGHBOURHOODS_GEO g,
         LATERAL FLATTEN(input => g.RAW:features) f
)
SELECT *
FROM flattened
WHERE neighbourhood IS NOT NULL          -- must have a usable borough name
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY neighbourhood
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per borough, latest load wins
