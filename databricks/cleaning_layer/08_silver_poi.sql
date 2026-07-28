-- Builds SILVER.POI_CLEANED: Overture POIs filtered to investment-relevant amenities, with a point geometry.
-- Databricks port of etl/cleaning_layer/08_silver_poi.sql.
-- ============================================================
-- SILVER — POI CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_OVERTURE_POI (634,958 rows, already spatially scoped
-- to the three cities during ingestion) and keeps only POIs that
-- plausibly affect property value, assigning each to a borough.
--
-- Principles (unchanged):
--   * Curated amenity allow-list on EXACT category tokens, not fuzzy LIKE.
--     Naive wildcards pull in noise: %park% -> parking, %school% -> driving
--     schools, %bar% -> barber, %bus% -> business services. Only two safe
--     wildcards are used (%restaurant%, %grocery%).
--   * Validate: must have a name, a location, and an amenity group.
--   * Assign to a borough by point-in-polygon.
--   * Deduplicate to one row per POI; latest load wins.
--   * CONFIDENCE is carried through unfiltered — GOLD.DIM_POI applies its own
--     >= 0.5 threshold, so each consumer chooses.
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE — less than expected
-- ------------------------------------------------------------
-- ✅ p.GEOMETRY PORTS UNCHANGED. The Overture Delta Sharing feed gives WKB
--    binary, but that conversion already happened in Bronze
--    (05_overture_poi_load.sql). Verified 2026-07-28: the column is native
--    GEOMETRY at SRID 4326 for all 634,958 rows — matching the SRID that
--    st_geomfromgeojson produces for the borough polygons in file 06, so the
--    ST_WITHIN below compares like with like.
--
-- ✅ ST_WITHIN PORTS UNCHANGED. It is topological, not metric, so it has none
--    of the unit trouble that affects st_area (file 06) and st_dwithin (Gold).
--
-- 🔴 THE ACCESSORS CHANGED. Snowflake received NAMES and CATEGORIES as VARIANT
--    and read them with `NAMES:primary::string`. The Delta Sharing feed types
--    them as native STRUCT, so the VARIANT path syntax does not apply:
--
--        NAMES:primary::string       ->  NAMES.primary
--        CATEGORIES:primary::string  ->  CATEGORIES.primary
--
--    Verified live: 'Kensington Palace Gardens' / 'park'. No backticks needed;
--    `primary` is not reserved in this position.
--
--    ⚠️ This is the general rule for this table — ADDRESSES (ARRAY<STRUCT>) and
--    BRAND (STRUCT) are the same shape if a later transform needs them.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.POI_CLEANED AS
WITH typed AS (
    SELECT
        p.ID                                              AS poi_id,
        NULLIF(TRIM(p.NAMES.primary), '')                 AS name,
        LOWER(p.CATEGORIES.primary)                       AS category,
        p.CONFIDENCE                                      AS confidence,
        p.GEOMETRY                                        AS location,
        p._SOURCE,
        p._LOAD_TS
    FROM AIRBNB_INVESTMENT.BRONZE.RAW_OVERTURE_POI p
),
grouped AS (
    SELECT
        t.*,
        -- ---- curated amenity allow-list: first matching group wins; NULL => dropped ----
        CASE
            WHEN category IN (
                     'train_station', 'metro_station', 'bus_station', 'transportation')
                THEN 'Transport'
            WHEN category IN (
                     'landmark_and_historical_building', 'museum', 'history_museum',
                     'art_museum', 'art_gallery', 'monument', 'theatre', 'cinema',
                     'arts_and_entertainment', 'amusement_park', 'stadium_arena',
                     'football_stadium')
                THEN 'Attractions & Culture'
            WHEN category IN (
                     'park', 'botanical_garden', 'hiking_trail')
                THEN 'Parks & Green'
            WHEN category LIKE '%restaurant%'
                 OR category IN ('cafe', 'coffee_shop', 'pub', 'bar', 'sports_bar', 'bakery')
                THEN 'Dining & Nightlife'
            WHEN category LIKE '%grocery%'
                 OR category IN ('supermarket', 'convenience_store', 'pharmacy',
                                 'pharmacy_and_drug_store')
                THEN 'Groceries & Essentials'
            WHEN category IN (
                     'gym', 'fitness_trainer', 'sports_club_and_league',
                     'sports_and_recreation_venue')
                THEN 'Fitness'
            WHEN category IN (
                     'elementary_school', 'high_school', 'preschool', 'day_care_preschool',
                     'private_school', 'religious_school', 'school', 'college_university',
                     'university')
                THEN 'Education'
            WHEN category IN (
                     'hospital', 'medical_center', 'doctor', 'public_health_clinic',
                     'health_and_medical', 'dentist')
                THEN 'Health'
            ELSE NULL
        END                                               AS amenity_group
    FROM typed t
),
classified AS (
    SELECT *
    FROM grouped
    WHERE name IS NOT NULL              -- must be named
      AND location IS NOT NULL          -- must be locatable
      AND amenity_group IS NOT NULL     -- must be investment-relevant
),
-- assign each POI to the borough polygon it falls within
located AS (
    SELECT
        c.poi_id,
        c.name,
        c.category,
        c.amenity_group,
        c.confidence,
        c.location,
        n.NEIGHBOURHOOD        AS neighbourhood,
        n.NEIGHBOURHOOD_GROUP  AS neighbourhood_group,
        c._SOURCE,
        c._LOAD_TS
    FROM classified c
    LEFT JOIN AIRBNB_INVESTMENT.SILVER.NEIGHBOURHOODS_GEO_CLEANED n
        ON ST_WITHIN(c.location, n.BOUNDARY)
)
SELECT *
FROM located
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY poi_id
            ORDER BY _LOAD_TS DESC
        ) = 1;                          -- one row per POI, latest load wins
