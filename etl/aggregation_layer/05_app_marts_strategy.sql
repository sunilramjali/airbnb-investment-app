-- Builds the GOLD ST-vs-LT yield mart: MART_ST_VS_LT.
-- Co-authored with CoCo
-- ============================================================
-- GOLD - APP MARTS (ST-vs-LT yield). Split out of 03_app_marts.sql.
-- Reads GOLD.MART_LISTING_CANDIDATES + DIM_*/FCT_AREA_* -> run AFTER 03_app_marts_core.sql.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ============================================================
-- MART_ST_VS_LT — grain: CITY x NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET.
-- Single combined grain (no facet collapse): every row is a real
-- (Flat|House) x (1|2|3|4+) cell. Active-only, entire-home.
--
-- BASIS
--   * Active-only: IS_ACTIVE = actively let (est. 30+ booked nights, trailing 12m).
--   * ST income = PURE CAPPED: median(ADR x LEAST(booked nights, city legal cap)).
--       London cap = 90 nights, Manchester/Bristol = 365 (uncapped). No blended
--       "90 ST + rest LT" and no realistic-ceiling view — this is the legally
--       capped, typical-actual ST income only.
--   * LT income: observed ONS rent (bedroom-level, else structure-level) x 12
--       where available, else modelled (sale price x per-city assumed yield).
--   * Sale price: Land Registry per area x structure (shared across bedroom
--       buckets; Land Registry has no bedroom count).
--
-- BENEFIT OF ST (the headline question)
--   ST_VS_LT_INCOME_UPLIFT / _YIELD_UPLIFT_PPT / ST_TO_LT_INCOME_RATIO / ST_WINS
--   quantify ST minus LT. Because ST is cap-aware, London (90-night cap) shows a
--   small or negative uplift — "LT shows that performance" — while uncapped
--   Manchester/Bristol show a large positive uplift. The cap is self-documenting.
--
-- Gross figures only (before mortgage, management, voids, short-let regulation).
-- SUFFICIENT_SAMPLE (n>=5) guards thin cells, which are more common at this finer combined grain.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_ST_VS_LT
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST (Airbnb) vs LT (let) comparison at grain CITY x NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House) x BEDROOM_BUCKET (1/2/3/4+). Active-only (actively let, est. 30+ booked nights trailing 12m). ST income is PURE CAPPED = median ADR x LEAST(booked nights, city legal cap) so London''s 90-night cap is reflected. Columns: ST/LT annual income + gross yield, and benefit-of-ST (ST_VS_LT_INCOME_UPLIFT, ST_VS_LT_YIELD_UPLIFT_PPT, ST_TO_LT_INCOME_RATIO, ST_WINS). Sale price per area x structure (shared across bedroom buckets); LT rent = bedroom ONS -> structure ONS -> modelled. SUFFICIENT_SAMPLE flags thin cells.'
AS
WITH seg_rev AS (
    -- Combined grain: NEIGHBOURHOOD x STRUCTURE_CLASS (Flat/House) x BEDROOM_BUCKET (1/2/3/4+).
    -- Active-only (actively let, est. 30+ booked nights trailing 12m). ST is PURE CAPPED:
    -- ADR x LEAST(booked nights, city legal cap) so London's 90-night cap is baked in.
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
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS a
        ON a.CITY = n.CITY
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')   -- houses & flats only (whole-dwelling universe)
      AND m.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
      AND m.IS_ACTIVE                              -- actively let (est. 30+ booked nights, trailing 12m)
      AND m.ADR IS NOT NULL
      AND m.BEDROOMS >= 1                          -- drop Studio(0) and Unknown(NULL); buckets 1/2/3/4+
    GROUP BY m.NEIGHBOURHOOD, m.STRUCTURE_CLASS, BEDROOM_BUCKET, BEDROOM_SORT,
             COALESCE(a.CAP_NIGHTS, 365), COALESCE(a.ST_COST_PCT, 28), COALESCE(a.LT_COST_PCT, 18)
),
joined AS (
    -- Attach cost basis (sale price: per area x structure, shared across bedroom buckets)
    -- and LT rent (bedroom ONS -> structure ONS -> modelled fallback).
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
    LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON sr.NEIGHBOURHOOD = n.NEIGHBOURHOOD
    LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
        ON c.NEIGHBOURHOOD   = sr.NEIGHBOURHOOD
       AND c.STRUCTURE_CLASS = sr.STRUCTURE_CLASS
    LEFT JOIN GOLD.FCT_AREA_RENT rb
        ON rb.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
       AND rb.CATEGORY_TYPE = 'bedroom'
       AND rb.RENT_CATEGORY = sr.BEDROOM_BUCKET
    LEFT JOIN GOLD.FCT_AREA_RENT rs
        ON rs.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
       AND rs.CATEGORY_TYPE = 'structure'
       AND rs.RENT_CATEGORY = sr.STRUCTURE_CLASS
    LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS y
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
    -- SHORT-TERM (Airbnb), pure capped: median ADR x LEAST(booked nights, city legal cap)
    ROUND(MEDIAN_ST_ANNUAL_REVENUE, 2)                                       AS ST_ANNUAL_INCOME,
    ROUND(MEDIAN_ST_ANNUAL_REVENUE / NULLIF(MEDIAN_SALE_PRICE, 0) * 100, 2)   AS ST_GROSS_YIELD_PCT,
    -- LONG-TERM (let)
    ASSUMED_LT_GROSS_YIELD_PCT,
    LT_ANNUAL_INCOME,
    ROUND(LT_ANNUAL_INCOME / NULLIF(MEDIAN_SALE_PRICE, 0) * 100, 2)           AS LT_GROSS_YIELD_PCT,
    LT_RENT_SOURCE,
    -- BENEFIT OF ST vs LT: London's 90-night cap self-documents here (low/negative uplift
    -- vs the large positive uplift in uncapped Manchester/Bristol).
    ROUND(MEDIAN_ST_ANNUAL_REVENUE - LT_ANNUAL_INCOME, 2)                    AS ST_VS_LT_INCOME_UPLIFT,
    ROUND((MEDIAN_ST_ANNUAL_REVENUE - LT_ANNUAL_INCOME) / NULLIF(MEDIAN_SALE_PRICE, 0) * 100, 2) AS ST_VS_LT_YIELD_UPLIFT_PPT,
    ROUND(MEDIAN_ST_ANNUAL_REVENUE / NULLIF(LT_ANNUAL_INCOME, 0), 2)         AS ST_TO_LT_INCOME_RATIO,
    (MEDIAN_ST_ANNUAL_REVENUE > LT_ANNUAL_INCOME)                            AS ST_WINS,
    (LISTING_COUNT >= 5)                                                     AS SUFFICIENT_SAMPLE
FROM joined;

-- ============================================================
-- COLUMN COMMENTS
-- ------------------------------------------------------------
-- Per-column documentation for the app marts, kept as COMMENT ON COLUMN
-- (rather than inline column lists) so they can be maintained without
-- re-running the mart bodies. Re-applied on every run AFTER the CREATE OR
-- REPLACE statements above, so they persist across rebuilds. Column names
-- must match the mart projections above.
-- ============================================================
-- ---- MART_ST_VS_LT ----
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.STRUCTURE_CLASS IS 'Property type: Flat or House (entire-home, whole-dwelling universe).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.BEDROOM_BUCKET IS 'Bedroom bucket: 1 / 2 / 3 / 4+ (Studio and Unknown excluded).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.BEDROOM_SORT IS 'Sort key 1..4 for BEDROOM_BUCKET (4+ sorts last).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.LISTING_COUNT IS 'Actively-let entire-home Flat/House listings behind the ST income for the CITY x NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET cell.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.OCCUPANCY_CAP_NIGHTS IS 'City short-let LEGAL night cap applied to ST income (London 90, other cities 365 = uncapped).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.MEDIAN_SALE_PRICE IS 'Land Registry median purchase price per area x structure (shared across bedroom buckets; Land Registry has no bedroom count).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ST_ANNUAL_INCOME IS 'Short-term (Airbnb) annual income, PURE CAPPED: median of ADR x LEAST(est. booked nights, city legal cap) over actively-let listings in the cell. London reflects the 90-night cap.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ST_GROSS_YIELD_PCT IS 'Short-term gross yield percent = ST_ANNUAL_INCOME / MEDIAN_SALE_PRICE.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption; used for the modelled LT fallback).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.LT_ANNUAL_INCOME IS 'Long-term gross annual rent: observed ONS PIPR rent x 12 (bedroom-level where available, else structure-level), else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.LT_GROSS_YIELD_PCT IS 'Long-term gross yield percent = LT_ANNUAL_INCOME / MEDIAN_SALE_PRICE. Real when LT_RENT_SOURCE starts with observed.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.LT_RENT_SOURCE IS 'observed_bedroom = ONS bedroom-level rent; observed_structure = ONS structure-level rent; assumed = modelled fallback (no ONS coverage).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ST_VS_LT_INCOME_UPLIFT IS 'Benefit of ST in cash: ST_ANNUAL_INCOME - LT_ANNUAL_INCOME (GBP/yr). Small/negative in London (90-night cap), large positive in uncapped Manchester/Bristol.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ST_VS_LT_YIELD_UPLIFT_PPT IS 'Benefit of ST in yield: ST gross yield minus LT gross yield, in percentage points.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ST_TO_LT_INCOME_RATIO IS 'ST_ANNUAL_INCOME / LT_ANNUAL_INCOME (e.g. 1.8 = ST earns 1.8x long-let). NULL if LT income is 0.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.ST_WINS IS 'TRUE when ST_ANNUAL_INCOME > LT_ANNUAL_INCOME for the cell (before costs).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT.SUFFICIENT_SAMPLE IS 'TRUE if LISTING_COUNT >= 5 (cell large enough to trust the ST median); more cells fall below this at the finer combined grain.';

