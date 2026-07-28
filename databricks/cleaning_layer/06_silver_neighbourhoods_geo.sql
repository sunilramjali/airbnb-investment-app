-- Builds SILVER.NEIGHBOURHOODS_GEO_CLEANED: flattens the GeoJSON FeatureCollection into one polygon per borough.
-- Databricks port of etl/cleaning_layer/06_silver_neighbourhoods_geo.sql.
-- ============================================================
-- SILVER — NEIGHBOURHOODS GEO CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_NEIGHBOURHOODS_GEO (3 VARIANT rows, one GeoJSON
-- FeatureCollection per city) and explodes it into one row per
-- borough polygon.
--
-- This is a 3 -> 108 fan-out, unlike the row-preserving transforms.
--
-- Principles (unchanged):
--   * Explode the features array; one output row per feature.
--   * Build a geometry for spatial joins (point-in-polygon).
--   * Validate: drop features with no usable neighbourhood.
--   * Deduplicate to one row per neighbourhood; latest load wins.
--   * Keep _FILENAME / _LOAD_TS lineage.
--
-- NOTE: feature "neighbourhood_group" is null/"None" for some cities
-- (e.g. London groups boroughs flat) but carries a real value for
-- others, so it IS carried into silver with 'None' normalised to NULL.
--
-- ============================================================
-- 🔴 ST_AREA IS A UNIT TRAP — THE SAME CLASS AS ST_DWITHIN
-- ------------------------------------------------------------
-- Snowflake's ST_AREA on a GEOGRAPHY returns SQUARE METRES, so the original
-- divided by 1e6 to get km². Databricks' st_area returns area in the SRID's
-- units — for EPSG:4326 that is SQUARE DEGREES.
--
-- A verbatim port is wrong by ~8 orders of magnitude and NOTHING FAILS.
-- Measured 2026-07-28 against real borough areas:
--
--     borough                naive st_area   st_transform(...,27700)   true
--     Kingston upon Thames   0.00481         37.26                     37.25 km²
--     Croydon                0.01116         86.49                     86.52 km²
--     Bromley                0.01938         150.13                    150.15 km²
--
-- Fixed by reprojecting to EPSG:27700 (British National Grid), whose units are
-- metres — the same approach Session 2 chose for ST_DWITHIN. The log had only
-- ever flagged distance; the trap applies to EVERY metric ST_ function.
--
-- ⚠️ ST_WITHIN is NOT affected — it is topological, not metric, so it ports
-- verbatim in files 08 and 12.
--
-- ============================================================
-- OTHER CHANGES FROM SNOWFLAKE
-- ------------------------------------------------------------
--   LATERAL FLATTEN(input => x)  -> LATERAL variant_explode(x)
--       The `f.value` accessor and the `:path::type` syntax are IDENTICAL —
--       verified, no edit needed to any VARIANT path expression.
--
--   TO_GEOGRAPHY(f.value:geometry) -> st_geomfromgeojson(to_json(f.value:geometry))
--       ⚠️ st_geomfromgeojson takes a STRING; f.value:geometry is a VARIANT, so
--       it needs to_json() around it. TO_GEOGRAPHY accepted the VARIANT directly.
--       st_geomfromgeojson returns SRID 4326, which matches the SRID already
--       stored on BRONZE.RAW_OVERTURE_POI.GEOMETRY — so the ST_WITHIN in file 08
--       compares like with like. (st_geomfromwkb returns SRID 0; that mismatch
--       was fixed in Bronze, see LOG.md session 3.)
--
--   The geometry is built ONCE in a CTE rather than twice inline, so boundary
--   and area_sqkm cannot drift apart.
--
-- ⚠️ _FILENAME is consumed downstream to derive CITY (file 12 and Gold's
--    DIM_NEIGHBOURHOOD). Its format CHANGED: Snowflake stored a stage-relative
--    path, Databricks stores a full s3:// URL. See file 12 for the consequence.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOODS_GEO_CLEANED AS
WITH features AS (
    SELECT
        f.value        AS feature,
        g._FILENAME,
        g._LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_NEIGHBOURHOODS_GEO g,
         LATERAL variant_explode(g.RAW:features) f
),
flattened AS (
    SELECT
        -- ---- borough name (grain) ----
        NULLIF(TRIM(feature:properties:neighbourhood::string), '')   AS neighbourhood,

        -- ---- borough group ('None' literal -> NULL) ----
        NULLIF(NULLIF(TRIM(feature:properties:neighbourhood_group::string), ''), 'None') AS neighbourhood_group,

        -- ---- geometry (MultiPolygon boundary), SRID 4326 ----
        st_geomfromgeojson(to_json(feature:geometry))                AS boundary,

        -- ---- lineage (carried from bronze) ----
        _FILENAME,
        _LOAD_TS
    FROM features
)
SELECT
    neighbourhood,
    neighbourhood_group,
    boundary,
    -- convenience metric: borough area in km^2. Reprojected to EPSG:27700 first
    -- because st_area on a 4326 geometry returns SQUARE DEGREES — see the header.
    st_area(st_transform(boundary, 27700)) / 1e6                     AS area_sqkm,
    _FILENAME,
    _LOAD_TS
FROM flattened
WHERE neighbourhood IS NOT NULL          -- must have a usable borough name
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY neighbourhood
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per borough, latest load wins
