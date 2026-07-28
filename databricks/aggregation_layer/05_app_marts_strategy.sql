-- Builds the GOLD ST-vs-LT yield mart: MART_ST_VS_LT.
-- Databricks port of etl/aggregation_layer/05_app_marts_strategy.sql.
-- ============================================================
-- GOLD - APP MARTS (ST-vs-LT yield).
-- Reads GOLD.MART_LISTING_CANDIDATES + DIM_*/FCT_AREA_* -> run AFTER 03_app_marts_core.sql.
--
-- WHAT CHANGED FROM SNOWFLAKE: DYNAMIC TABLE -> TABLE, TARGET_LAG/WAREHOUSE
-- dropped, three-level names, COMMENT = -> COMMENT.
--
-- ✅ Verified verbatim: MEDIAN, LEAST, COALESCE, NULLIF, ROUND, the `::STRING`
--    cast, and the doubled apostrophe in the table COMMENT ('London''s').
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA GOLD;

-- ============================================================
-- MART_ST_VS_LT — grain: CITY x NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET.
-- Single combined grain: every row is a real (Flat|House) x (1|2|3|4+) cell.
--
-- BASIS
--   * Active-only: IS_ACTIVE = actively let (est. 30+ booked nights, trailing 12m).
--   * ST income = PURE CAPPED: median(ADR x LEAST(booked nights, city legal cap)).
--       London cap = 90 nights, Manchester/Bristol = 365 (uncapped).
--   * LT income: observed ONS rent (bedroom-level, else structure-level) x 12
--       where available, else modelled (sale price x per-city assumed yield).
--   * Sale price: Land Registry per area x structure (shared across bedroom
--       buckets; Land Registry has no bedroom count).
--
-- Gross figures only. SUFFICIENT_SAMPLE (n>=5) guards thin cells.
-- ============================================================
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT
    COMMENT 'App-ready ST (Airbnb) vs LT (let) comparison at grain CITY x NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House) x BEDROOM_BUCKET (1/2/3/4+). Active-only (actively let, est. 30+ booked nights trailing 12m). ST income is PURE CAPPED = median ADR x LEAST(booked nights, city legal cap) so London''s 90-night cap is reflected. Columns: ST/LT annual income + gross yield, and benefit-of-ST (ST_VS_LT_INCOME_UPLIFT, ST_VS_LT_YIELD_UPLIFT_PPT, ST_TO_LT_INCOME_RATIO, ST_WINS). Sale price per area x structure (shared across bedroom buckets); LT rent = bedroom ONS -> structure ONS -> modelled. SUFFICIENT_SAMPLE flags thin cells.'
AS
WITH seg_rev AS (
    -- Combined grain, active-only. ST is PURE CAPPED: ADR x LEAST(booked nights,
    -- city legal cap) so London's 90-night cap is baked in.
    SELECT
        m.NEIGHBOURHOOD,
        m.STRUCTURE_CLASS,
        CASE WHEN m.BEDROOMS >= 4 THEN '4+' ELSE m.BEDROOMS::STRING END        AS BEDROOM_BUCKET,
        LEAST(m.BEDROOMS, 4)                                                  AS BEDROOM_SORT,
        COALESCE(a.CAP_NIGHTS, 365)                                           AS OCCUPANCY_CAP_NIGHTS,
        COALESCE(a.ST_COST_PCT, 28)                                           AS ST_COST_PCT,
        COALESCE(a.LT_COST_PCT, 18)                                           AS LT_COST_PCT,
        COUNT(*)                                                              AS LISTING_COUNT,
        MEDIAN(m.ADR * LEAST(m.OCCUPANCY_NIGHTS, COALESCE(a.CAP_NIGHTS, 365))) AS MEDIAN_ST_ANNUAL_REVENUE
    FROM AIRBNB_INVESTMENT.GOLD.MART_LISTING_CANDIDATES m
    JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS a
        ON a.CITY = n.CITY
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')   -- whole-dwelling universe
      AND m.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
      AND m.IS_ACTIVE                              -- actively let
      AND m.ADR IS NOT NULL
      AND m.BEDROOMS >= 1                          -- drop Studio(0) and Unknown(NULL)
    GROUP BY m.NEIGHBOURHOOD, m.STRUCTURE_CLASS, BEDROOM_BUCKET, BEDROOM_SORT,
             COALESCE(a.CAP_NIGHTS, 365), COALESCE(a.ST_COST_PCT, 28), COALESCE(a.LT_COST_PCT, 18)
),
joined AS (
    -- Attach cost basis and LT rent (bedroom ONS -> structure ONS -> modelled).
    SELECT
        sr.NEIGHBOURHOOD,
        n.CITY,
        sr.STRUCTURE_CLASS,
        sr.BEDROOM_BUCKET,
        sr.BEDROOM_SORT,
        sr.LISTING_COUNT,
        sr.OCCUPANCY_CAP_NIGHTS,
        sr.ST_COST_PCT,
        sr.LT_COST_PCT,
        sr.MEDIAN_ST_ANNUAL_REVENUE,
        c.MEDIAN_SALE_PRICE,
        y.ASSUMED_LT_GROSS_YIELD_PCT,
        COALESCE(rb.ANNUAL_RENT, rs.ANNUAL_RENT,
                 ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0)) AS LT_ANNUAL_INCOME,
        CASE WHEN rb.ANNUAL_RENT IS NOT NULL THEN 'observed_bedroom'
             WHEN rs.ANNUAL_RENT IS NOT NULL THEN 'observed_structure'
             ELSE 'assumed' END                                              AS LT_RENT_SOURCE
    FROM seg_rev sr
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.DIM_NEIGHBOURHOOD n
        ON sr.NEIGHBOURHOOD = n.NEIGHBOURHOOD
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.FCT_AREA_SALE_PRICE c
        ON c.NEIGHBOURHOOD   = sr.NEIGHBOURHOOD
       AND c.STRUCTURE_CLASS = sr.STRUCTURE_CLASS
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.FCT_AREA_RENT rb
        ON rb.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
       AND rb.CATEGORY_TYPE = 'bedroom'
       AND rb.RENT_CATEGORY = sr.BEDROOM_BUCKET
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.FCT_AREA_RENT rs
        ON rs.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
       AND rs.CATEGORY_TYPE = 'structure'
       AND rs.RENT_CATEGORY = sr.STRUCTURE_CLASS
    LEFT JOIN AIRBNB_INVESTMENT.GOLD.DIM_CITY_ASSUMPTIONS y
        ON n.CITY = y.CITY
)
SELECT
    NEIGHBOURHOOD,
    CITY,
    STRUCTURE_CLASS,
    BEDROOM_BUCKET,
    BEDROOM_SORT,
    LISTING_COUNT,
    OCCUPANCY_CAP_NIGHTS,
    MEDIAN_SALE_PRICE,
    -- SHORT-TERM (Airbnb), pure capped
    ROUND(MEDIAN_ST_ANNUAL_REVENUE, 2)                                       AS ST_ANNUAL_INCOME,
    ROUND(MEDIAN_ST_ANNUAL_REVENUE / NULLIF(MEDIAN_SALE_PRICE, 0) * 100, 2)   AS ST_GROSS_YIELD_PCT,
    -- LONG-TERM (let)
    ASSUMED_LT_GROSS_YIELD_PCT,
    LT_ANNUAL_INCOME,
    ROUND(LT_ANNUAL_INCOME / NULLIF(MEDIAN_SALE_PRICE, 0) * 100, 2)           AS LT_GROSS_YIELD_PCT,
    LT_RENT_SOURCE,
    -- BENEFIT OF ST vs LT: London's 90-night cap self-documents here.
    ROUND(MEDIAN_ST_ANNUAL_REVENUE - LT_ANNUAL_INCOME, 2)                    AS ST_VS_LT_INCOME_UPLIFT,
    ROUND((MEDIAN_ST_ANNUAL_REVENUE - LT_ANNUAL_INCOME) / NULLIF(MEDIAN_SALE_PRICE, 0) * 100, 2) AS ST_VS_LT_YIELD_UPLIFT_PPT,
    ROUND(MEDIAN_ST_ANNUAL_REVENUE / NULLIF(LT_ANNUAL_INCOME, 0), 2)         AS ST_TO_LT_INCOME_RATIO,
    (MEDIAN_ST_ANNUAL_REVENUE > LT_ANNUAL_INCOME)                            AS ST_WINS,
    (LISTING_COUNT >= 5)                                                     AS SUFFICIENT_SAMPLE
FROM joined;

-- ============================================================
-- COLUMN COMMENTS — re-applied on every run so they persist across rebuilds.
-- ============================================================
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.STRUCTURE_CLASS IS 'Property type: Flat or House (entire-home, whole-dwelling universe).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.BEDROOM_BUCKET IS 'Bedroom bucket: 1 / 2 / 3 / 4+ (Studio and Unknown excluded).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.BEDROOM_SORT IS 'Sort key 1..4 for BEDROOM_BUCKET (4+ sorts last).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.LISTING_COUNT IS 'Actively-let entire-home Flat/House listings behind the ST income for the CITY x NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET cell.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.OCCUPANCY_CAP_NIGHTS IS 'City short-let LEGAL night cap applied to ST income (London 90, other cities 365 = uncapped).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.MEDIAN_SALE_PRICE IS 'Land Registry median purchase price per area x structure (shared across bedroom buckets; Land Registry has no bedroom count).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ST_ANNUAL_INCOME IS 'Short-term (Airbnb) annual income, PURE CAPPED: median of ADR x LEAST(est. booked nights, city legal cap) over actively-let listings in the cell. London reflects the 90-night cap.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ST_GROSS_YIELD_PCT IS 'Short-term gross yield percent = ST_ANNUAL_INCOME / MEDIAN_SALE_PRICE.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption; used for the modelled LT fallback).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.LT_ANNUAL_INCOME IS 'Long-term gross annual rent: observed ONS PIPR rent x 12 (bedroom-level where available, else structure-level), else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.LT_GROSS_YIELD_PCT IS 'Long-term gross yield percent = LT_ANNUAL_INCOME / MEDIAN_SALE_PRICE. Real when LT_RENT_SOURCE starts with observed.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.LT_RENT_SOURCE IS 'observed_bedroom = ONS bedroom-level rent; observed_structure = ONS structure-level rent; assumed = modelled fallback (no ONS coverage).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ST_VS_LT_INCOME_UPLIFT IS 'Benefit of ST in cash: ST_ANNUAL_INCOME - LT_ANNUAL_INCOME (GBP/yr). Small/negative in London (90-night cap), large positive in uncapped Manchester/Bristol.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ST_VS_LT_YIELD_UPLIFT_PPT IS 'Benefit of ST in yield: ST gross yield minus LT gross yield, in percentage points.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ST_TO_LT_INCOME_RATIO IS 'ST_ANNUAL_INCOME / LT_ANNUAL_INCOME (e.g. 1.8 = ST earns 1.8x long-let). NULL if LT income is 0.';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.ST_WINS IS 'TRUE when ST_ANNUAL_INCOME > LT_ANNUAL_INCOME for the cell (before costs).';
COMMENT ON COLUMN AIRBNB_INVESTMENT.GOLD.MART_ST_VS_LT.SUFFICIENT_SAMPLE IS 'TRUE if LISTING_COUNT >= 5 (cell large enough to trust the ST median); more cells fall below this at the finer combined grain.';
