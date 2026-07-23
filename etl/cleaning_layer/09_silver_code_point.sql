-- Builds SILVER.CODE_POINT_CLEANED: normalized postcode join key over a faithful full copy of BRONZE.RAW_CODE_POINT (no filter, no columns dropped).
-- Co-authored with CoCo
-- ============================================================
-- SILVER — CODE-POINT OPEN CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_CODE_POINT (~1.7M GB postcode units, faithful
-- full copy of the Ordnance Survey share) and produces a clean
-- postcode reference table.
--
-- This is a light "clean only" transform by design:
--   * NO filtering — all GB postcodes are kept (no spatial scoping).
--   * NO columns dropped — every bronze column is carried through.
--   * The ONLY added column is POSTCODE_KEY, a normalized join key
--     (upper-cased, spaces removed) so it matches the equivalently
--     normalized PRICE_PAID postcode in the aggregation step.
--
-- The postcode -> neighbourhood attribution (ST_WITHIN against the
-- borough polygons) is deliberately DEFERRED to the aggregation
-- layer (etl/aggregation_layer/03_sales_codepoint.sql), keeping this
-- silver step a pure normalization of the reference data.
--
-- Principles (same as the other silver transforms):
--   * Deduplicate to one row per postcode key; latest load wins.
--   * Keep _SOURCE / _LOAD_TS lineage.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.CODE_POINT_CLEANED AS
SELECT
    -- ---- normalized join key (the one added column) ----
    UPPER(REPLACE(POSTCODE, ' ', ''))    AS POSTCODE_KEY,

    -- ---- all bronze columns carried through unchanged ----
    POSTCODE,
    POSITIONAL_QUALITY_INDICATOR,
    COUNTRY_CODE,
    NHS_REGIONAL_HA_CODE,
    NHS_HA_CODE,
    ADMIN_COUNTY_CODE,
    ADMIN_DISTRICT_CODE,
    ADMIN_WARD_CODE,
    GEOMETRY,
    GEOGRAPHY,

    -- ---- lineage (carried from bronze) ----
    _SOURCE,
    _LOAD_TS
FROM BRONZE.RAW_CODE_POINT
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY UPPER(REPLACE(POSTCODE, ' ', ''))
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per postcode key, latest load wins
