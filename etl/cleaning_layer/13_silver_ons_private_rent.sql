-- Builds SILVER.ONS_PRIVATE_RENT_CLEANED: typed, tidy-long ONS private rent panel for the target areas.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — ONS PRIVATE RENT (PIPR) CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_ONS_PRIVATE_RENT (faithful landing: one ARRAY row per
-- workbook row, 'Table 1' tab, header on original row 3, data on rows >= 4)
-- and produces a typed, TIDY-LONG panel restricted to the investment areas.
--
-- The ONS workbook is WIDE: 4 dimensions + 4 measures (Index, Monthly change,
-- Annual change, Rental price) repeated across 9 breakdowns (all properties;
-- 1/2/3/4+ bed; detached/semi-detached/terraced/flat). We UNPIVOT those 9
-- breakdowns into rows so downstream analysis can slice by category.
--
-- Principles (same as the other Silver layers):
--   * TRY_TO_DATE / TRY_CAST; TRIM text; ONS markers ('[z]','[x]', etc.) -> NULL
--     (TRY_CAST of a non-numeric marker yields NULL automatically).
--   * Restrict to the target areas by AREA CODE (stable; names are ambiguous —
--     e.g. 'Canterbury'/'Tewkesbury' both contain 'bury').
--   * property_class (Flat/House) bridges to PRICE_PAID_CLEANED / the Airbnb
--     side for area x property_class comparison.
--   * Validate: drop rows with no period / area_code or all-NULL measures.
--   * Deduplicate to one row per (period, area_code, category); latest load wins.
--   * Keep _FILENAME / _FILE_ROW_NUMBER / _LOAD_TS lineage.
--
-- AREA SCOPE (by code — mirrors PRICE_PAID_CLEANED's county scope at LA grain):
--   * E06000023                 -> Bristol, City of
--   * E08000001 .. E08000010    -> Greater Manchester (10 metropolitan districts)
--   * E09%                      -> London (32 boroughs)
--   * E12000007                 -> London region roll-up (geo_level = 'region')
--
-- CELLS index -> header (row 3):
--   0 Time period | 1 Area code | 2 Area name | 3 Region or country name
--   4-7 all | 8-11 one bed | 12-15 two bed | 16-19 three bed | 20-23 four+ bed
--   24-27 detached | 28-31 semidetached | 32-35 terraced | 36-39 flat maisonette
--   (each block = Index, Monthly change, Annual change, Rental price)
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.ONS_PRIVATE_RENT_CLEANED AS
WITH base AS (
    -- Typed dimensions + the raw CELLS array, scoped to the target areas.
    SELECT
        TRY_TO_DATE(LEFT(CELLS[0]::STRING, 10))          AS period,
        TRIM(CELLS[1]::STRING)                           AS area_code,
        NULLIF(TRIM(CELLS[2]::STRING), '')               AS area_name,
        NULLIF(NULLIF(TRIM(CELLS[3]::STRING), ''), '[z]') AS region_name,
        CASE WHEN TRIM(CELLS[1]::STRING) LIKE 'E12%' THEN 'region' ELSE 'district' END AS geo_level,
        CELLS,
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM BRONZE.RAW_ONS_PRIVATE_RENT
    WHERE _FILE_ROW_NUMBER >= 4
      AND (
            TRIM(CELLS[1]::STRING) = 'E06000023'                          -- Bristol
         OR TRIM(CELLS[1]::STRING) BETWEEN 'E08000001' AND 'E08000010'    -- Greater Manchester
         OR TRIM(CELLS[1]::STRING) LIKE 'E09%'                            -- London boroughs
         OR TRIM(CELLS[1]::STRING) = 'E12000007'                          -- London region roll-up
      )
),
cats AS (
    -- One row per breakdown: label, type, Flat/House bridge, and the base
    -- CELLS index of its 4-measure block (index, monthly, annual, rental).
    SELECT * FROM (VALUES
        ('All property types',      'overall',       NULL,     4),
        ('One bedroom',             'bedroom',       NULL,     8),
        ('Two bedrooms',            'bedroom',       NULL,    12),
        ('Three bedrooms',          'bedroom',       NULL,    16),
        ('Four or more bedrooms',   'bedroom',       NULL,    20),
        ('Detached',                'property_type', 'House', 24),
        ('Semi-detached',           'property_type', 'House', 28),
        ('Terraced',                'property_type', 'House', 32),
        ('Flat/Maisonette',         'property_type', 'Flat',  36)
    ) AS c(category, category_type, property_class, base_idx)
),
unpivoted AS (
    SELECT
        b.period,
        b.area_code,
        b.area_name,
        b.region_name,
        b.geo_level,
        c.category,
        c.category_type,
        c.property_class,
        TRY_CAST(GET(b.CELLS, c.base_idx)::STRING     AS FLOAT) AS rent_index,
        TRY_CAST(GET(b.CELLS, c.base_idx + 1)::STRING AS FLOAT) AS monthly_change,
        TRY_CAST(GET(b.CELLS, c.base_idx + 2)::STRING AS FLOAT) AS annual_change,
        TRY_CAST(GET(b.CELLS, c.base_idx + 3)::STRING AS FLOAT) AS rental_price,
        b._FILENAME,
        b._FILE_ROW_NUMBER,
        b._LOAD_TS
    FROM base b
    CROSS JOIN cats c
)
SELECT *
FROM unpivoted
WHERE period    IS NOT NULL          -- must have a reporting month
  AND area_code IS NOT NULL          -- must have an area
  AND COALESCE(rent_index, monthly_change, annual_change, rental_price) IS NOT NULL  -- drop empty category rows
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY period, area_code, category
            ORDER BY _LOAD_TS DESC
        ) = 1;                        -- one row per (month, area, category), latest load wins

-- Re-enable change tracking: CREATE OR REPLACE TABLE above drops it, and the
-- downstream dynamic table GOLD.FCT_AREA_RENT reads this table -> its refresh
-- can fail without change tracking. Re-assert it on every rebuild.
ALTER TABLE SILVER.ONS_PRIVATE_RENT_CLEANED SET CHANGE_TRACKING = TRUE;
