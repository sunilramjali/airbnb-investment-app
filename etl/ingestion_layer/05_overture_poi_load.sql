-- Overture Maps Places — Bronze load (Marketplace share -> scoped Bronze snapshot).
-- Co-authored with CoCo
-- ============================================================
-- OVERTURE MAPS PLACES  —  LOAD (run each refresh).
-- ------------------------------------------------------------
-- SOURCE: the Overture Maps "Places" Marketplace share from CARTO,
--   mounted as the shared database OVERTURE_MAPS__PLACES. The global
--   places table (OVERTURE_MAPS__PLACES.CARTO.PLACE) holds ~75M point
--   POIs worldwide, so this Bronze step is NOT a faithful full copy:
--   it is a SPATIALLY SCOPED snapshot of only the POIs that fall inside
--   the borough polygons we already ingested (London / Greater
--   Manchester / Bristol), keeping Bronze faithful to the SOURCE COLUMN
--   SHAPE while restricting to our coverage.
--
-- Unlike the S3-based sources there is no stage or file format to create
-- (the data is a live share), so this single file is the whole load.
-- CREATE OR REPLACE keeps it idempotent: re-running after CARTO refreshes
-- the share simply rebuilds the scoped snapshot with no duplicates.
--
-- PREREQUISITES:
--   1) The OVERTURE_MAPS__PLACES Marketplace share is acquired (Get Data;
--      terms accepted) and mounted under that database name.
--   2) SILVER.NEIGHBOURHOODS_GEO_CLEANED exists (borough polygons) — it
--      defines the spatial coverage filter below.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- Bronze table: source columns we care about (faithful shape) + lineage.
--   Rebuilt each run (OR REPLACE) so the load stays idempotent.
--
--   Coverage filter strategy (two-stage):
--     1) A cheap NUMERIC bounding-box prefilter: keep only POIs whose
--        lon/lat fall inside the overall min/max envelope of all borough
--        polygons. This discards ~all of the 75M global rows before any
--        expensive geometry op.
--     2) An exact point-in-polygon test by JOINing to the INDIVIDUAL
--        borough (Multi)Polygons. We deliberately do NOT ST_UNION_AGG the
--        boroughs first: the union returns a GeometryCollection, which
--        ST_WITHIN/ST_CONTAINS does not support. A correlated EXISTS with
--        a spatial predicate is also unsupported, so we use a JOIN and
--        QUALIFY to keep one row per POI id (boroughs don't overlap, so
--        this is just a safety de-dup).
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_OVERTURE_POI AS
WITH bbox AS (   -- overall lon/lat envelope across every borough polygon
    SELECT
        MIN(ST_XMIN(BOUNDARY)) AS lon_min,
        MAX(ST_XMAX(BOUNDARY)) AS lon_max,
        MIN(ST_YMIN(BOUNDARY)) AS lat_min,
        MAX(ST_YMAX(BOUNDARY)) AS lat_max
    FROM SILVER.NEIGHBOURHOODS_GEO_CLEANED
),
candidates AS (  -- 1) cheap numeric bbox prefilter on the point's lon/lat
    SELECT p.*
    FROM OVERTURE_MAPS__PLACES.CARTO.PLACE p, bbox b
    WHERE ST_X(p.GEOMETRY) BETWEEN b.lon_min AND b.lon_max
      AND ST_Y(p.GEOMETRY) BETWEEN b.lat_min AND b.lat_max
)
SELECT
    c.ID,                                    -- Overture stable POI id
    c.GEOMETRY,                              -- GEOGRAPHY point
    c.NAMES,                                 -- VARIANT: {"primary": "...", ...}
    c.CATEGORIES,                            -- VARIANT: {"primary": "...", "alternate": [...]}
    c.BASIC_CATEGORY,                        -- rolled-up category string
    c.CONFIDENCE,                            -- Overture confidence score [0,1]
    c.ADDRESSES,                             -- VARIANT: address detail
    c.BRAND,                                 -- VARIANT: brand (chains), usually null for landmarks
    'OVERTURE_MAPS__PLACES.CARTO.PLACE'  AS _SOURCE,   -- lineage: originating share object
    CURRENT_TIMESTAMP()::TIMESTAMP_NTZ   AS _LOAD_TS   -- lineage: load timestamp
FROM candidates c
JOIN SILVER.NEIGHBOURHOODS_GEO_CLEANED n     -- 2) exact point-in-borough (per-polygon)
    ON ST_WITHIN(c.GEOMETRY, n.BOUNDARY)
QUALIFY ROW_NUMBER() OVER (PARTITION BY c.ID ORDER BY n.NEIGHBOURHOOD) = 1;

---------------------------------------------
-- Verify (uncomment to run interactively):
--   SELECT COUNT(*) AS poi_rows FROM BRONZE.RAW_OVERTURE_POI;
--   SELECT BASIC_CATEGORY, COUNT(*) FROM BRONZE.RAW_OVERTURE_POI
--   GROUP BY 1 ORDER BY 2 DESC LIMIT 30;
