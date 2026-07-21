-- Builds the GOLD ST-vs-LT yield marts: MART_AREA_STRATEGY and MART_AREA_STRATEGY_BEDROOMS.
-- Co-authored with CoCo
-- ============================================================
-- GOLD - APP MARTS (ST-vs-LT yield). Split out of 03_app_marts.sql.
-- Reads GOLD.MART_LISTING_CANDIDATES + DIM_*/FCT_AREA_* -> run AFTER 03_app_marts_core.sql.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ============================================================
-- MART_AREA_STRATEGY — grain: NEIGHBOURHOOD x STRUCTURE_CLASS.
-- Area-COMPARISON screen: short-term (Airbnb) vs long-term (traditional
-- let) investment comparison — the ST-vs-LT grouped bar chart + the basis
-- for the AI-generated ST-vs-LT text (which is produced downstream).
--
-- Both strategies are normalised to GROSS RENTAL YIELD against the Land
-- Registry median purchase price so they sit on one comparable axis:
--     gross yield % = annual rental income / purchase price
--
-- PURCHASE PRICE is normalised PER AREA x STRUCTURE_CLASS (not a blunt
-- area-wide median), matching the house pattern used by MART_LISTING_-
-- CANDIDATES / MART_PROPERTY_GROUP. HM Land Registry PROPERTY_TYPE_CODE is
-- collapsed to the grain the Airbnb side can actually match:
--     F           -> Flat
--     D, S, T     -> House   (Detached / Semi-detached / Terraced)
--     O           -> Other   (commercial / land / non-standard sales)
-- Airbnb listings expose STRUCTURE_CLASS = Flat / House / NULL (hotel,
-- boat, tiny home, ...); NULL is bucketed as 'Other' via COALESCE.
--
-- YIELD_COMPARABLE: TRUE only for Flat / House, where BOTH the Airbnb
-- revenue and the LR price describe the same kind of home. For 'Other'
-- the two sides are unlike (LR 'O' = commercial/land vs Airbnb hotel/boat),
-- so the price is carried as CONTEXT only and every yield column is NULL.
--
--   SHORT-TERM (ST): income = median Airbnb ANNUAL_REVENUE for the
--     (area, structure) segment (scraper estimate, ESTIMATED_REVENUE_L365D).
--
--   LONG-TERM (LT): NO rent dataset is ingested (Land Registry is SALES
--     only). LT annual rent is therefore MODELLED as
--         purchase_price x ASSUMED_LT_GROSS_YIELD_PCT
--     using a per-city assumed gross yield constant. These are documented,
--     configurable ASSUMPTIONS (not observed rents) — approximate market
--     buy-to-let gross yields, city-level:
--         London              4.5%   (high prices -> low yields)
--         Greater Manchester  6.0%   (strong rental yields)
--         Bristol             5.0%
--     Source basis: published UK buy-to-let gross-yield reporting (e.g.
--     Zoopla Rental Market Report / Paragon regional yields). Update the
--     VALUES list when refreshing. Upgrade path: ingest ONS Private Rental
--     Market Statistics for observed rents and replace the assumption.
--
-- CAVEATS (document in the app): ST income = scrape estimates; LT income =
-- assumption; BOTH are GROSS (before mortgage, management, voids, and any
-- short-let regulation). Directional comparison, not a full return model.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_STRATEGY
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST (Airbnb) vs LT (let) yield comparison per neighbourhood x structure_class (Flat/House only). ST revenue basis = active (>=30 booked nights), entire-home listings, capped at the city short-let night limit (London 90). Purchase price normalised per area x structure; all figures gross.'
AS
WITH
-- Short-term (Airbnb) income per area x structure_class.
-- Reads the canonical per-listing mart (MART_LISTING_CANDIDATES) so the
-- active-listing universe (IS_ACTIVE) is defined ONCE and shared with the
-- property marts. City night cap sourced from DIM_CITY_ASSUMPTIONS.
-- BASIS (like-for-like with the whole-dwelling sale price & LT rent):
--   * Flat/House only (purchasable dwellings; 'Other'/guest-accommodation dropped).
--   * Entire home/apt only (whole property, not single-room lets).
--   * Active listings only (IS_ACTIVE, i.e. >=30 booked nights) to exclude the
--     dormant tail that otherwise depresses the median ~4x.
--   * Revenue capped at the city short-let night limit:
--       ADR x LEAST(booked_nights, CAP_NIGHTS).
area_rev AS (
    SELECT
        m.NEIGHBOURHOOD,
        m.STRUCTURE_CLASS,
        COALESCE(a.CAP_NIGHTS, 365)                                                 AS OCCUPANCY_CAP_NIGHTS,
        COUNT(*)                                                                    AS LISTING_COUNT,
        MEDIAN(m.ADR * LEAST(m.OCCUPANCY_NIGHTS, COALESCE(a.CAP_NIGHTS, 365)))       AS MEDIAN_ST_ANNUAL_REVENUE
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS a
        ON a.CITY = n.CITY
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')   -- purchasable dwellings only (drop Other)
      AND m.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like with sale price & LT rent
      AND m.IS_ACTIVE                              -- active listings only (shared definition; >=30 booked nights)
      AND m.ADR IS NOT NULL
    GROUP BY m.NEIGHBOURHOOD, m.STRUCTURE_CLASS, COALESCE(a.CAP_NIGHTS, 365)
)
SELECT
    ar.NEIGHBOURHOOD,
    n.CITY,
    ar.STRUCTURE_CLASS,
    (ar.STRUCTURE_CLASS IN ('Flat', 'House'))                                    AS YIELD_COMPARABLE,
    ar.LISTING_COUNT,
    ar.OCCUPANCY_CAP_NIGHTS,
    c.MEDIAN_SALE_PRICE                                                          AS MEDIAN_SALE_PRICE,
    -- ---- Short-term (Airbnb): active + entire-home, capped at city night limit ----
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END AS ST_GROSS_YIELD_PCT,
    -- ---- Long-term: OBSERVED ONS rent where available, else modelled assumption ----
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS ASSUMED_LT_GROSS_YIELD_PCT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN COALESCE(rr.ANNUAL_RENT,
                       ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0)) END  AS LT_ANNUAL_RENT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(COALESCE(rr.ANNUAL_RENT,
                             c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
                    / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END                              AS LT_GROSS_YIELD_PCT,
    CASE WHEN ar.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN CASE WHEN rr.ANNUAL_RENT IS NOT NULL THEN 'observed' ELSE 'assumed' END END       AS LT_RENT_SOURCE
FROM area_rev ar
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON ar.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = ar.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = ar.STRUCTURE_CLASS
LEFT JOIN GOLD.FCT_AREA_RENT rr
    ON rr.NEIGHBOURHOOD = ar.NEIGHBOURHOOD
   AND rr.CATEGORY_TYPE = 'structure'
   AND rr.RENT_CATEGORY = ar.STRUCTURE_CLASS
LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS y
    ON n.CITY = y.CITY;


-- ============================================================
-- MART_AREA_STRATEGY_BEDROOMS — grain: NEIGHBOURHOOD x STRUCTURE_CLASS x BEDROOM_BUCKET.
-- Like-for-like refinement of MART_AREA_STRATEGY. Segmenting Airbnb
-- income by property size removes the median-depression caused by the
-- large tail of barely-booked listings, so a 2-bed is compared with a
-- 2-bed. Feeds a bedroom-faceted ST-vs-LT grouped bar chart.
--
-- STRUCTURE_CLASS: Flat / House / Other (see MART_AREA_STRATEGY header for
-- the F/D/S/T/O -> Flat/House/Other mapping and the YIELD_COMPARABLE rule).
-- BEDROOM_BUCKET: Studio(0) / 1 / 2 / 3 / 4 / 5+ / Unknown(NULL).
-- BEDROOMS comes from GOLD.DIM_LISTING (already carried up from silver);
-- revenue stays sourced from the FCT_LISTING_SNAPSHOT investment fact.
--
-- PRICE GRANULARITY: purchase price is normalised per AREA x STRUCTURE_CLASS
-- (as in MART_AREA_STRATEGY). It is therefore SHARED across bedroom buckets
-- within a structure — HM Land Registry has property type but NO bedroom
-- count, so a bedroom-specific price is impossible. This is far tighter than
-- a single area-wide price: a 3-bed House yield uses the House price, not a
-- flat-dominated area blend. ST_ANNUAL_REVENUE remains bedroom-specific.
-- YIELD_COMPARABLE is FALSE for 'Other' (yield columns NULL there).
-- All figures GROSS (see MART_AREA_STRATEGY caveats).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_STRATEGY_BEDROOMS
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST-vs-LT yield comparison per neighbourhood x structure_class x bedroom bucket. ST annual revenue is bedroom-specific; purchase price is per area x structure (shared across bedroom buckets); yields only for Flat/House. All figures gross.'
AS
WITH
-- Short-term (Airbnb) income per area x structure_class x bedroom bucket.
-- Same like-for-like basis as MART_AREA_STRATEGY, sourced from the canonical
-- per-listing mart (MART_LISTING_CANDIDATES): Flat/House only, entire-home only,
-- active (IS_ACTIVE) only, revenue capped at the city short-let night limit
-- (cap from DIM_CITY_ASSUMPTIONS). BEDROOMS is carried on the core mart.
seg_rev AS (
    SELECT
        m.NEIGHBOURHOOD,
        m.STRUCTURE_CLASS                                       AS STRUCTURE_CLASS,
        CASE
            WHEN m.BEDROOMS IS NULL THEN 'Unknown'
            WHEN m.BEDROOMS = 0      THEN 'Studio'
            WHEN m.BEDROOMS >= 5     THEN '5+'
            ELSE m.BEDROOMS::STRING
        END                                                     AS BEDROOM_BUCKET,
        CASE
            WHEN m.BEDROOMS IS NULL THEN 99             -- Unknown sorts last
            ELSE LEAST(m.BEDROOMS, 5)
        END                                                     AS BEDROOM_SORT,
        COUNT(*)                    AS LISTING_COUNT,
        MEDIAN(m.ADR * LEAST(m.OCCUPANCY_NIGHTS, COALESCE(a.CAP_NIGHTS, 365))) AS MEDIAN_ST_ANNUAL_REVENUE
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS a
        ON a.CITY = n.CITY
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')   -- purchasable dwellings only (drop Other)
      AND m.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
      AND m.IS_ACTIVE                              -- active listings only (shared definition)
      AND m.ADR IS NOT NULL
    GROUP BY m.NEIGHBOURHOOD, m.STRUCTURE_CLASS, BEDROOM_BUCKET, BEDROOM_SORT
)
SELECT
    sr.NEIGHBOURHOOD,
    n.CITY,
    sr.STRUCTURE_CLASS,
    (sr.STRUCTURE_CLASS IN ('Flat', 'House'))                                    AS YIELD_COMPARABLE,
    sr.BEDROOM_BUCKET,
    sr.BEDROOM_SORT,
    sr.LISTING_COUNT,
    c.MEDIAN_SALE_PRICE                                                          AS MEDIAN_SALE_PRICE,
    -- ---- Short-term (Airbnb), bedroom-specific ----
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END AS ST_GROSS_YIELD_PCT,
    -- ---- Long-term: OBSERVED ONS bedroom-specific rent where available, else modelled ----
    --   ONS bedroom rent is independent of structure_class (ONS does not cross
    --   bedroom x property type), so the same bedroom rent applies to Flat/House
    --   rows; the yield still differs via the structure-specific sale price.
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House') THEN y.ASSUMED_LT_GROSS_YIELD_PCT END    AS ASSUMED_LT_GROSS_YIELD_PCT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN COALESCE(rr.ANNUAL_RENT,
                       ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0)) END  AS LT_ANNUAL_RENT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN ROUND(COALESCE(rr.ANNUAL_RENT,
                             c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
                    / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) END                              AS LT_GROSS_YIELD_PCT,
    CASE WHEN sr.STRUCTURE_CLASS IN ('Flat', 'House')
         THEN CASE WHEN rr.ANNUAL_RENT IS NOT NULL THEN 'observed' ELSE 'assumed' END END       AS LT_RENT_SOURCE
FROM seg_rev sr
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON sr.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = sr.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = sr.STRUCTURE_CLASS
LEFT JOIN GOLD.FCT_AREA_RENT rr
    ON rr.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
   AND rr.CATEGORY_TYPE = 'bedroom'
   AND rr.RENT_CATEGORY = CASE sr.BEDROOM_BUCKET
                              WHEN '1' THEN '1' WHEN '2' THEN '2' WHEN '3' THEN '3'
                               WHEN '4' THEN '4+' WHEN '5+' THEN '4+' END   -- Studio/Unknown -> no match -> assumption
LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS y
    ON n.CITY = y.CITY;


-- ============================================================
-- MART_ST_VS_LT_PROPERTY_TYPE — grain: NEIGHBOURHOOD x STRUCTURE_CLASS.
-- Dedicated ST-vs-LT yield mart faceted by PROPERTY TYPE (Flat / House
-- only). Same basis as MART_AREA_STRATEGY but Flat/House-only by construction,
-- so there is NO YIELD_COMPARABLE flag and NO 'Other'/NULL yield handling —
-- every yield column is always populated. Purchase price is per area x structure.
--
-- THREE ST VIEWS + NET are provided so the ST-vs-LT verdict can be read fairly:
--   * ST_ANNUAL_REVENUE / ST_GROSS_YIELD_PCT     = TYPICAL ACTUAL: median of
--       ADR x LEAST(booked_nights, legal cap). Estimated real performance, capped
--       for legality.
--   * ST_ANNUAL_REVENUE_AT_CAP / _AT_CAP_PCT     = CEILING: median ADR x
--       LEAST(legal cap, REALISTIC_OCC_NIGHTS). London = x90 (conservative:
--       ignores peak-season ADR uplift); uncapped cities = x255 (~70% occupancy,
--       since 365-night full occupancy is unrealistic).
--   * ST_NET_* / LT_NET_*                         = NET: gross x (1 - cost%),
--       using per-city ST_COST_PCT / LT_COST_PCT. Flat per-city cost loads (not
--       segment-specific). NET is the decision-grade view — ST carries a heavier
--       operating drag than LT.
-- All *_GROSS_* figures are gross (see MART_AREA_STRATEGY caveats).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_ST_VS_LT_PROPERTY_TYPE
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST (Airbnb) vs LT (let) yield comparison per neighbourhood x property type (Flat/House only). GROSS + NET yields provided. ST_* = typical-actual (capped); ST_*_AT_CAP = realistic ceiling (median ADR x achievable nights); *_NET_* apply per-city ST/LT cost loads. LT = observed ONS rent where available else modelled. Net costs are flat per-city percentages.'
AS
WITH area_rev AS (
    SELECT
        m.NEIGHBOURHOOD,
        m.STRUCTURE_CLASS,
        COALESCE(a.CAP_NIGHTS, 365)                                           AS OCCUPANCY_CAP_NIGHTS,
        COALESCE(a.REALISTIC_OCC_NIGHTS, 255)                                 AS REALISTIC_OCC_NIGHTS,
        COALESCE(a.ST_COST_PCT, 28)                                           AS ST_COST_PCT,
        COALESCE(a.LT_COST_PCT, 18)                                           AS LT_COST_PCT,
        COUNT(*)                                                              AS LISTING_COUNT,
        MEDIAN(m.ADR * LEAST(m.OCCUPANCY_NIGHTS, COALESCE(a.CAP_NIGHTS, 365))) AS MEDIAN_ST_ANNUAL_REVENUE,
        MEDIAN(m.ADR)                                                         AS MEDIAN_ADR
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS a
        ON a.CITY = n.CITY
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')   -- property type: houses & flats only
      AND m.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
      AND m.IS_ACTIVE                              -- active listings only (shared definition)
      AND m.ADR IS NOT NULL
    GROUP BY m.NEIGHBOURHOOD, m.STRUCTURE_CLASS,
             COALESCE(a.CAP_NIGHTS, 365), COALESCE(a.REALISTIC_OCC_NIGHTS, 255),
             COALESCE(a.ST_COST_PCT, 28), COALESCE(a.LT_COST_PCT, 18)
)
SELECT
    ar.NEIGHBOURHOOD,
    n.CITY,
    ar.STRUCTURE_CLASS,
    ar.LISTING_COUNT,
    ar.OCCUPANCY_CAP_NIGHTS,
    ar.REALISTIC_OCC_NIGHTS,
    c.MEDIAN_SALE_PRICE                                                          AS MEDIAN_SALE_PRICE,
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2)  AS ST_GROSS_YIELD_PCT,
    ROUND(ar.MEDIAN_ADR * LEAST(ar.OCCUPANCY_CAP_NIGHTS, ar.REALISTIC_OCC_NIGHTS), 2) AS ST_ANNUAL_REVENUE_AT_CAP,
    ROUND(ar.MEDIAN_ADR * LEAST(ar.OCCUPANCY_CAP_NIGHTS, ar.REALISTIC_OCC_NIGHTS) / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) AS ST_GROSS_YIELD_AT_CAP_PCT,
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE * (1 - ar.ST_COST_PCT/100.0), 2)            AS ST_NET_ANNUAL_REVENUE,
    ROUND(ar.MEDIAN_ST_ANNUAL_REVENUE * (1 - ar.ST_COST_PCT/100.0) / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) AS ST_NET_YIELD_PCT,
    y.ASSUMED_LT_GROSS_YIELD_PCT                                                 AS ASSUMED_LT_GROSS_YIELD_PCT,
    COALESCE(rr.ANNUAL_RENT,
             ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0))  AS LT_ANNUAL_RENT,
    ROUND(COALESCE(rr.ANNUAL_RENT,
                   c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
          / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2)                             AS LT_GROSS_YIELD_PCT,
    ROUND(COALESCE(rr.ANNUAL_RENT,
                   c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
          * (1 - ar.LT_COST_PCT/100.0), 2)                                      AS LT_NET_ANNUAL_RENT,
    ROUND(COALESCE(rr.ANNUAL_RENT,
                   c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
          * (1 - ar.LT_COST_PCT/100.0)
          / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2)                            AS LT_NET_YIELD_PCT,
    CASE WHEN rr.ANNUAL_RENT IS NOT NULL THEN 'observed' ELSE 'assumed' END       AS LT_RENT_SOURCE,
    (ar.LISTING_COUNT >= 5)                                                      AS SUFFICIENT_SAMPLE
FROM area_rev ar
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON ar.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = ar.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = ar.STRUCTURE_CLASS
LEFT JOIN GOLD.FCT_AREA_RENT rr
    ON rr.NEIGHBOURHOOD = ar.NEIGHBOURHOOD
   AND rr.CATEGORY_TYPE = 'structure'
   AND rr.RENT_CATEGORY = ar.STRUCTURE_CLASS
LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS y
    ON n.CITY = y.CITY;


-- ============================================================
-- MART_ST_VS_LT_BEDROOMS — grain: NEIGHBOURHOOD x BEDROOM_BUCKET (1/2/3/4+).
-- Dedicated ST-vs-LT yield mart faceted by BEDROOM COUNT. Listings are
-- restricted to active entire-home Flat/House dwellings (houses & flats only);
-- Studio(0)/Unknown(NULL) are dropped (BEDROOMS >= 1) and 5+ is folded into 4+.
-- PURCHASE PRICE is the AREA-WIDE median (FCT_AREA_SALE_PRICE STRUCTURE_CLASS =
-- 'All'), because this mart is not split by property type. LT rent = observed
-- ONS bedroom-category rent where available, else modelled.
--
-- Provides typical-actual + ceiling (AT_CAP) + NET ST/LT yields — see
-- MART_ST_VS_LT_PROPERTY_TYPE header for the definitions. NOTE: net costs are a
-- flat per-city % (not bedroom-specific), and the area-wide sale price is shared
-- across bedroom buckets (Land Registry has no bedroom count), so per-bucket
-- yields inherit that denominator caveat.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_ST_VS_LT_BEDROOMS
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready ST (Airbnb) vs LT (let) yield comparison per neighbourhood x bedroom bucket (1/2/3/4+). GROSS + NET yields provided. ST_* = typical-actual (capped); ST_*_AT_CAP = realistic ceiling (median ADR x achievable nights); *_NET_* apply per-city ST/LT cost loads. Purchase price is the area-wide (all-structure) median; LT = observed ONS bedroom rent where available else modelled. Net costs are flat per-city percentages.'
AS
WITH seg_rev AS (
    SELECT
        m.NEIGHBOURHOOD,
        CASE WHEN m.BEDROOMS >= 4 THEN '4+' ELSE m.BEDROOMS::STRING END        AS BEDROOM_BUCKET,
        LEAST(m.BEDROOMS, 4)                                                  AS BEDROOM_SORT,
        COALESCE(a.CAP_NIGHTS, 365)                                           AS OCCUPANCY_CAP_NIGHTS,
        COALESCE(a.REALISTIC_OCC_NIGHTS, 255)                                 AS REALISTIC_OCC_NIGHTS,
        COALESCE(a.ST_COST_PCT, 28)                                           AS ST_COST_PCT,
        COALESCE(a.LT_COST_PCT, 18)                                           AS LT_COST_PCT,
        COUNT(*)                                                              AS LISTING_COUNT,
        MEDIAN(m.ADR * LEAST(m.OCCUPANCY_NIGHTS, COALESCE(a.CAP_NIGHTS, 365))) AS MEDIAN_ST_ANNUAL_REVENUE,
        MEDIAN(m.ADR)                                                         AS MEDIAN_ADR
    FROM GOLD.MART_LISTING_CANDIDATES m
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = m.NEIGHBOURHOOD
    LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS a
        ON a.CITY = n.CITY
    WHERE m.STRUCTURE_CLASS IN ('Flat', 'House')   -- houses & flats only (whole-dwelling universe)
      AND m.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
      AND m.IS_ACTIVE                              -- active listings only (shared definition)
      AND m.ADR IS NOT NULL
      AND m.BEDROOMS >= 1                          -- drop Studio(0) and Unknown(NULL); buckets 1/2/3/4+
    GROUP BY m.NEIGHBOURHOOD, BEDROOM_BUCKET, BEDROOM_SORT,
             COALESCE(a.CAP_NIGHTS, 365), COALESCE(a.REALISTIC_OCC_NIGHTS, 255),
             COALESCE(a.ST_COST_PCT, 28), COALESCE(a.LT_COST_PCT, 18)
)
SELECT
    sr.NEIGHBOURHOOD,
    n.CITY,
    sr.BEDROOM_BUCKET,
    sr.BEDROOM_SORT,
    sr.LISTING_COUNT,
    sr.OCCUPANCY_CAP_NIGHTS,
    sr.REALISTIC_OCC_NIGHTS,
    c.MEDIAN_SALE_PRICE                                                          AS MEDIAN_SALE_PRICE,
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE, 2)                                        AS ST_ANNUAL_REVENUE,
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2)  AS ST_GROSS_YIELD_PCT,
    ROUND(sr.MEDIAN_ADR * LEAST(sr.OCCUPANCY_CAP_NIGHTS, sr.REALISTIC_OCC_NIGHTS), 2) AS ST_ANNUAL_REVENUE_AT_CAP,
    ROUND(sr.MEDIAN_ADR * LEAST(sr.OCCUPANCY_CAP_NIGHTS, sr.REALISTIC_OCC_NIGHTS) / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) AS ST_GROSS_YIELD_AT_CAP_PCT,
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE * (1 - sr.ST_COST_PCT/100.0), 2)            AS ST_NET_ANNUAL_REVENUE,
    ROUND(sr.MEDIAN_ST_ANNUAL_REVENUE * (1 - sr.ST_COST_PCT/100.0) / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2) AS ST_NET_YIELD_PCT,
    y.ASSUMED_LT_GROSS_YIELD_PCT                                                 AS ASSUMED_LT_GROSS_YIELD_PCT,
    COALESCE(rr.ANNUAL_RENT,
             ROUND(c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100, 0))  AS LT_ANNUAL_RENT,
    ROUND(COALESCE(rr.ANNUAL_RENT,
                   c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
          / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2)                             AS LT_GROSS_YIELD_PCT,
    ROUND(COALESCE(rr.ANNUAL_RENT,
                   c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
          * (1 - sr.LT_COST_PCT/100.0), 2)                                      AS LT_NET_ANNUAL_RENT,
    ROUND(COALESCE(rr.ANNUAL_RENT,
                   c.MEDIAN_SALE_PRICE * y.ASSUMED_LT_GROSS_YIELD_PCT / 100)
          * (1 - sr.LT_COST_PCT/100.0)
          / NULLIF(c.MEDIAN_SALE_PRICE, 0) * 100, 2)                            AS LT_NET_YIELD_PCT,
    CASE WHEN rr.ANNUAL_RENT IS NOT NULL THEN 'observed' ELSE 'assumed' END       AS LT_RENT_SOURCE,
    (sr.LISTING_COUNT >= 5)                                                      AS SUFFICIENT_SAMPLE
FROM seg_rev sr
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON sr.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = sr.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = 'All'
LEFT JOIN GOLD.FCT_AREA_RENT rr
    ON rr.NEIGHBOURHOOD = sr.NEIGHBOURHOOD
   AND rr.CATEGORY_TYPE = 'bedroom'
   AND rr.RENT_CATEGORY = sr.BEDROOM_BUCKET
LEFT JOIN GOLD.DIM_CITY_ASSUMPTIONS y
    ON n.CITY = y.CITY;

-- ============================================================
-- COLUMN COMMENTS
-- ------------------------------------------------------------
-- Per-column documentation for the app marts, kept as COMMENT ON COLUMN
-- (rather than inline column lists) so they can be maintained without
-- re-running the mart bodies. Re-applied on every run AFTER the CREATE OR
-- REPLACE statements above, so they persist across rebuilds. Column names
-- must match the mart projections above.
-- ============================================================
-- ---- MART_AREA_STRATEGY ----
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.CITY IS 'City of the neighbourhood.';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.STRUCTURE_CLASS IS 'Flat / House property-type bucket (purchasable dwellings only; Other excluded).';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.YIELD_COMPARABLE IS 'TRUE for all rows (Flat/House); retained for schema stability.';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LISTING_COUNT IS 'Active (>=30 booked nights) entire-home listings behind the ST revenue for the area x structure.';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.OCCUPANCY_CAP_NIGHTS IS 'City short-let night cap applied to ST revenue (London 90, other cities 365 = uncapped).';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.MEDIAN_SALE_PRICE IS 'Land Registry median purchase price for the area x structure.';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.ST_ANNUAL_REVENUE IS 'Median short-term (Airbnb) annual revenue: ADR x LEAST(booked_nights, city cap), over active entire-home Flat/House listings.';
    COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.ST_GROSS_YIELD_PCT IS 'Short-term gross yield percent = ST revenue / sale price.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LT_ANNUAL_RENT IS 'Long-term annual rent: observed ONS PIPR rent x 12 where available, else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LT_GROSS_YIELD_PCT IS 'Long-term gross yield percent = LT_ANNUAL_RENT / median sale price (NULL for Other). Real when LT_RENT_SOURCE=observed.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY.LT_RENT_SOURCE IS 'observed = real ONS PIPR rent; assumed = modelled fallback (no ONS coverage, e.g. City of London). NULL for Other.';

-- ---- MART_AREA_STRATEGY_BEDROOMS ----
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.STRUCTURE_CLASS IS 'Flat / House / Other property-type bucket.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.YIELD_COMPARABLE IS 'TRUE for Flat/House where yields are like-for-like; FALSE for Other.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.BEDROOM_BUCKET IS 'Bedroom bucket: Studio / 1 / 2 / 3 / 4 / 5+ / Unknown.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.BEDROOM_SORT IS 'Sort key for BEDROOM_BUCKET (Unknown sorts last).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LISTING_COUNT IS 'Active listings in the area x structure x bedroom bucket.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.MEDIAN_SALE_PRICE IS 'Area x structure median purchase price (shared across bedroom buckets).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.ST_ANNUAL_REVENUE IS 'Median short-term annual revenue for the bucket (bedroom-specific).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.ST_GROSS_YIELD_PCT IS 'Short-term gross yield percent (NULL for Other).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption).';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LT_ANNUAL_RENT IS 'Long-term annual rent: observed ONS PIPR bedroom-specific rent x 12 where available, else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LT_GROSS_YIELD_PCT IS 'Long-term gross yield percent = LT_ANNUAL_RENT / median sale price (NULL for Other). Real when LT_RENT_SOURCE=observed.';
COMMENT ON COLUMN GOLD.MART_AREA_STRATEGY_BEDROOMS.LT_RENT_SOURCE IS 'observed = real ONS PIPR bedroom rent (independent of structure_class); assumed = modelled fallback (Studio/Unknown/no ONS coverage). NULL for Other.';

-- ---- MART_ST_VS_LT_PROPERTY_TYPE ----
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.STRUCTURE_CLASS IS 'Property type: Flat or House (houses & flats only).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.LISTING_COUNT IS 'Active (>=30 booked nights) entire-home listings behind the ST revenue for the area x property type.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.OCCUPANCY_CAP_NIGHTS IS 'City short-let LEGAL night cap (London 90, other cities 365 = uncapped).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.REALISTIC_OCC_NIGHTS IS 'Realistic achievable ST nights used for the AT_CAP ceiling (London 90, uncapped cities ~70% = 255).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.MEDIAN_SALE_PRICE IS 'Land Registry median purchase price for the area x property type.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ST_ANNUAL_REVENUE IS 'TYPICAL ACTUAL gross ST annual revenue: median of ADR x LEAST(booked_nights, legal cap), over active entire-home listings.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ST_GROSS_YIELD_PCT IS 'Typical-actual GROSS short-term yield percent = ST_ANNUAL_REVENUE / sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ST_ANNUAL_REVENUE_AT_CAP IS 'CEILING gross ST annual revenue = median ADR x LEAST(legal cap, realistic nights). London=x90 (conservative: ignores peak-season ADR uplift); uncapped cities=x255 (~70% occupancy).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ST_GROSS_YIELD_AT_CAP_PCT IS 'Ceiling GROSS short-term yield percent = ST_ANNUAL_REVENUE_AT_CAP / sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ST_NET_ANNUAL_REVENUE IS 'NET ST annual revenue = ST_ANNUAL_REVENUE x (1 - ST_COST_PCT). Flat per-city cost %.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ST_NET_YIELD_PCT IS 'NET short-term yield percent = ST_NET_ANNUAL_REVENUE / sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.LT_ANNUAL_RENT IS 'Long-term gross annual rent: observed ONS PIPR rent x 12 where available, else modelled (sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.LT_GROSS_YIELD_PCT IS 'Long-term GROSS yield percent = LT_ANNUAL_RENT / median sale price. Real when LT_RENT_SOURCE=observed.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.LT_NET_ANNUAL_RENT IS 'NET LT annual rent = LT_ANNUAL_RENT x (1 - LT_COST_PCT). Flat per-city cost %.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.LT_NET_YIELD_PCT IS 'NET long-term yield percent = LT_NET_ANNUAL_RENT / median sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.LT_RENT_SOURCE IS 'observed = real ONS PIPR rent; assumed = modelled fallback (no ONS coverage).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_PROPERTY_TYPE.SUFFICIENT_SAMPLE IS 'TRUE if LISTING_COUNT >= 5 (cell large enough to trust the ST median).';

-- ---- MART_ST_VS_LT_BEDROOMS ----
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.BEDROOM_BUCKET IS 'Bedroom bucket: 1 / 2 / 3 / 4+ (Studio and Unknown excluded; 5+ folded into 4+).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.BEDROOM_SORT IS 'Sort key for BEDROOM_BUCKET (1..4).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.LISTING_COUNT IS 'Active entire-home Flat/House listings in the area x bedroom bucket.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.OCCUPANCY_CAP_NIGHTS IS 'City short-let LEGAL night cap (London 90, other cities 365 = uncapped).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.REALISTIC_OCC_NIGHTS IS 'Realistic achievable ST nights used for the AT_CAP ceiling (London 90, uncapped cities ~70% = 255).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.MEDIAN_SALE_PRICE IS 'Area-wide (all-structure) Land Registry median purchase price; shared across bedroom buckets.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ST_ANNUAL_REVENUE IS 'TYPICAL ACTUAL gross ST annual revenue for the bedroom bucket: median of ADR x LEAST(booked_nights, legal cap).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ST_GROSS_YIELD_PCT IS 'Typical-actual GROSS short-term yield percent = ST_ANNUAL_REVENUE / area-wide sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ST_ANNUAL_REVENUE_AT_CAP IS 'CEILING gross ST annual revenue = median ADR x LEAST(legal cap, realistic nights). London=x90 (conservative: ignores peak-season ADR uplift); uncapped cities=x255 (~70% occupancy).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ST_GROSS_YIELD_AT_CAP_PCT IS 'Ceiling GROSS short-term yield percent = ST_ANNUAL_REVENUE_AT_CAP / area-wide sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ST_NET_ANNUAL_REVENUE IS 'NET ST annual revenue = ST_ANNUAL_REVENUE x (1 - ST_COST_PCT). Costs are a flat per-city % (not bedroom-specific).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ST_NET_YIELD_PCT IS 'NET short-term yield percent = ST_NET_ANNUAL_REVENUE / area-wide sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.ASSUMED_LT_GROSS_YIELD_PCT IS 'Per-city assumed long-term gross yield percent (documented assumption).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.LT_ANNUAL_RENT IS 'Long-term gross annual rent: observed ONS PIPR bedroom-specific rent x 12 where available, else modelled (area-wide sale price x assumed yield). See LT_RENT_SOURCE.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.LT_GROSS_YIELD_PCT IS 'Long-term GROSS yield percent = LT_ANNUAL_RENT / area-wide median sale price. Real when LT_RENT_SOURCE=observed.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.LT_NET_ANNUAL_RENT IS 'NET LT annual rent = LT_ANNUAL_RENT x (1 - LT_COST_PCT). Flat per-city cost %.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.LT_NET_YIELD_PCT IS 'NET long-term yield percent = LT_NET_ANNUAL_RENT / area-wide median sale price.';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.LT_RENT_SOURCE IS 'observed = real ONS PIPR bedroom rent; assumed = modelled fallback (no ONS coverage for the bucket/area).';
COMMENT ON COLUMN GOLD.MART_ST_VS_LT_BEDROOMS.SUFFICIENT_SAMPLE IS 'TRUE if LISTING_COUNT >= 5 (cell large enough to trust the ST median).';

