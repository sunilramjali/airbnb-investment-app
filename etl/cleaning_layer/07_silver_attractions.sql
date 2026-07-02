-- Builds SILVER.ATTRACTIONS_CLEANED: one typed row per landmark/attraction POI, with a native GEOGRAPHY point.
-- Co-authored with CoCo
-- ============================================================
-- SILVER — ATTRACTIONS CLEANING TRANSFORM
-- ------------------------------------------------------------
-- Reads BRONZE.RAW_OVERTURE_POI (scoped Overture POIs) and keeps only
-- the ones that are genuine landmarks / visitor attractions, casting to
-- an analysis-ready shape for proximity scoring.
--
-- Principles (mirroring the other silver transforms):
--   * Extract scalars out of the Overture VARIANTs (NAMES, CATEGORIES).
--   * Classify into a small ATTRACTION_TYPE bucket via a category
--     allow-pattern; rows that match no bucket are DROPPED (that pattern
--     set IS the "is this an attraction?" filter).
--   * Assign each POI to the borough polygon it sits in (point-in-polygon
--     against SILVER.NEIGHBOURHOODS_GEO_CLEANED) so attractions share the
--     same NEIGHBOURHOOD grain as listings.
--   * Validate: must have a name and a geometry.
--   * Deduplicate to one row per POI id; latest load wins.
--   * Keep _SOURCE / _LOAD_TS lineage.
--
-- NOTE: CONFIDENCE is carried through (not filtered) so downstream can
-- choose its own threshold; low-confidence rows are common in Overture
-- but some real landmarks score low, so we do not drop on it here.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.ATTRACTIONS_CLEANED AS
WITH typed AS (
    SELECT
        -- ---- identity + name ----
        p.ID                                              AS poi_id,
        NULLIF(TRIM(p.NAMES:primary::string), '')         AS name,

        -- ---- raw category signals (lower-cased for matching) ----
        LOWER(p.CATEGORIES:primary::string)               AS category,
        LOWER(p.BASIC_CATEGORY)                           AS basic_category,

        -- ---- attraction bucket: the allow-pattern that defines "attraction" ----
        --      Ordered CASE: first matching bucket wins. NULL => not an attraction => dropped.
        CASE
            WHEN LOWER(p.CATEGORIES:primary::string) LIKE ANY ('%museum%', '%gallery%')
                THEN 'Museum/Gallery'
            WHEN LOWER(p.CATEGORIES:primary::string) LIKE ANY (
                     '%landmark%', '%monument%', '%historic%', '%heritage%',
                     '%castle%', '%palace%', '%cathedral%', '%monastery%',
                     '%ruins%', '%memorial%', '%abbey%')
                THEN 'Historic/Landmark'
            WHEN LOWER(p.CATEGORIES:primary::string) LIKE ANY (
                     '%park%', '%garden%', '%zoo%', '%aquarium%',
                     '%nature%', '%scenic%', '%lookout%', '%viewpoint%')
                THEN 'Park/Nature'
            WHEN LOWER(p.CATEGORIES:primary::string) LIKE ANY (
                     '%theater%', '%theatre%', '%opera%', '%concert%',
                     '%planetarium%', '%stadium%', '%arena%')
                THEN 'Entertainment/Culture'
            WHEN LOWER(p.CATEGORIES:primary::string) LIKE ANY (
                     '%attraction%', '%tourist%', '%observation%', '%theme_park%',
                     '%amusement%', '%pier%')
                THEN 'Attraction'
            ELSE NULL
        END                                               AS attraction_type,

        p.CONFIDENCE                                      AS confidence,
        p.GEOMETRY                                        AS location,     -- GEOGRAPHY point
        p._SOURCE,
        p._LOAD_TS
    FROM BRONZE.RAW_OVERTURE_POI p
),
classified AS (
    SELECT *
    FROM typed
    WHERE name IS NOT NULL                 -- must be named
      AND location IS NOT NULL             -- must be locatable
      AND attraction_type IS NOT NULL      -- must classify as an attraction
),
-- assign each attraction to the borough polygon it falls within
located AS (
    SELECT
        c.poi_id,
        c.name,
        c.category,
        c.attraction_type,
        c.basic_category,
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
        ) = 1;                             -- one row per POI, latest load wins
