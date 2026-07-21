-- Builds the GOLD ST-vs-LT yield marts: MART_AREA_STRATEGY and MART_AREA_STRATEGY_BEDROOMS.
-- Co-authored with CoCo
-- ============================================================
-- GOLD - APP MARTS (ST-vs-LT yield). Split out of 03_app_marts.sql.
-- Reads FCT_*/DIM_* only -> order-independent after 03_app_marts_core.sql.
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
-- Per-city legal cap on short-let nights (entire-home planning rule).
-- London = 90 nights/yr (deemed planning permission limit); other cities uncapped (365).
occ_cap AS (
    SELECT column1 AS CITY, column2 AS CAP_NIGHTS
    FROM VALUES
        ('London',             90),
        ('Greater Manchester', 365),
        ('Bristol',            365)
),
-- Short-term (Airbnb) income per area x structure_class.
-- BASIS (like-for-like with the whole-dwelling sale price & LT rent):
--   * Flat/House only (purchasable dwellings; 'Other'/guest-accommodation dropped).
--   * Entire home/apt only (whole property, not single-room lets).
--   * Active listings only (>=30 booked nights) to exclude the dormant tail
--     that otherwise depresses the median ~4x.
--   * Revenue capped at the city short-let night limit:
--       ADR x LEAST(booked_nights, CAP_NIGHTS).
area_rev AS (
    SELECT
        f.NEIGHBOURHOOD,
        f.STRUCTURE_CLASS,
        COALESCE(cap.CAP_NIGHTS, 365)                                               AS OCCUPANCY_CAP_NIGHTS,
        COUNT(*)                                                                    AS LISTING_COUNT,
        MEDIAN(f.ADR * LEAST(f.OCCUPANCY_NIGHTS, COALESCE(cap.CAP_NIGHTS, 365)))     AS MEDIAN_ST_ANNUAL_REVENUE
    FROM GOLD.FCT_LISTING_SNAPSHOT f
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = f.NEIGHBOURHOOD
    LEFT JOIN occ_cap cap
        ON cap.CITY = n.CITY
    WHERE f.STRUCTURE_CLASS IN ('Flat', 'House')   -- purchasable dwellings only (drop Other)
      AND f.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like with sale price & LT rent
      AND f.OCCUPANCY_NIGHTS >= 30                 -- active listings only (exclude dormant tail)
      AND f.ADR IS NOT NULL
    GROUP BY f.NEIGHBOURHOOD, f.STRUCTURE_CLASS, COALESCE(cap.CAP_NIGHTS, 365)
),
-- Per-city assumed long-term GROSS rental yield (documented assumption).
lt_yield AS (
    SELECT column1 AS CITY, column2 AS ASSUMED_LT_GROSS_YIELD_PCT
    FROM VALUES
        ('London',             4.5),
        ('Greater Manchester', 6.0),
        ('Bristol',            5.0)
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
LEFT JOIN lt_yield y
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
-- Per-city legal cap on short-let nights (entire-home planning rule); London 90, else uncapped.
occ_cap AS (
    SELECT column1 AS CITY, column2 AS CAP_NIGHTS
    FROM VALUES
        ('London',             90),
        ('Greater Manchester', 365),
        ('Bristol',            365)
),
-- Short-term (Airbnb) income per area x structure_class x bedroom bucket.
-- Same like-for-like basis as MART_AREA_STRATEGY: Flat/House only, entire-home only,
-- active (>=30 booked nights) only, revenue capped at the city short-let night limit.
seg_rev AS (
    SELECT
        f.NEIGHBOURHOOD,
        f.STRUCTURE_CLASS                                       AS STRUCTURE_CLASS,
        CASE
            WHEN d.BEDROOMS IS NULL THEN 'Unknown'
            WHEN d.BEDROOMS = 0      THEN 'Studio'
            WHEN d.BEDROOMS >= 5     THEN '5+'
            ELSE d.BEDROOMS::STRING
        END                                                     AS BEDROOM_BUCKET,
        CASE
            WHEN d.BEDROOMS IS NULL THEN 99             -- Unknown sorts last
            ELSE LEAST(d.BEDROOMS, 5)
        END                                                     AS BEDROOM_SORT,
        COUNT(*)                    AS LISTING_COUNT,
        MEDIAN(f.ADR * LEAST(f.OCCUPANCY_NIGHTS, COALESCE(cap.CAP_NIGHTS, 365))) AS MEDIAN_ST_ANNUAL_REVENUE
    FROM GOLD.FCT_LISTING_SNAPSHOT f
    JOIN GOLD.DIM_LISTING d
        ON f.LISTING_ID = d.LISTING_ID
    JOIN GOLD.DIM_NEIGHBOURHOOD n
        ON n.NEIGHBOURHOOD = f.NEIGHBOURHOOD
    LEFT JOIN occ_cap cap
        ON cap.CITY = n.CITY
    WHERE f.STRUCTURE_CLASS IN ('Flat', 'House')   -- purchasable dwellings only (drop Other)
      AND f.ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
      AND f.OCCUPANCY_NIGHTS >= 30                 -- active listings only
      AND f.ADR IS NOT NULL
    GROUP BY f.NEIGHBOURHOOD, f.STRUCTURE_CLASS, BEDROOM_BUCKET, BEDROOM_SORT
),
lt_yield AS (
    SELECT column1 AS CITY, column2 AS ASSUMED_LT_GROSS_YIELD_PCT
    FROM VALUES
        ('London',             4.5),
        ('Greater Manchester', 6.0),
        ('Bristol',            5.0)
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
LEFT JOIN lt_yield y
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

