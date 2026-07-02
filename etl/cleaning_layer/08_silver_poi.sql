-- Builds SILVER.POI_CLEANED: Overture POIs filtered to investment-relevant amenities, with a native GEOGRAPHY point.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — POI CLEANING TRANSFORM (investment-relevant amenities)
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_OVERTURE_POI (scoped Overture POIs) and keeps only
-- categories that plausibly influence Airbnb property investment value
-- (transport, attractions, green space, dining, groceries, fitness,
-- formal education, healthcare). Everything else — B2B/personal services,
-- offices, contractors, auto repair, commercial schools, etc. — is dropped.
--
-- Principles (mirroring the other silver transforms):
--   * Extract scalars out of the Overture VARIANTs (NAMES, CATEGORIES).
--   * Classify into AMENITY_GROUP via a CURATED allow-list. We match on
--     EXACT category tokens (IN-lists) rather than fuzzy LIKE, because
--     naive wildcards pull in noise: '%park%' -> parking, '%school%' ->
--     driving/dance/music schools, '%bar%' -> barber, '%bus%' ->
--     business_*. Only a couple of safe wildcards are used ('%restaurant%',
--     '%grocery%'). Rows matching no group are DROPPED (the allow-list IS
--     the "is this investment-relevant?" filter).
--   * Assign each POI to the borough polygon it sits in (point-in-polygon
--     against SILVER.NEIGHBOURHOODS_GEO_CLEANED).
--   * Validate: must have a name and a geometry.
--   * Deduplicate to one row per POI id; latest load wins.
--   * Keep _SOURCE / _LOAD_TS lineage.
--
-- NOTE: CONFIDENCE is carried through (not filtered) so downstream can
-- choose its own threshold.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.POI_CLEANED AS
WITH typed AS (
    SELECT
        p.ID                                              AS poi_id,
        NULLIF(TRIM(p.NAMES:primary::string), '')         AS name,
        LOWER(p.CATEGORIES:primary::string)               AS category,
        p.CONFIDENCE                                      AS confidence,
        p.GEOMETRY                                        AS location,
        p._SOURCE,
        p._LOAD_TS
    FROM BRONZE.RAW_OVERTURE_POI p
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
    LEFT JOIN SILVER.NEIGHBOURHOODS_GEO_CLEANED n
        ON ST_WITHIN(c.location, n.BOUNDARY)
)
SELECT *
FROM located
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY poi_id
            ORDER BY _LOAD_TS DESC
        ) = 1;                          -- one row per POI, latest load wins
