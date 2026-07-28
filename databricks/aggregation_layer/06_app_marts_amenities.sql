-- Builds the GOLD amenity marts: MART_AREA_AMENITIES and MART_AREA_AMENITY_GAP.
-- Databricks port of etl/aggregation_layer/06_app_marts_amenities.sql.
-- ============================================================
-- GOLD - APP MARTS (amenities).
-- Reads FCT_*/DIM_*/SILVER only -> order-independent after 03_app_marts_core.sql.
--
-- WHAT CHANGED FROM SNOWFLAKE: DYNAMIC TABLE -> TABLE, TARGET_LAG/WAREHOUSE
-- dropped, three-level names, COMMENT = -> COMMENT.
--
-- ✅ Verified verbatim: NTILE() OVER (PARTITION BY … ORDER BY …), EXISTS
--    correlated subquery, COUNT(DISTINCT CASE WHEN … END), NULLIF, ROUND.
--    This file needed no logic changes at all.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA GOLD;

-- ============================================================
-- MART_AREA_AMENITIES — grain: NEIGHBOURHOOD x AMENITY_GROUP.
-- PCT_LISTINGS_WITH_GROUP = share of the area's listings offering AT LEAST ONE
-- amenity in that group. Long form so the app can facet the pinned boroughs
-- across the ~13 curated groups.
--
-- AREA_LISTINGS is the denominator: DISTINCT listings in the area that have any
-- amenities at all (i.e. appear in LISTING_AMENITIES), so PCT is a clean 0..1.
-- ============================================================
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES
    COMMENT 'App-ready amenity-group coverage per neighbourhood x amenity_group: listings offering >=1 amenity in the group, area listing base, and the coverage percentage. Long form for faceted area comparison.'
AS
WITH area_base AS (
    -- Denominator: distinct listings per area that have any amenities.
    SELECT
        d.NEIGHBOURHOOD,
        COUNT(DISTINCT la.LISTING_ID) AS AREA_LISTINGS
    FROM AIRBNB_INVESTMENT.SILVER.LISTING_AMENITIES la
    JOIN AIRBNB_INVESTMENT.GOLD.DIM_LISTING d
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
    FROM AIRBNB_INVESTMENT.SILVER.LISTING_AMENITIES la
    JOIN AIRBNB_INVESTMENT.GOLD.DIM_LISTING d
        ON la.LISTING_ID = d.LISTING_ID
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
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
-- Within an area, how much more likely are the TOP-earning listings to offer
-- each amenity group than the rest? GAP = PCT_TOP - PCT_REST.
--
-- Population: listings with ANNUAL_REVENUE > 0 that also appear in
-- SILVER.LISTING_AMENITIES. Segment: NTILE(4) by ANNUAL_REVENUE DESC within
-- the area -> quartile 1 is 'top', quartiles 2-4 are 'rest'.
--
-- CAVEAT (document in the app): ASSOCIATIONAL, NOT CAUSAL. Top earners tend to
-- list more amenities partly because they are professionally managed, so a gap
-- is a strong HINT of what to add, not a guaranteed revenue uplift.
-- SUFFICIENT_SAMPLE flags areas too small for the quartile split.
-- ============================================================
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP
    COMMENT 'App-ready amenity fit-out signal per neighbourhood x amenity_group: coverage among top-revenue-quartile listings vs the rest, and the gap. Active listings only; associational not causal. SUFFICIENT_SAMPLE guards small areas.'
AS
WITH seg AS (
    -- NOTE: "active" here = ANNUAL_REVENUE > 0, a DELIBERATELY looser population
    -- than the shared IS_ACTIVE (>=30 booked nights) used by the property and
    -- strategy marts. The gap analysis only needs a revenue signal to RANK
    -- listings within an area, so the wider net keeps more listings for the
    -- quartile split. It is intentionally not the like-for-like investment
    -- universe — do not "fix" this to IS_ACTIVE for consistency.
    SELECT
        f.LISTING_ID,
        f.NEIGHBOURHOOD,
        CASE WHEN NTILE(4) OVER (PARTITION BY f.NEIGHBOURHOOD ORDER BY f.ANNUAL_REVENUE DESC) = 1
             THEN 'top' ELSE 'rest' END AS segment
    FROM AIRBNB_INVESTMENT.GOLD.FCT_LISTING_SNAPSHOT f
    WHERE f.ANNUAL_REVENUE > 0
      AND EXISTS (SELECT 1 FROM AIRBNB_INVESTMENT.SILVER.LISTING_AMENITIES la WHERE la.LISTING_ID = f.LISTING_ID)
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
    JOIN AIRBNB_INVESTMENT.SILVER.LISTING_AMENITIES la
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
    -- ⚠️ RENAMED from AREA_ACTIVE_LISTINGS (Databricks port, 2026-07-28).
    --    "Active" means OCCUPANCY_NIGHTS >= 30 everywhere else in this layer
    --    (the conformed IS_ACTIVE flag, 37,046 listings). The population here is
    --    ANNUAL_REVENUE > 0 — a deliberately looser 47,838, a 29% difference.
    --    Both definitions are defensible; sharing the word "active" between them
    --    was not. Safe rename: no app file reads this mart.
    (ss.TOP_N + ss.REST_N)                                                            AS AREA_RANKED_LISTINGS,
    (ss.TOP_N >= 5 AND ss.REST_N >= 15)                                               AS SUFFICIENT_SAMPLE
FROM grp g
JOIN seg_size ss
    ON g.NEIGHBOURHOOD = ss.NEIGHBOURHOOD
LEFT JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
    ON g.NEIGHBOURHOOD = n.NEIGHBOURHOOD;

-- ============================================================
-- COLUMN COMMENTS — re-applied on every run so they persist across rebuilds.
-- ============================================================
-- ---- MART_AREA_AMENITIES ----
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES.AMENITY_GROUP IS 'Curated amenity group.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES.LISTINGS_WITH_GROUP IS 'Listings offering at least one amenity in the group.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES.AREA_LISTINGS IS 'Area listings that have any amenities (the denominator).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITIES.PCT_LISTINGS_WITH_GROUP IS 'Share (0..1) of the area listings offering >=1 amenity in this group.';

-- ---- MART_AREA_AMENITY_GAP ----
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.AMENITY_GROUP IS 'Curated amenity group.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.TOP_N IS 'Listings in the top revenue quartile. Population is ANNUAL_REVENUE > 0, NOT the conformed IS_ACTIVE (>=30 booked nights) used elsewhere in this layer.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.REST_N IS 'Listings in revenue quartiles 2-4. Same ANNUAL_REVENUE > 0 population as TOP_N.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.PCT_TOP IS 'Share (0..1) of top-quartile listings offering the group.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.PCT_REST IS 'Share (0..1) of the rest offering the group.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.GAP IS 'PCT_TOP minus PCT_REST; positive = winners over-index on this group.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.AREA_RANKED_LISTINGS IS 'Listings ranked for the quartile split (TOP_N + REST_N). Renamed from AREA_ACTIVE_LISTINGS: this population is ANNUAL_REVENUE > 0, which is 29% larger than the conformed IS_ACTIVE (>=30 booked nights) used by the property and strategy marts.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_AREA_AMENITY_GAP.SUFFICIENT_SAMPLE IS 'TRUE if TOP_N >= 5 AND REST_N >= 15 (quartile split trustworthy).';
