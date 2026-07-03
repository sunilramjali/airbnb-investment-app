-- Builds the GOLD facts: FCT_CALENDAR_DAILY (listing x date base), FCT_LISTING_SNAPSHOT (per-listing investment metrics), and FCT_LISTING_POI (per-listing POI proximity).
-- Co-authored with CoCo
-- ============================================================
-- GOLD — FACTS
-- ------------------------------------------------------------
-- Single-schema aggregation layer: the whole star + consumer objects
-- live in GOLD, distinguished by name prefix (DIM_/FCT_/AGG_/MART_/
-- VW_/FEATURE_). The GOLD schema is created by the setup layer
-- (setup/01_setup_database_and_warehouse.sql).
--
-- FCT_CALENDAR_DAILY   : grain listing x date. Lean projection of
--                        SILVER.CALENDAR_CLEANED (39M rows) kept
--                        incremental-friendly (no window fns).
--
-- FCT_LISTING_SNAPSHOT : grain listing. The investment-metrics fact.
--                        v1 uses the scraper's pre-computed
--                        ESTIMATED_OCCUPANCY_L365D / ESTIMATED_REVENUE_L365D
--                        (sidesteps the calendar booked-vs-blocked
--                        ambiguity). ADR = nightly PRICE.
--
-- FCT_LISTING_POI      : grain listing. POI proximity computed
--                        SEPARATELY from the snapshot so the expensive
--                        spatial join doesn't slow snapshot refresh.
--                        Bounded ST_DWITHIN (500m) join DIM_LISTING x DIM_POI.
--
-- Metrics:
--   OCCUPANCY_RATE = ESTIMATED_OCCUPANCY_L365D / 365
--   ANNUAL_REVENUE = ESTIMATED_REVENUE_L365D
--   REVPAR         = ANNUAL_REVENUE / 365
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ------------------------------------------------------------
-- FCT_CALENDAR_DAILY — daily availability/price per listing.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_CALENDAR_DAILY
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Daily availability & price per listing (grain: listing x date). Lean incremental projection of SILVER.CALENDAR_CLEANED.'
AS
SELECT
    LISTING_ID,
    CALENDAR_DATE,
    AVAILABLE,
    ADJUSTED_PRICE,
    MINIMUM_NIGHTS,
    MAXIMUM_NIGHTS
FROM SILVER.CALENDAR_CLEANED;

-- ------------------------------------------------------------
-- FCT_LISTING_SNAPSHOT — per-listing investment metrics.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_LISTING_SNAPSHOT
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'Per-listing investment metrics: ADR, occupancy rate, annual revenue, RevPAR. v1 uses scraper estimates.'
AS
SELECT
    LISTING_ID,
    HOST_ID,
    NEIGHBOURHOOD,
    NEIGHBOURHOOD_GROUP,
    ROOM_TYPE,
    STRUCTURE_CLASS,
    GEO_POINT,
    PRICE                                              AS ADR,
    ESTIMATED_OCCUPANCY_L365D                          AS OCCUPANCY_NIGHTS,
    ROUND(ESTIMATED_OCCUPANCY_L365D / 365.0, 4)        AS OCCUPANCY_RATE,
    ESTIMATED_REVENUE_L365D                            AS ANNUAL_REVENUE,
    ROUND(ESTIMATED_REVENUE_L365D / 365.0, 2)          AS REVPAR,
    REVIEW_SCORES_RATING,
    NUMBER_OF_REVIEWS
FROM GOLD.DIM_LISTING;

-- ------------------------------------------------------------
-- FCT_LISTING_POI — proximity features (bounded 500m spatial join).
-- Separate from the snapshot to keep that refresh cheap.
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE GOLD.FCT_LISTING_POI
    TARGET_LAG = '1 day'
    WAREHOUSE  = COMPUTE_WH
    COMMENT    = 'POI proximity per listing: count of POIs within 500m, overall and for transport. Bounded ST_DWITHIN join.'
AS
SELECT
    l.LISTING_ID,
    COUNT(p.NAME)                                                       AS POI_COUNT_500M,
    COUNT(CASE WHEN p.CATEGORY ILIKE ANY ('%station%','%bus%','%transit%','%subway%','%tram%')
               THEN 1 END)                                              AS TRANSPORT_COUNT_500M,
    COUNT(CASE WHEN p.AMENITY_GROUP ILIKE '%dining%' THEN 1 END)        AS DINING_COUNT_500M
FROM GOLD.DIM_LISTING l
LEFT JOIN GOLD.DIM_POI p
    ON ST_DWITHIN(l.GEO_POINT, p.LOCATION, 500)
GROUP BY l.LISTING_ID;
