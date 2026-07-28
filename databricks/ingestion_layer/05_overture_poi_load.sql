-- Overture Maps Places — Bronze load. Databricks port of etl/ingestion_layer/05_overture_poi_load.sql.
-- ============================================================
-- OVERTURE MAPS PLACES  —  LOAD (run each refresh).
-- ------------------------------------------------------------
-- SOURCE: the Overture Maps "Places" Marketplace listing from CARTO, attached as
--   the Delta Sharing catalog CARTO_OVERTURE_MAPS_PLACES. The global places table
--   (CARTO_OVERTURE_MAPS_PLACES.CARTO.PLACE) holds ~75M point POIs worldwide
--   (measured: 75,642,289), so this Bronze step is NOT a faithful full copy:
--   it is a SPATIALLY SCOPED snapshot of only the POIs that fall inside the
--   borough polygons we already ingested (London / Greater Manchester / Bristol),
--   keeping Bronze faithful to the SOURCE COLUMN SHAPE while restricting to our
--   coverage.
--
-- Unlike the S3-based sources there is no external location or file format to
-- create (the data is a live share), so this single file is the whole load.
-- CREATE OR REPLACE keeps it idempotent: re-running after CARTO refreshes the
-- share simply rebuilds the scoped snapshot with no duplicates.
--
-- PREREQUISITES:
--   1) The Overture Maps Places listing is acquired from Databricks Marketplace
--      and attached as the catalog CARTO_OVERTURE_MAPS_PLACES.
--   2) BRONZE.RAW_NEIGHBOURHOODS_GEO exists (raw GeoJSON FeatureCollections,
--      one row per city) — its per-feature borough polygons define the spatial
--      coverage filter below.
--
-- ============================================================
-- SNOWFLAKE -> DATABRICKS TRANSLATION NOTES
-- ------------------------------------------------------------
--   OVERTURE_MAPS__PLACES.CARTO.PLACE  (Snowflake Marketplace share)
--       -> CARTO_OVERTURE_MAPS_PLACES.CARTO.PLACE  (Delta Sharing catalog)
--          Same provider, same table, three-level name instead of two.
--
--   LATERAL FLATTEN(input => t.RAW:features) f
--       -> LATERAL variant_explode(t.RAW:features) f
--          The VARIANT path syntax itself (`:` navigation and `::` cast) ports
--          UNCHANGED — f.value:properties:neighbourhood::STRING is identical in
--          both engines.
--
--   TO_GEOGRAPHY(f.value:geometry)  -> st_geomfromgeojson(to_json(f.value:geometry))
--       Snowflake's GEOGRAPHY accepted a GeoJSON VARIANT directly. Databricks
--       ST_* functions operate on GEOMETRY, and st_geomfromgeojson takes a JSON
--       STRING, hence the to_json(). Returns SRID 4326 (verified).
--
--   ⚠️ p.GEOMETRY (Snowflake GEOGRAPHY column) -> p.geom, which is WKB BINARY here.
--       It must be decoded with st_geomfromwkb() AND given an SRID:
--
--         st_geomfromwkb(geom)                -> SRID 0    (verified)
--         st_geomfromgeojson(borough geojson) -> SRID 4326 (verified)
--
--       Joining those two directly is the silent-bug trap in this file. The
--       geometries are both lon/lat degrees, so a mismatched-SRID st_within can
--       appear to "work" while being semantically undefined. st_setsrid(...,4326)
--       on the Overture side makes both operands agree explicitly.
--
--   ST_X(p.GEOMETRY) / ST_Y(p.GEOMETRY) numeric prefilter
--       -> p.bbox.xmin / p.bbox.ymin. The Overture share ships a NATIVE bbox
--          struct<xmin,xmax,ymin,ymax> per row, so the prefilter reads a plain
--          double column instead of decoding 75M geometries to extract a
--          coordinate. This is strictly cheaper than the Snowflake original and
--          is what keeps the scan affordable (75,642,289 rows -> 1,788,763
--          candidates, a 97.6% cut, before any geometry work happens).
--
--   ST_WITHIN  -> st_within        (same semantics for point-in-polygon)
--   QUALIFY    -> QUALIFY          (supported; ports unchanged)
--
--   NO LOAD_AUDIT ROW. The Snowflake original does not write one either — this is
--   a CTAS from a live share, not a file COPY, so there is no per-file outcome to
--   record. Deliberate parity choice, not an omission.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA BRONZE;

---------------------------------------------
-- Bronze table: source columns we care about (faithful shape) + lineage.
--   Rebuilt each run (OR REPLACE) so the load stays idempotent.
--
--   Coverage filter strategy (two-stage):
--     1) A cheap NUMERIC bounding-box prefilter using the share's own bbox
--        struct: keep only POIs whose lon/lat fall inside the overall min/max
--        envelope of all borough polygons. This discards ~all of the 75M global
--        rows before any expensive geometry op.
--     2) An exact point-in-polygon test by JOINing to the INDIVIDUAL borough
--        (Multi)Polygons. We deliberately do NOT union the boroughs first: the
--        union returns a GeometryCollection, which st_within does not support.
--        A correlated EXISTS with a spatial predicate is also unsupported, so we
--        use a JOIN and QUALIFY to keep one row per POI id (boroughs don't
--        overlap, so this is just a safety de-dup).
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_OVERTURE_POI
COMMENT 'Bronze Overture Places — spatially scoped to our borough polygons, rebuilt each run.'
AS
WITH boroughs AS (  -- borough polygons parsed from the raw GeoJSON FeatureCollections
    SELECT
        f.value:properties:neighbourhood::STRING                AS NEIGHBOURHOOD,
        st_geomfromgeojson(to_json(f.value:geometry))           AS BOUNDARY   -- SRID 4326
    FROM BRONZE.RAW_NEIGHBOURHOODS_GEO t,
         LATERAL variant_explode(t.RAW:features) f
),
envelope AS (   -- overall lon/lat envelope across every borough polygon
    SELECT
        min(st_xmin(BOUNDARY)) AS lon_min,
        max(st_xmax(BOUNDARY)) AS lon_max,
        min(st_ymin(BOUNDARY)) AS lat_min,
        max(st_ymax(BOUNDARY)) AS lat_max
    FROM boroughs
),
candidates AS (  -- 1) cheap numeric bbox prefilter on the point's own bbox struct
    SELECT
        p.id, p.names, p.categories, p.basic_category, p.confidence,
        p.addresses, p.brand,
        st_setsrid(st_geomfromwkb(p.geom), 4326) AS GEOMETRY   -- SRID aligned to boroughs
    FROM CARTO_OVERTURE_MAPS_PLACES.CARTO.PLACE p, envelope b
    WHERE p.bbox.xmin BETWEEN b.lon_min AND b.lon_max
      AND p.bbox.ymin BETWEEN b.lat_min AND b.lat_max
)
SELECT
    c.ID,                                    -- Overture stable POI id
    c.GEOMETRY,                              -- GEOMETRY point, SRID 4326
    c.NAMES,                                 -- STRUCT: {primary, common, rules}
    c.CATEGORIES,                            -- STRUCT: {primary, alternate[]}
    c.BASIC_CATEGORY,                        -- rolled-up category string
    c.CONFIDENCE,                            -- Overture confidence score [0,1]
    c.ADDRESSES,                             -- ARRAY<STRUCT>: address detail
    c.BRAND,                                 -- STRUCT: brand (chains), usually null for landmarks
    'CARTO_OVERTURE_MAPS_PLACES.CARTO.PLACE'   AS _SOURCE,   -- lineage: originating share object
    CAST(current_timestamp() AS TIMESTAMP_NTZ) AS _LOAD_TS   -- lineage: load timestamp
FROM candidates c
JOIN boroughs n     -- 2) exact point-in-borough (per-polygon)
    ON st_within(c.GEOMETRY, n.BOUNDARY)
QUALIFY row_number() OVER (PARTITION BY c.ID ORDER BY n.NEIGHBOURHOOD) = 1;

---------------------------------------------
-- ⚠️ SHAPE CHANGE FOR SILVER: NAMES / CATEGORIES / ADDRESSES / BRAND arrive as
--   native STRUCT / ARRAY<STRUCT> here, not VARIANT as they did in Snowflake.
--   Silver's VARIANT accessors must change accordingly, e.g.
--       NAMES:primary::STRING      ->  NAMES.primary
--       CATEGORIES:primary::STRING ->  CATEGORIES.primary
--   Recorded in LOG.md for the Silver port; NOT fixed here, because Bronze must
--   stay faithful to the shape the source actually delivers.
--
-- Verify (uncomment to run interactively):
--   SELECT COUNT(*) AS poi_rows FROM BRONZE.RAW_OVERTURE_POI;
--   SELECT BASIC_CATEGORY, COUNT(*) FROM BRONZE.RAW_OVERTURE_POI
--   GROUP BY 1 ORDER BY 2 DESC LIMIT 30;
---------------------------------------------
