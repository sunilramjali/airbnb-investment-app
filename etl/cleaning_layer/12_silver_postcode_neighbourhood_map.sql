-- Builds SILVER.POSTCODE_NEIGHBOURHOOD_MAP: a postcode -> neighbourhood spatial bridge.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — POSTCODE -> NEIGHBOURHOOD SPATIAL BRIDGE
-- ------------------------------------------------------------
-- Purpose: HM Land Registry Price Paid sales are located by POSTCODE only
-- (no lat/long, no neighbourhood), while Airbnb listings are located by
-- NEIGHBOURHOOD. This bridge assigns every postcode a neighbourhood so the
-- two sources can be aggregated on the SAME area grain.
--
-- Method: point-in-polygon.
--   CODE_POINT_CLEANED.GEOGRAPHY (postcode centroid)
--     ST_WITHIN
--   NEIGHBOURHOODS_GEO_CLEANED.BOUNDARY (Inside Airbnb neighbourhood polygon)
--
-- Grain : one row per POSTCODE_KEY (normalised, space-stripped postcode).
--         0 polygon overlaps observed across the 3 areas; the QUALIFY is a
--         defensive dedup so the grain is guaranteed even if polygons ever
--         overlap.
-- CITY  : derived from the polygon's source filename (same rule as
--         GOLD.DIM_NEIGHBOURHOOD), so downstream consumers get city for free.
--
-- Validated coverage (Price Paid 'ok' postcodes): 157,638 / 157,725 = 99.95%
-- map to a neighbourhood; 108/108 neighbourhood names match Airbnb exactly.
--
-- Consumer: GOLD.FCT_AREA_SALE_PRICE (joins Price Paid -> postcode_key -> here).
-- Refresh : DYNAMIC TABLE, TARGET_LAG = DOWNSTREAM (refreshes only to satisfy
--           the sale-price fact). FULL refresh (spatial join is a complex query).
-- ============================================================

CREATE OR REPLACE DYNAMIC TABLE AIRBNB_INVESTMENT_DB.SILVER.POSTCODE_NEIGHBOURHOOD_MAP
    TARGET_LAG = 'DOWNSTREAM'
    REFRESH_MODE = AUTO
    INITIALIZE = ON_CREATE
    WAREHOUSE = COMPUTE_WH
    COMMENT = 'Postcode->neighbourhood spatial bridge: CODE_POINT geography point-in-polygon into NEIGHBOURHOODS_GEO_CLEANED. One row per postcode_key (dedup defensive; 0 polygon overlaps observed). Feeds GOLD.FCT_AREA_SALE_PRICE to give postcode-based Price Paid sales a neighbourhood + city.'
AS
SELECT
    cp.POSTCODE_KEY,
    n.NEIGHBOURHOOD,
    CASE SPLIT_PART(n._FILENAME, '/', 3)
        WHEN 'greater_manchester' THEN 'Greater Manchester'
        WHEN 'bristol'            THEN 'Bristol'
        WHEN 'london'             THEN 'London'
    END AS CITY
FROM AIRBNB_INVESTMENT_DB.SILVER.CODE_POINT_CLEANED cp
JOIN AIRBNB_INVESTMENT_DB.SILVER.NEIGHBOURHOODS_GEO_CLEANED n
    ON ST_WITHIN(cp.GEOGRAPHY, n.BOUNDARY)
QUALIFY ROW_NUMBER() OVER (PARTITION BY cp.POSTCODE_KEY ORDER BY n.NEIGHBOURHOOD) = 1;
