-- Builds SILVER.CODE_POINT_CLEANED: normalised postcode reference with a constructed point geometry.
-- Databricks REWRITE of etl/cleaning_layer/09_silver_code_point.sql — NOT a port.
-- ============================================================
-- SILVER — POSTCODE REFERENCE CLEANING TRANSFORM
-- ------------------------------------------------------------
-- ⚠️ THE SOURCE CHANGED. The Snowflake original read BRONZE.RAW_CODE_POINT
-- (Ordnance Survey "Code-Point Open", a Snowflake Marketplace share). No
-- equivalent share exists on Databricks, so postcodes now come from the ONS
-- Postcode Directory — BRONZE.RAW_ONSPD, loaded by
-- databricks/ingestion_layer/06_onspd_load.py.
--
-- 📛 THE TABLE NAME IS DELIBERATELY UNCHANGED. It no longer describes its
-- source, but keeping CODE_POINT_CLEANED means file 12 and the whole Gold layer
-- keep their existing references, and the ported files stay diffable against
-- their Snowflake originals (the stated layout goal — see LOG.md session 3).
-- ⚠️ docs/data_pipeline.md:84 still describes this as Code-Point and needs updating.
--
-- Grain : one row per POSTCODE_KEY (upper-cased, spaces stripped) — unchanged.
-- Still a light "clean only" transform: no spatial scoping, nothing filtered.
--
-- ============================================================
-- 1. COLUMN MAPPING — all confirmed against the real 53-column header
-- ------------------------------------------------------------
--     Code-Point Open (old)      ->  ONSPD (new)
--     POSTCODE                   ->  pcds
--     ADMIN_DISTRICT_CODE        ->  oslaua
--     ADMIN_WARD_CODE            ->  osward
--     COUNTRY_CODE               ->  ctry
--     ADMIN_COUNTY_CODE          ->  oscty
--     POSITIONAL_QUALITY_IND.    ->  osgrdind
--     NHS_HA_CODE                ->  oshlthau
--     NHS_REGIONAL_HA_CODE       ->  nhser
--     GEOMETRY / GEOGRAPHY       ->  none — CONSTRUCTED below from lat/long
--     _SOURCE                    ->  _FILENAME  (ONSPD Bronze carries no _SOURCE)
--
-- ============================================================
-- 2. GEOMETRY IS CONSTRUCTED, AND THE COLUMN IS RENAMED TO GEOM
-- ------------------------------------------------------------
-- Code-Point shipped native GEOMETRY and GEOGRAPHY columns. ONSPD ships plain
-- lat/long numbers (kept as TEXT in Bronze per the all-TEXT rule), so the point
-- is built here:
--
--     st_setsrid(st_point(long, lat), 4326)
--
-- SRID 4326 is asserted explicitly so this matches the borough polygons from
-- st_geomfromgeojson in file 06. Without st_setsrid the geometry would carry
-- SRID 0 and ST_WITHIN across the two would be semantically undefined while
-- still appearing to work (the exact bug caught in Bronze — LOG.md session 3).
--
-- ⚠️ RENAMED GEOGRAPHY -> GEOM. In Databricks GEOGRAPHY is a distinct, narrower
-- type from GEOMETRY; calling a GEOMETRY column "GEOGRAPHY" would be actively
-- misleading. File 12 is updated to match. Gold must use GEOM too.
--
-- ============================================================
-- 3. 🔴 ONSPD HAS A "NO GRID REFERENCE" SENTINEL — CODE-POINT DID NOT
-- ------------------------------------------------------------
-- 24,012 of 2,700,777 rows carry lat = 99.999999 (long = 0.0), ONS's marker for
-- a postcode with no grid reference. Code-Point Open only ever shipped
-- geocoded postcodes, so the original had nothing to guard against.
--
-- Building a point from those would place 24,012 postcodes at an IMPOSSIBLE
-- latitude — st_within would simply never match them, so they would look like
-- ordinary "outside every polygon" misses rather than missing data. GEOM is
-- therefore NULL for them, and IS_GEOCODED records the distinction so the
-- coverage invariant stays attributable.
--
-- ============================================================
-- 4. TERMINATED POSTCODES ARE KEPT AND FLAGGED (Sunil's decision, 2026-07-28)
-- ------------------------------------------------------------
-- ONSPD carries 901,381 terminated postcodes; Code-Point Open carried none.
-- They are KEPT because Price Paid is historic — sales from 2021-23 reference
-- postcodes that have since been retired, and those are exactly the rows that
-- would otherwise fail to resolve.
--
-- IS_TERMINATED makes the change explicit and reversible: Gold can exclude them
-- with one predicate, and any movement in the documented 99.95% coverage
-- invariant can be attributed to them rather than guessed at. Keeping them
-- WITHOUT the flag was rejected for exactly that reason.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.CODE_POINT_CLEANED AS
SELECT
    -- ---- normalised join key (the grain) ----
    UPPER(REPLACE(pcds, ' ', ''))          AS POSTCODE_KEY,
    pcds                                   AS POSTCODE,

    -- ---- lifecycle: kept, not filtered. See section 4. ----
    (doterm IS NOT NULL)                   AS IS_TERMINATED,
    TRY_TO_DATE(dointr, 'yyyyMM')          AS DATE_INTRODUCED,
    TRY_TO_DATE(doterm, 'yyyyMM')          AS DATE_TERMINATED,

    -- ---- administrative codes (renamed from Code-Point, section 1) ----
    osgrdind                               AS POSITIONAL_QUALITY_INDICATOR,
    ctry                                   AS COUNTRY_CODE,
    nhser                                  AS NHS_REGIONAL_HA_CODE,
    oshlthau                               AS NHS_HA_CODE,
    oscty                                  AS ADMIN_COUNTY_CODE,
    oslaua                                 AS ADMIN_DISTRICT_CODE,
    osward                                 AS ADMIN_WARD_CODE,

    -- ---- raw coordinates, kept for traceability ----
    TRY_CAST(lat AS DOUBLE)                AS LATITUDE,
    TRY_CAST(`long` AS DOUBLE)             AS LONGITUDE,

    -- ---- was this postcode geocoded at all? See section 3. ----
    (TRY_CAST(lat AS DOUBLE) IS NOT NULL
     AND TRY_CAST(lat AS DOUBLE) <> 99.999999)  AS IS_GEOCODED,

    -- ---- constructed point, SRID 4326. NULL when not geocoded. ----
    CASE
        WHEN TRY_CAST(lat AS DOUBLE) IS NULL OR TRY_CAST(lat AS DOUBLE) = 99.999999
            THEN NULL
        ELSE st_setsrid(st_point(TRY_CAST(`long` AS DOUBLE),
                                 TRY_CAST(lat AS DOUBLE)), 4326)
    END                                    AS GEOM,

    -- ---- lineage (carried from bronze) ----
    _FILENAME,
    _LOAD_TS
FROM AIRBNB_INVESTMENT.BRONZE.RAW_ONSPD
WHERE pcds IS NOT NULL
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY UPPER(REPLACE(pcds, ' ', ''))
            ORDER BY _LOAD_TS DESC
        ) = 1;                           -- one row per postcode key, latest load wins
