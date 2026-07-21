-- Builds the GOLD amenity marts: MART_AREA_AMENITIES and MART_AREA_AMENITY_GAP.
-- Co-authored with CoCo
-- ============================================================
-- GOLD - APP MARTS (amenities). Split out of 03_app_marts.sql.
-- Reads FCT_*/DIM_*/SILVER only -> order-independent after 03_app_marts_core.sql.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ============================================================
-- MART_AREA_AMENITIES — grain: NEIGHBOURHOOD x AMENITY_GROUP.
-- Area-COMPARISON screen: how well-equipped an area's listings are, by
-- amenity group. PCT_LISTINGS_WITH_GROUP = share of the area's listings
-- offering AT LEAST ONE amenity in that group. Long form (one row per
-- area x group) so the app can facet / grouped-bar the 3 pinned boroughs
-- across the ~13 curated groups. Filter with WHERE NEIGHBOURHOOD IN (...).
--
-- Source: SILVER.LISTING_AMENITIES (exploded listing x amenity, already
-- classified into AMENITY_GROUP) joined to GOLD.DIM_LISTING for the
-- listing's NEIGHBOURHOOD / CITY. AREA_LISTINGS is the denominator: the
-- count of DISTINCT listings in the area that have any amenities at all
-- (i.e. appear in LISTING_AMENITIES), so PCT is a clean 0..1 share.
--
-- This is DELIBERATELY decoupled from the persona investment scores and
-- AI narratives — it adds amenity insight without invalidating either.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_AMENITIES
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready amenity-group coverage per neighbourhood x amenity_group: listings offering >=1 amenity in the group, area listing base, and the coverage percentage. Long form for faceted area comparison.'
AS
WITH area_base AS (
    -- Denominator: distinct listings per area that have any amenities.
    SELECT
        d.NEIGHBOURHOOD,
        COUNT(DISTINCT la.LISTING_ID) AS AREA_LISTINGS
    FROM SILVER.LISTING_AMENITIES la
    JOIN GOLD.DIM_LISTING d
        ON la.LISTING_ID = d.LISTING_ID
    GROUP BY d.NEIGHBOURHOOD
),
group_cov AS (
    -- Numerator: distinct listings per area offering >=1 amenity in each group.
    SELECT
        d.NEIGHBOURHOOD,
        n.CITY,
        la.AMENITY_GROUP,
        COUNT(DISTINCT la.LISTING_ID) AS LISTINGS_WITH_GROUP
    FROM SILVER.LISTING_AMENITIES la
    JOIN GOLD.DIM_LISTING d
        ON la.LISTING_ID = d.LISTING_ID
    LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON d.NEIGHBOURHOOD = n.NEIGHBOURHOOD
    GROUP BY d.NEIGHBOURHOOD, n.CITY, la.AMENITY_GROUP
)
SELECT
    g.NEIGHBOURHOOD,
    g.CITY,
    g.AMENITY_GROUP,
    g.LISTINGS_WITH_GROUP,
    b.AREA_LISTINGS,
    ROUND(g.LISTINGS_WITH_GROUP / NULLIF(b.AREA_LISTINGS, 0), 4) AS PCT_LISTINGS_WITH_GROUP
FROM group_cov g
JOIN area_base b
    ON g.NEIGHBOURHOOD = b.NEIGHBOURHOOD;

-- ============================================================
-- MART_AREA_AMENITY_GAP — grain: NEIGHBOURHOOD x AMENITY_GROUP.
-- Area-COMPARISON / fit-out signal: within an area, how much more likely
-- are the TOP-earning listings to offer each amenity group than the rest?
-- GAP = PCT_TOP - PCT_REST. A big positive GAP flags an amenity group that
-- distinguishes local winners — a candidate "add this to compete here".
--
-- Population: ACTIVE listings only (ANNUAL_REVENUE > 0) that also appear in
-- SILVER.LISTING_AMENITIES, so the coverage % is well-defined and the
-- dormant-listing tail (revenue 0, few amenities) doesn't distort the split.
-- Segment: NTILE(4) by ANNUAL_REVENUE DESC within the area -> quartile 1 is
-- 'top', quartiles 2-4 are 'rest'.
--
-- CAVEAT (document in the app): ASSOCIATIONAL, NOT CAUSAL. Top earners tend
-- to list more amenities partly because they are professionally managed, so
-- a gap is a strong HINT of what to add, not a guaranteed revenue uplift.
-- SUFFICIENT_SAMPLE flags areas too small for the quartile split to be
-- trustworthy (top quartile < 5 or rest < 15 active listings).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_AMENITY_GAP
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready amenity fit-out signal per neighbourhood x amenity_group: coverage among top-revenue-quartile listings vs the rest, and the gap. Active listings only; associational not causal. SUFFICIENT_SAMPLE guards small areas.'
AS
WITH seg AS (
    -- Active listings with amenities, segmented into top revenue quartile vs rest, per area.
    SELECT
        f.LISTING_ID,
        f.NEIGHBOURHOOD,
        CASE WHEN NTILE(4) OVER (PARTITION BY f.NEIGHBOURHOOD ORDER BY f.ANNUAL_REVENUE DESC) = 1
             THEN 'top' ELSE 'rest' END AS segment
    FROM GOLD.FCT_LISTING_SNAPSHOT f
    WHERE f.ANNUAL_REVENUE > 0
      AND EXISTS (SELECT 1 FROM SILVER.LISTING_AMENITIES la WHERE la.LISTING_ID = f.LISTING_ID)
),
seg_size AS (
    SELECT
        NEIGHBOURHOOD,
        COUNT(DISTINCT CASE WHEN segment = 'top'  THEN LISTING_ID END) AS TOP_N,
        COUNT(DISTINCT CASE WHEN segment = 'rest' THEN LISTING_ID END) AS REST_N
    FROM seg
    GROUP BY NEIGHBOURHOOD
),
listing_group AS (
    -- One row per (area, segment, listing, group) the listing offers.
    SELECT DISTINCT s.NEIGHBOURHOOD, s.segment, s.LISTING_ID, la.AMENITY_GROUP
    FROM seg s
    JOIN SILVER.LISTING_AMENITIES la
        ON s.LISTING_ID = la.LISTING_ID
),
grp AS (
    SELECT
        NEIGHBOURHOOD,
        AMENITY_GROUP,
        COUNT(DISTINCT CASE WHEN segment = 'top'  THEN LISTING_ID END) AS TOP_WITH,
        COUNT(DISTINCT CASE WHEN segment = 'rest' THEN LISTING_ID END) AS REST_WITH
    FROM listing_group
    GROUP BY NEIGHBOURHOOD, AMENITY_GROUP
)
SELECT
    g.NEIGHBOURHOOD,
    n.CITY,
    g.AMENITY_GROUP,
    ss.TOP_N,
    ss.REST_N,
    ROUND(g.TOP_WITH  / NULLIF(ss.TOP_N, 0),  4)                                      AS PCT_TOP,
    ROUND(g.REST_WITH / NULLIF(ss.REST_N, 0), 4)                                      AS PCT_REST,
    ROUND(g.TOP_WITH / NULLIF(ss.TOP_N, 0) - g.REST_WITH / NULLIF(ss.REST_N, 0), 4)   AS GAP,
    (ss.TOP_N + ss.REST_N)                                                            AS AREA_ACTIVE_LISTINGS,
    (ss.TOP_N >= 5 AND ss.REST_N >= 15)                                               AS SUFFICIENT_SAMPLE
FROM grp g
JOIN seg_size ss
    ON g.NEIGHBOURHOOD = ss.NEIGHBOURHOOD
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON g.NEIGHBOURHOOD = n.NEIGHBOURHOOD;

-- ============================================================
-- COLUMN COMMENTS
-- ------------------------------------------------------------
-- Per-column documentation for the app marts, kept as COMMENT ON COLUMN
-- (rather than inline column lists) so they can be maintained without
-- re-running the mart bodies. Re-applied on every run AFTER the CREATE OR
-- REPLACE statements above, so they persist across rebuilds. Column names
-- must match the mart projections above.
-- ============================================================
-- ---- MART_AREA_AMENITIES ----
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.AMENITY_GROUP IS 'Curated amenity group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.LISTINGS_WITH_GROUP IS 'Listings offering at least one amenity in the group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.AREA_LISTINGS IS 'Area listings that have any amenities (the denominator).';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITIES.PCT_LISTINGS_WITH_GROUP IS 'Share (0..1) of the area listings offering >=1 amenity in this group.';

-- ---- MART_AREA_AMENITY_GAP ----
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.AMENITY_GROUP IS 'Curated amenity group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.TOP_N IS 'Active listings in the top revenue quartile.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.REST_N IS 'Active listings in revenue quartiles 2-4.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.PCT_TOP IS 'Share (0..1) of top-quartile listings offering the group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.PCT_REST IS 'Share (0..1) of the rest offering the group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.GAP IS 'PCT_TOP minus PCT_REST; positive = winners over-index on this group.';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.AREA_ACTIVE_LISTINGS IS 'Total active listings (TOP_N + REST_N).';
COMMENT ON COLUMN GOLD.MART_AREA_AMENITY_GAP.SUFFICIENT_SAMPLE IS 'TRUE if TOP_N >= 5 AND REST_N >= 15 (quartile split trustworthy).';
