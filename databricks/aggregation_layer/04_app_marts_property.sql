-- Builds the GOLD property drill-down marts: MART_PROPERTY_TYPE (L1, with buy price), MART_BEDROOMS (L2), MART_PROPERTY_SEASONAL.
-- Databricks port of etl/aggregation_layer/04_app_marts_property.sql.
-- ============================================================
-- GOLD - APP MARTS (property drill-down).
-- Reads GOLD.MART_LISTING_CANDIDATES -> run AFTER 03_app_marts_core.sql.
--
-- WHAT CHANGED FROM SNOWFLAKE: DYNAMIC TABLE -> TABLE, TARGET_LAG/WAREHOUSE
-- dropped, three-level names, COMMENT = -> COMMENT.
--
-- ✅ Verified verbatim: MEDIAN, LEAST, the `::STRING` cast, MONTH(),
--    COUNT(CASE WHEN … END), NULLIF, UNION ALL, and doubled quotes inside
--    string literals ('''All''').
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA GOLD;

-- ============================================================
-- MART_PROPERTY_TYPE — grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House).
-- Level 1 of the property drill-down: Flat vs House operating KPIs PLUS the
-- Land Registry median buy price (valid at this grain because Price Paid
-- carries property type but no bedroom count).
--
-- BASIS: active (IS_ACTIVE = >=30 booked nights), entire-home, Flat/House only —
-- the same like-for-like universe as the yield marts, so KPIs reconcile.
-- ============================================================
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_TYPE
    COMMENT 'App-ready level-1 property drill-down: operating KPIs (ADR, occupancy, revenue, rating) per neighbourhood x structure_class (Flat/House, active entire-home) plus Land Registry median buy price. Buy price valid at this grain (structure has a sale comparator).'
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
    FROM AIRBNB_INVESTMENT.GOLD.MART_LISTING_CANDIDATES m
    JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')          -- purchasable dwellings only
      AND m.ROOM_TYPE = 'Entire home/apt'                 -- whole property
      AND m.IS_ACTIVE                                     -- active only (shared definition)
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
LEFT JOIN AIRBNB_INVESTMENT.GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = a.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = a.STRUCTURE_CLASS;


-- ============================================================
-- MART_BEDROOMS — grain: NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET.
-- Level 2: bedroom breakdown with the SAME operating KPIs. NO buy price at this
-- grain — Price Paid has property type but NO bedroom count, so a bedroom
-- yield cannot be derived honestly; buy price stays on MART_PROPERTY_TYPE.
--
-- Bedroom cells are sparse (~half have <5 active listings), so CITY_* benchmark
-- columns give a graceful fallback and SUFFICIENT_SAMPLE flags thin cells.
-- ============================================================
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.MART_BEDROOMS
    COMMENT 'App-ready level-2 property drill-down: operating KPIs per neighbourhood x structure_class x bedroom bucket (active entire-home Flat/House). NO buy price (Land Registry has no bedroom count). Includes CITY_* fallback benchmarks for sparse cells.'
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
    FROM AIRBNB_INVESTMENT.GOLD.MART_LISTING_CANDIDATES m
    JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')
      AND m.ROOM_TYPE = 'Entire home/apt'
      AND m.IS_ACTIVE
      AND m.BEDROOMS >= 1                                 -- drop Studio (0) and Unknown (NULL)
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
-- MART_PROPERTY_SEASONAL — grain: NEIGHBOURHOOD x STRUCTURE_CLASS x
-- BEDROOM_BUCKET x MONTH (1-12). Serves ONE graph, so both views live in one mart:
--   * BEDROOM_BUCKET = 'All'  -> structure-level line, bedrooms ignored.
--   * BEDROOM_BUCKET 1/2/3/4+ -> bedroom drill-down (BEDROOMS >= 1 only).
--
-- Inactive listings are DELIBERATELY EXCLUDED: they are mostly dormant
-- (host-blocked / delisted) calendars, and because a booked night is only
-- proxied as AVAILABLE = FALSE, their blocked nights masquerade as bookings and
-- would inflate + distort the seasonal curve.
-- ============================================================
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL
    COMMENT 'App-ready property seasonal occupancy trend per neighbourhood x structure_class (Flat/House) x bedroom bucket x month (1-12): booked/total nights and occupancy rate from calendar availability, active entire-home only. BEDROOM_BUCKET = ''All'' is the structure-level line; 1/2/3/4+ are the bedroom drill-down. Occupancy-only (no monthly price exists). Inactive listings excluded (blocked calendars would inflate occupancy).'
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
    FROM AIRBNB_INVESTMENT.GOLD.FCT_CALENDAR_DAILY c
    JOIN AIRBNB_INVESTMENT.GOLD.MART_LISTING_CANDIDATES m
        ON m.LISTING_ID = c.LISTING_ID
    JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')          -- purchasable dwellings only
      AND m.ROOM_TYPE = 'Entire home/apt'                 -- whole property
      AND m.IS_ACTIVE                                     -- active only
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
-- COLUMN COMMENTS — re-applied on every run so they persist across rebuilds.
-- ⚠️ Faithful to the original: only MART_PROPERTY_SEASONAL is documented here.
--    MART_PROPERTY_TYPE and MART_BEDROOMS carry table-level comments only.
-- ============================================================
-- ---- MART_PROPERTY_SEASONAL ----
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.NEIGHBOURHOOD IS 'Area name; grain key. Read with WHERE NEIGHBOURHOOD = ...';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.CITY IS 'City of the neighbourhood (Greater Manchester / Bristol / London).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.STRUCTURE_CLASS IS 'Dwelling type: Flat or House. Active entire-home listings only.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.BEDROOM_BUCKET IS '''All'' = structure-level line (bedrooms ignored, incl. studio/unknown); ''1''/''2''/''3''/''4+'' = bedroom drill-down (BEDROOMS >= 1). Filter to one value per chart series.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.BEDROOM_SORT IS 'Numeric sort helper: -1 for the ''All'' rollup, else LEAST(BEDROOMS, 4). Order by this for a natural bucket sequence.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.MONTH IS 'Calendar month 1-12 (x-axis of the seasonality chart). Collapses the ~13-month scrape window; a seasonal shape, not a same-year comparison.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.LISTING_COUNT IS 'Distinct listings contributing calendar nights to this cell.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.TOTAL_NIGHTS IS 'Total listing-nights in the calendar for this cell (denominator of OCCUPANCY_RATE).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.BOOKED_NIGHTS IS 'Listing-nights where AVAILABLE = FALSE. Proxy for booked (calendar has no booked-vs-blocked flag).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.OCCUPANCY_RATE IS 'BOOKED_NIGHTS / TOTAL_NIGHTS (0..1). The seasonal occupancy metric; active-only so blocked dormant calendars do not inflate it.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_PROPERTY_SEASONAL.SUFFICIENT_SAMPLE IS 'TRUE if LISTING_COUNT >= 5. Bedroom x month cells are sparse; use to grey out / caveat thin cells.';
