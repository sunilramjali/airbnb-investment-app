-- Builds the GOLD property drill-down marts: MART_PROPERTY_TYPE (L1, with buy price), MART_BEDROOMS (L2), MART_PROPERTY_GROUP.
-- Co-authored with CoCo
-- ============================================================
-- GOLD - APP MARTS (property drill-down). Split out of 03_app_marts.sql.
-- Reads GOLD.MART_LISTING_CANDIDATES -> run AFTER 03_app_marts_core.sql.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ============================================================
-- MART_PROPERTY_TYPE — grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House).
-- Level 1 of the property drill-down: pick an area, see Flat vs House
-- operating KPIs PLUS the Land Registry median buy price (valid at this grain
-- because Price Paid carries property type but no bedroom count).
--
-- BASIS: active (IS_ACTIVE = >=30 booked nights), entire-home,
-- Flat/House listings only — the same like-for-like universe as the yield marts,
-- so KPIs here reconcile with MART_AREA_STRATEGY.
-- Source: per-listing rows from GOLD.MART_LISTING_CANDIDATES; sale price from
-- GOLD.FCT_AREA_SALE_PRICE (area x structure). SUFFICIENT_SAMPLE flags thin cells.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_PROPERTY_TYPE
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready level-1 property drill-down: operating KPIs (ADR, occupancy, revenue, rating) per neighbourhood x structure_class (Flat/House, active entire-home) plus Land Registry median buy price. Buy price valid at this grain (structure has a sale comparator).'
AS
WITH base AS (
    SELECT
        m.NEIGHBOURHOOD,
        n.CITY,
        m.STRUCTURE_CLASS,
        m.ADR,
        m.OCCUPANCY_RATE,
        m.ANNUAL_REVENUE,
        m.BEDROOMS,
        m.REVIEW_SCORES_RATING
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')          -- purchasable dwellings only
      AND m.ROOM_TYPE = 'Entire home/apt'                 -- whole property
      AND m.IS_ACTIVE                                     -- active listings only (shared definition)
),
agg AS (
    SELECT
        NEIGHBOURHOOD,
        CITY,
        STRUCTURE_CLASS,
        COUNT(*)                              AS LISTING_COUNT,
        ROUND(AVG(ADR), 2)                    AS AVG_ADR,
        MEDIAN(ADR)                           AS MEDIAN_ADR,
        ROUND(AVG(OCCUPANCY_RATE), 4)         AS AVG_OCCUPANCY_RATE,
        ROUND(AVG(ANNUAL_REVENUE), 2)         AS AVG_ANNUAL_REVENUE,
        MEDIAN(ANNUAL_REVENUE)                AS MEDIAN_ANNUAL_REVENUE,
        ROUND(AVG(BEDROOMS), 2)               AS AVG_BEDROOMS,
        ROUND(AVG(REVIEW_SCORES_RATING), 2)   AS AVG_RATING
    FROM base
    GROUP BY NEIGHBOURHOOD, CITY, STRUCTURE_CLASS
)
SELECT
    a.NEIGHBOURHOOD,
    a.CITY,
    a.STRUCTURE_CLASS,
    a.LISTING_COUNT,
    a.AVG_ADR,
    a.MEDIAN_ADR,
    a.AVG_OCCUPANCY_RATE,
    a.AVG_ANNUAL_REVENUE,
    a.MEDIAN_ANNUAL_REVENUE,
    a.AVG_BEDROOMS,
    a.AVG_RATING,
    c.MEDIAN_SALE_PRICE                       AS MEDIAN_SALE_PRICE,
    c.SALE_TXN_COUNT                          AS SALE_TXN_COUNT,
    (a.LISTING_COUNT >= 5)                    AS SUFFICIENT_SAMPLE
FROM agg a
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = a.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = a.STRUCTURE_CLASS;


-- ============================================================
-- MART_BEDROOMS — grain: NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET.
-- Level 2 of the property drill-down: click a Flat/House on level 1, see the
-- bedroom breakdown with the SAME operating KPIs. NO buy price at this grain —
-- HM Land Registry Price Paid has property type but NO bedroom count, so a
-- bedroom-specific sale price (and therefore a bedroom yield) cannot be derived
-- honestly; buy price stays on MART_PROPERTY_TYPE (structure grain).
--
-- BASIS: identical to MART_PROPERTY_TYPE (active, entire-home, Flat/House).
-- Bedroom cells are sparse (~half have <5 active listings), so CITY_* benchmark
-- columns are provided for graceful fallback and SUFFICIENT_SAMPLE flags thin cells.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_BEDROOMS
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready level-2 property drill-down: operating KPIs per neighbourhood x structure_class x bedroom bucket (active entire-home Flat/House). NO buy price (Land Registry has no bedroom count). Includes CITY_* fallback benchmarks for sparse cells.'
AS
WITH base AS (
    SELECT
        m.NEIGHBOURHOOD,
        n.CITY,
        m.STRUCTURE_CLASS,
        CASE
            WHEN m.BEDROOMS >= 4 THEN '4+'
            ELSE m.BEDROOMS::STRING
        END                                   AS BEDROOM_BUCKET,
        LEAST(m.BEDROOMS, 4)                  AS BEDROOM_SORT,
        m.ADR,
        m.OCCUPANCY_RATE,
        m.ANNUAL_REVENUE,
        m.REVIEW_SCORES_RATING
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')
      AND m.ROOM_TYPE = 'Entire home/apt'
      AND m.IS_ACTIVE
      AND m.BEDROOMS >= 1                                 -- drop Studio (0) and Unknown (NULL); buckets 1/2/3/4+
),
local_agg AS (
    SELECT
        NEIGHBOURHOOD, CITY, STRUCTURE_CLASS, BEDROOM_BUCKET, BEDROOM_SORT,
        COUNT(*)                              AS LISTING_COUNT,
        ROUND(AVG(ADR), 2)                    AS AVG_ADR,
        MEDIAN(ADR)                           AS MEDIAN_ADR,
        ROUND(AVG(OCCUPANCY_RATE), 4)         AS AVG_OCCUPANCY_RATE,
        ROUND(AVG(ANNUAL_REVENUE), 2)         AS AVG_ANNUAL_REVENUE,
        MEDIAN(ANNUAL_REVENUE)                AS MEDIAN_ANNUAL_REVENUE,
        ROUND(AVG(REVIEW_SCORES_RATING), 2)   AS AVG_RATING
    FROM base
    GROUP BY NEIGHBOURHOOD, CITY, STRUCTURE_CLASS, BEDROOM_BUCKET, BEDROOM_SORT
),
-- City x structure x bedroom benchmark for fallback when a local cell is thin.
city_agg AS (
    SELECT
        CITY, STRUCTURE_CLASS, BEDROOM_BUCKET,
        COUNT(*)                              AS CITY_LISTING_COUNT,
        MEDIAN(ADR)                           AS CITY_MEDIAN_ADR,
        ROUND(AVG(OCCUPANCY_RATE), 4)         AS CITY_AVG_OCCUPANCY_RATE,
        MEDIAN(ANNUAL_REVENUE)                AS CITY_MEDIAN_ANNUAL_REVENUE
    FROM base
    GROUP BY CITY, STRUCTURE_CLASS, BEDROOM_BUCKET
)
SELECT
    la.NEIGHBOURHOOD,
    la.CITY,
    la.STRUCTURE_CLASS,
    la.BEDROOM_BUCKET,
    la.BEDROOM_SORT,
    la.LISTING_COUNT,
    la.AVG_ADR,
    la.MEDIAN_ADR,
    la.AVG_OCCUPANCY_RATE,
    la.AVG_ANNUAL_REVENUE,
    la.MEDIAN_ANNUAL_REVENUE,
    la.AVG_RATING,
    ca.CITY_LISTING_COUNT,
    ca.CITY_MEDIAN_ADR,
    ca.CITY_AVG_OCCUPANCY_RATE,
    ca.CITY_MEDIAN_ANNUAL_REVENUE,
    (la.LISTING_COUNT >= 5)                   AS SUFFICIENT_SAMPLE,
    (la.LISTING_COUNT >= 10)                  AS ROBUST_SAMPLE
FROM local_agg la
LEFT JOIN city_agg ca
    ON ca.CITY = la.CITY
   AND ca.STRUCTURE_CLASS = la.STRUCTURE_CLASS
   AND ca.BEDROOM_BUCKET = la.BEDROOM_BUCKET;


-- ============================================================
-- MART_PROPERTY_GROUP — grain: NEIGHBOURHOOD x PROPERTY_GROUP.
-- Property selection screen: pick a neighbourhood, then see each of the
-- 7 property groups. Every (neighbourhood, group) combo is emitted via a
-- scaffold, so groups with no listings in the area still appear
-- (LISTING_COUNT = 0, HAS_LOCAL_DATA = FALSE) instead of vanishing.
--
-- Three tiers of averages, kept as SEPARATE columns so the app never
-- shows a wider figure disguised as a local one:
--   * AVG_*      — true neighbourhood x group average (primary), always
--                  paired with LISTING_COUNT so reliability is visible.
--   * CITY_AVG_* — city x group benchmark (Greater Manchester / Bristol /
--                  London), for fallback when local data is thin/absent.
--   * ALL_AVG_*  — group benchmark across all neighbourhoods.
-- The app shows AVG_* (LISTING_COUNT) as headline and falls back to
-- CITY_AVG_* / ALL_AVG_* with an explicit "wider area" label when
-- HAS_LOCAL_DATA is FALSE or the count is low.
--
-- Median sale-price cost is joined where the group maps to a Land
-- Registry structure (Apartment/Flat -> Flat, House -> House); other
-- groups have no sale-price basis (NULL cost). PROPERTY_GROUP is the
-- selection key; group details live in DIM_PROPERTY_GROUP (normalised).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_PROPERTY_GROUP
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready neighbourhood x property group summary: all 7 groups per neighbourhood with true local averages + count, city and all-areas benchmark averages, HAS_LOCAL_DATA flag, and Land Registry median sale price where the group maps to Flat/House.'
AS
WITH
-- All neighbourhood x group combinations (108 x 7). CITY carried through
-- for the city-level benchmark join and app filtering.
scaffold AS (
    SELECT n.NEIGHBOURHOOD, n.CITY, g.PROPERTY_GROUP
    FROM GOLD.DIM_NEIGHBOURHOOD n
    CROSS JOIN GOLD.DIM_PROPERTY_GROUP g
),
-- Tier 1: true neighbourhood x group aggregates.
local_agg AS (
    SELECT
        m.NEIGHBOURHOOD,
        m.PROPERTY_GROUP,
        COUNT(*)                        AS LISTING_COUNT,
        ROUND(AVG(m.ADR), 2)            AS AVG_ADR,
        MEDIAN(m.ADR)                   AS MEDIAN_ADR,
        ROUND(AVG(m.OCCUPANCY_RATE), 4) AS AVG_OCCUPANCY_RATE,
        ROUND(AVG(m.ANNUAL_REVENUE), 2) AS AVG_ANNUAL_REVENUE,
        MEDIAN(m.ANNUAL_REVENUE)        AS MEDIAN_ANNUAL_REVENUE,
        ROUND(AVG(m.BEDROOMS), 2)       AS AVG_BEDROOMS,
        ROUND(AVG(m.REVIEW_SCORES_RATING), 2) AS AVG_RATING
    FROM GOLD.MART_LISTING_CANDIDATES m
    WHERE m.PROPERTY_GROUP IS NOT NULL
    GROUP BY m.NEIGHBOURHOOD, m.PROPERTY_GROUP
),
-- Tier 2: city x group benchmark (CITY sourced from DIM_NEIGHBOURHOOD).
city_agg AS (
    SELECT
        n.CITY,
        m.PROPERTY_GROUP,
        COUNT(*)                        AS CITY_LISTING_COUNT,
        ROUND(AVG(m.ADR), 2)            AS CITY_AVG_ADR,
        ROUND(AVG(m.OCCUPANCY_RATE), 4) AS CITY_AVG_OCCUPANCY_RATE,
        ROUND(AVG(m.ANNUAL_REVENUE), 2) AS CITY_AVG_ANNUAL_REVENUE
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON m.NEIGHBOURHOOD = n.NEIGHBOURHOOD
    WHERE m.PROPERTY_GROUP IS NOT NULL
    GROUP BY n.CITY, m.PROPERTY_GROUP
),
-- Tier 3: group benchmark across all neighbourhoods.
all_agg AS (
    SELECT
        m.PROPERTY_GROUP,
        COUNT(*)                        AS ALL_LISTING_COUNT,
        ROUND(AVG(m.ADR), 2)            AS ALL_AVG_ADR,
        ROUND(AVG(m.OCCUPANCY_RATE), 4) AS ALL_AVG_OCCUPANCY_RATE,
        ROUND(AVG(m.ANNUAL_REVENUE), 2) AS ALL_AVG_ANNUAL_REVENUE
    FROM GOLD.MART_LISTING_CANDIDATES m
    WHERE m.PROPERTY_GROUP IS NOT NULL
    GROUP BY m.PROPERTY_GROUP
)
SELECT
    s.NEIGHBOURHOOD,
    s.CITY,
    s.PROPERTY_GROUP,
    -- Tier 1: local (primary)
    COALESCE(la.LISTING_COUNT, 0)   AS LISTING_COUNT,
    (COALESCE(la.LISTING_COUNT, 0) > 0) AS HAS_LOCAL_DATA,
    la.AVG_ADR,
    la.MEDIAN_ADR,
    la.AVG_OCCUPANCY_RATE,
    la.AVG_ANNUAL_REVENUE,
    la.MEDIAN_ANNUAL_REVENUE,
    la.AVG_BEDROOMS,
    la.AVG_RATING,
    -- Tier 2: city benchmark
    ca.CITY_LISTING_COUNT,
    ca.CITY_AVG_ADR,
    ca.CITY_AVG_OCCUPANCY_RATE,
    ca.CITY_AVG_ANNUAL_REVENUE,
    -- Tier 3: all-areas benchmark
    aa.ALL_LISTING_COUNT,
    aa.ALL_AVG_ADR,
    aa.ALL_AVG_OCCUPANCY_RATE,
    aa.ALL_AVG_ANNUAL_REVENUE,
    -- Cost benchmark (Flat/House only)
    c.MEDIAN_SALE_PRICE             AS MEDIAN_SALE_PRICE,
    c.SALE_TXN_COUNT                    AS SALE_TXN_COUNT
FROM scaffold s
LEFT JOIN local_agg la
    ON s.NEIGHBOURHOOD = la.NEIGHBOURHOOD
   AND s.PROPERTY_GROUP = la.PROPERTY_GROUP
LEFT JOIN city_agg ca
    ON s.CITY = ca.CITY
   AND s.PROPERTY_GROUP = ca.PROPERTY_GROUP
LEFT JOIN all_agg aa
    ON s.PROPERTY_GROUP = aa.PROPERTY_GROUP
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD = s.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = CASE
           WHEN s.PROPERTY_GROUP = 'Apartment / Flat' THEN 'Flat'
           WHEN s.PROPERTY_GROUP = 'House'            THEN 'House'
       END;


-- ============================================================
-- MART_PROPERTY_SEASONAL — grain: NEIGHBOURHOOD x STRUCTURE_CLASS x
-- BEDROOM_BUCKET x MONTH (1-12).
-- Property page seasonal occupancy chart: for a chosen area, plot the
-- monthly occupancy curve for Flat vs House, with an optional drill into
-- bedroom count. Serves ONE graph, so both views live in one mart:
--   * BEDROOM_BUCKET = 'All'  -> structure-level line (Flat vs House),
--                                bedrooms ignored (incl. studio/unknown).
--   * BEDROOM_BUCKET 1/2/3/4+ -> bedroom drill-down (BEDROOMS >= 1 only).
--
-- BASIS: active (IS_ACTIVE), entire-home, Flat/House listings only — the
-- same like-for-like universe as MART_PROPERTY_TYPE / MART_BEDROOMS.
-- Inactive listings are DELIBERATELY EXCLUDED: they are mostly dormant
-- (host-blocked / delisted) calendars, and because a booked night is only
-- proxied as AVAILABLE = FALSE, their blocked nights masquerade as bookings
-- and would inflate + distort the seasonal curve.
--
-- METRIC: OCCUPANCY_RATE = BOOKED_NIGHTS / TOTAL_NIGHTS per cell, where a
-- booked night is AVAILABLE = FALSE in the calendar (the calendar carries no
-- booked-vs-blocked flag). Occupancy-only by design, matching
-- MART_AREA_SEASONAL (no monthly price exists in the scrape).
--
-- MONTH grain collapses the year (scrape spans ~13 months; boundary month
-- observed across two partial years) — fine for a seasonality shape, not a
-- same-year comparison. Bedroom x month cells are sparse, so SUFFICIENT_SAMPLE
-- flags thin cells (< 5 listings) rather than hiding them.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_PROPERTY_SEASONAL
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready property seasonal occupancy trend per neighbourhood x structure_class (Flat/House) x bedroom bucket x month (1-12): booked/total nights and occupancy rate from calendar availability, active entire-home only. BEDROOM_BUCKET = ''All'' is the structure-level line; 1/2/3/4+ are the bedroom drill-down. Occupancy-only (no monthly price exists). Inactive listings excluded (blocked calendars would inflate occupancy).'
AS
WITH base AS (
    SELECT
        m.NEIGHBOURHOOD,
        n.CITY,
        m.STRUCTURE_CLASS,
        m.BEDROOMS,
        c.LISTING_ID,
        c.CALENDAR_DATE,
        c.AVAILABLE
    FROM GOLD.FCT_CALENDAR_DAILY c
    JOIN GOLD.MART_LISTING_CANDIDATES m
        ON m.LISTING_ID = c.LISTING_ID
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')          -- purchasable dwellings only
      AND m.ROOM_TYPE = 'Entire home/apt'                 -- whole property
      AND m.IS_ACTIVE                                     -- active only (blocked calendars excluded)
),
-- 'All' rollup: structure-level line, bedrooms ignored (incl. studio/unknown).
all_beds AS (
    SELECT
        NEIGHBOURHOOD,
        CITY,
        STRUCTURE_CLASS,
        'All'                                        AS BEDROOM_BUCKET,
        -1                                           AS BEDROOM_SORT,
        MONTH(CALENDAR_DATE)                         AS MONTH,
        COUNT(DISTINCT LISTING_ID)                   AS LISTING_COUNT,
        COUNT(*)                                     AS TOTAL_NIGHTS,
        COUNT(CASE WHEN AVAILABLE = FALSE THEN 1 END) AS BOOKED_NIGHTS
    FROM base
    GROUP BY NEIGHBOURHOOD, CITY, STRUCTURE_CLASS, MONTH(CALENDAR_DATE)
),
-- Bedroom drill-down: buckets 1/2/3/4+ (drop studio 0 and unknown NULL).
by_beds AS (
    SELECT
        NEIGHBOURHOOD,
        CITY,
        STRUCTURE_CLASS,
        CASE WHEN BEDROOMS >= 4 THEN '4+' ELSE BEDROOMS::STRING END AS BEDROOM_BUCKET,
        LEAST(BEDROOMS, 4)                           AS BEDROOM_SORT,
        MONTH(CALENDAR_DATE)                         AS MONTH,
        COUNT(DISTINCT LISTING_ID)                   AS LISTING_COUNT,
        COUNT(*)                                     AS TOTAL_NIGHTS,
        COUNT(CASE WHEN AVAILABLE = FALSE THEN 1 END) AS BOOKED_NIGHTS
    FROM base
    WHERE BEDROOMS >= 1
    GROUP BY NEIGHBOURHOOD, CITY, STRUCTURE_CLASS,
             CASE WHEN BEDROOMS >= 4 THEN '4+' ELSE BEDROOMS::STRING END,
             LEAST(BEDROOMS, 4),
             MONTH(CALENDAR_DATE)
),
unioned AS (
    SELECT * FROM all_beds
    UNION ALL
    SELECT * FROM by_beds
)
SELECT
    NEIGHBOURHOOD,
    CITY,
    STRUCTURE_CLASS,
    BEDROOM_BUCKET,
    BEDROOM_SORT,
    MONTH,
    LISTING_COUNT,
    TOTAL_NIGHTS,
    BOOKED_NIGHTS,
    ROUND(BOOKED_NIGHTS / NULLIF(TOTAL_NIGHTS, 0), 4)  AS OCCUPANCY_RATE,
    (LISTING_COUNT >= 5)                               AS SUFFICIENT_SAMPLE
FROM unioned;

-- ============================================================
-- COLUMN COMMENTS
-- ------------------------------------------------------------
-- Per-column documentation for the app marts, kept as COMMENT ON COLUMN
-- (rather than inline column lists) so they can be maintained without
-- re-running the mart bodies. Re-applied on every run AFTER the CREATE OR
-- REPLACE statements above, so they persist across rebuilds. Column names
-- must match the mart projections above.
-- ============================================================
-- ---- MART_PROPERTY_GROUP ----
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.PROPERTY_GROUP IS 'Property group; grain with neighbourhood and the selection key.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.LISTING_COUNT IS 'Local listings in this area x group (0 if none).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.HAS_LOCAL_DATA IS 'TRUE if the area x group has at least one listing.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_ADR IS 'Local mean nightly rate for the group.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.MEDIAN_ADR IS 'Local median nightly rate.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_OCCUPANCY_RATE IS 'Local mean occupancy (0..1).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_ANNUAL_REVENUE IS 'Local mean annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.MEDIAN_ANNUAL_REVENUE IS 'Local median annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_BEDROOMS IS 'Local mean bedrooms.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.AVG_RATING IS 'Local mean rating.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_LISTING_COUNT IS 'Listings behind the city x group benchmark.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_AVG_ADR IS 'City x group mean nightly rate (fallback benchmark).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_AVG_OCCUPANCY_RATE IS 'City x group mean occupancy.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.CITY_AVG_ANNUAL_REVENUE IS 'City x group mean annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_LISTING_COUNT IS 'Listings behind the all-areas group benchmark.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_AVG_ADR IS 'All-areas group mean nightly rate.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_AVG_OCCUPANCY_RATE IS 'All-areas group mean occupancy.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.ALL_AVG_ANNUAL_REVENUE IS 'All-areas group mean annual revenue.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.MEDIAN_SALE_PRICE IS 'Land Registry median sale price where the group maps to Flat/House (else NULL).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_GROUP.SALE_TXN_COUNT IS 'Number of sale transactions behind MEDIAN_SALE_PRICE.';

-- ---- MART_PROPERTY_SEASONAL ----
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.NEIGHBOURHOOD IS 'Area name; grain key. Read with WHERE NEIGHBOURHOOD = ...';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.CITY IS 'City of the neighbourhood (Greater Manchester / Bristol / London).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.STRUCTURE_CLASS IS 'Dwelling type: Flat or House. Active entire-home listings only.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.BEDROOM_BUCKET IS '''All'' = structure-level line (bedrooms ignored, incl. studio/unknown); ''1''/''2''/''3''/''4+'' = bedroom drill-down (BEDROOMS >= 1). Filter to one value per chart series.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.BEDROOM_SORT IS 'Numeric sort helper: -1 for the ''All'' rollup, else LEAST(BEDROOMS, 4). Order by this for a natural bucket sequence.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.MONTH IS 'Calendar month 1-12 (x-axis of the seasonality chart). Collapses the ~13-month scrape window; a seasonal shape, not a same-year comparison.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.LISTING_COUNT IS 'Distinct listings contributing calendar nights to this cell.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.TOTAL_NIGHTS IS 'Total listing-nights in the calendar for this cell (denominator of OCCUPANCY_RATE).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.BOOKED_NIGHTS IS 'Listing-nights where AVAILABLE = FALSE. Proxy for booked (calendar has no booked-vs-blocked flag).';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.OCCUPANCY_RATE IS 'BOOKED_NIGHTS / TOTAL_NIGHTS (0..1). The seasonal occupancy metric; active-only so blocked dormant calendars do not inflate it.';
COMMENT ON COLUMN GOLD.MART_PROPERTY_SEASONAL.SUFFICIENT_SAMPLE IS 'TRUE if LISTING_COUNT >= 5. Bedroom x month cells are sparse; use to grey out / caveat thin cells.';

