-- Builds SILVER.ONS_PRIVATE_RENT_CLEANED: typed, tidy-long ONS private rent panel for the target areas.
-- Databricks port of etl/cleaning_layer/13_silver_ons_private_rent.sql.
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
-- Principles (unchanged):
--   * try_to_date / TRY_CAST; TRIM text; ONS markers ('[z]','[x]', etc.) -> NULL
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
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE
-- ------------------------------------------------------------
--   USE DATABASE / two-level names -> USE CATALOG / three-level names
--   TRY_TO_DATE(x)                 -> try_to_date(x)      (verified present)
--   FLOAT                          -> DOUBLE              (Databricks FLOAT is
--                                     4-byte REAL; Snowflake FLOAT is 8-byte)
--
--   ALTER TABLE ... SET CHANGE_TRACKING = TRUE  -> DELETED. Delta maintains
--   change data implicitly; there is no flag to re-assert. See file 10.
--
-- ✅ VERIFIED TO PORT VERBATIM (checked, not assumed):
--   * CELLS[0] array indexing is 0-BASED, same as Snowflake.
--   * GET(array, n) is 0-based AND returns NULL out of range, same as Snowflake.
--     Both matter: the unpivot addresses blocks by computed offset (base_idx+3
--     reaches index 39), so an off-by-one or a range error would shift every
--     measure by one column — silently, since all four are numeric.
--   * VALUES (...) AS c(cols) inline table syntax.
--   * LEFT(x, 10) for trimming the timestamp off the period string.
--
-- 🔬 _FILE_ROW_NUMBER >= 4 IS LOAD-BEARING and survives the migration intact.
--    Unlike every other Bronze table (where _FILE_ROW_NUMBER is a synthetic
--    read-order number), RAW_ONS_PRIVATE_RENT's is the REAL sheet row from
--    openpyxl's enumerate(). Verified in Bronze: row 3 is the header
--    ["Time period","Area code",...], data starts at row 4.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.ONS_PRIVATE_RENT_CLEANED
-- 🔴 REQUIRED, and NOT for a default declared in this file — there isn't one.
-- BRONZE.RAW_ONS_PRIVATE_RENT._LOAD_TS was created with DEFAULT current_timestamp()
-- (see databricks/ingestion_layer/08_ons_private_rent_load.py), and a CTAS
-- INHERITS the column-default metadata from its source column. Without this the
-- statement fails with WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED even
-- though the SELECT below declares no default at all.
--
-- This is the ONLY Silver table affected: it is the only one whose Bronze source
-- carries a column default. Snowflake had no equivalent opt-in and no inheritance
-- problem, so there is nothing here that corresponds to the original.
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')
AS
WITH base AS (
    -- Typed dimensions + the raw CELLS array, scoped to the target areas.
    SELECT
        try_to_date(LEFT(CELLS[0]::STRING, 10))          AS period,
        TRIM(CELLS[1]::STRING)                           AS area_code,
        NULLIF(TRIM(CELLS[2]::STRING), '')               AS area_name,
        NULLIF(NULLIF(TRIM(CELLS[3]::STRING), ''), '[z]') AS region_name,
        CASE WHEN TRIM(CELLS[1]::STRING) LIKE 'E12%' THEN 'region' ELSE 'district' END AS geo_level,
        CELLS,
        _FILENAME,
        _FILE_ROW_NUMBER,
        _LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_ONS_PRIVATE_RENT
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
        TRY_CAST(GET(b.CELLS, c.base_idx)::STRING     AS DOUBLE) AS rent_index,
        TRY_CAST(GET(b.CELLS, c.base_idx + 1)::STRING AS DOUBLE) AS monthly_change,
        TRY_CAST(GET(b.CELLS, c.base_idx + 2)::STRING AS DOUBLE) AS annual_change,
        TRY_CAST(GET(b.CELLS, c.base_idx + 3)::STRING AS DOUBLE) AS rental_price,
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
