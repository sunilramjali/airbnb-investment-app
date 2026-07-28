-- Builds SILVER.LISTING_AMENITIES: explodes the listings amenities JSON array into one row per (listing, amenity) and classifies each into a curated AMENITY_GROUP.
-- Databricks port of etl/cleaning_layer/11_silver_amenities.sql.
-- ============================================================
-- SILVER — LISTING AMENITIES EXTRACTION + GROUPING
-- ------------------------------------------------------------
-- Reads SILVER.LISTINGS_CLEANED.AMENITIES (a JSON-array TEXT blob like
-- ["Wifi","Kitchen","Free parking on premises",...]) and produces a long,
-- exploded table at the grain of one row per (listing_id, amenity).
--
-- Why: the raw amenities live as an unparsed string in silver and were
-- dropped entirely in gold. Airbnb hosts free-type amenities, so the raw
-- vocabulary is huge (~10.7k distinct strings, >half appearing once, e.g.
-- "KitchenAid oven", "Harman & Kardon Bluetooth sound system"). This table
-- makes amenities queryable and collapses that noise into ~12 curated
-- AMENITY_GROUPs so downstream can count/compare amenity coverage per
-- listing or per area.
--
-- Principles (unchanged):
--   * Explode over TRY_PARSE_JSON: bad/NULL JSON simply yields no rows
--     (no error). One output row per array element.
--   * BASE_TYPE = the amenity text before a ':' or ' – ' qualifier
--     (e.g. "Clothing storage: wardrobe" -> "Clothing storage").
--   * AMENITY_GROUP via a CURATED CASE, keyword-matched on the LOWERCASED
--     raw amenity, FIRST-MATCH-WINS. Order is deliberate to resolve
--     overlaps: 'dishwasher' must beat laundry '%washer%'; 'hair dryer'
--     must beat laundry '%dryer%'; 'hot water kettle' must beat bathroom
--     '%hot water%'; 'air conditioner' must NOT be caught by bathroom
--     '%conditioner%' (guarded). Unmatched -> 'Other'.
--   * Validate: drop rows with no usable listing_id or blank amenity.
--   * Deduplicate to one row per (listing_id, raw_amenity); latest load wins.
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE — one line, and three things that did NOT
-- ------------------------------------------------------------
--   LATERAL FLATTEN(input => TRY_PARSE_JSON(x)) -> LATERAL variant_explode(try_parse_json(x))
--
-- Everything else in this file was verified to port verbatim (2026-07-28):
--
-- ✅ try_parse_json EXISTS and behaves identically — returns NULL on bad JSON
--    rather than raising. That is load-bearing: it is the only reason a listing
--    with a malformed amenities blob yields no rows instead of failing the run.
--
-- ✅ f.value::string DOES NOT KEEP THE JSON QUOTES.
--    Verified: variant_explode(parse_json('["Wifi"]')) -> 'Wifi', length 4.
--    Worth checking rather than assuming — had it returned '"Wifi"' (length 6),
--    EVERY LIKE pattern in the CASE below would silently fail to match and all
--    ~4M rows would classify as 'Other'. The table would look fine.
--
-- ✅ SPLIT_PART is 1-indexed and handles the EN DASH delimiter ' – ' (U+2013),
--    not just the ASCII hyphen. Verified on both ':' and ' – '.
--
-- ✅ The ordered CASE, the LIKE guards, and QUALIFY all port unchanged.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.LISTING_AMENITIES AS
WITH exploded AS (
    SELECT
        l.LISTING_ID                                          AS listing_id,
        TRIM(f.value::string)                                 AS raw_amenity,
        TRIM(SPLIT_PART(SPLIT_PART(f.value::string, ':', 1), ' – ', 1)) AS base_type,
        l._LOAD_TS                                            AS _LOAD_TS
    FROM AIRBNB_INVESTMENT.SILVER.LISTINGS_CLEANED l,
         LATERAL variant_explode(try_parse_json(l.AMENITIES)) f
    WHERE l.LISTING_ID IS NOT NULL
),
grouped AS (
    SELECT
        e.listing_id,
        e.raw_amenity,
        e.base_type,
        -- ---- curated group: first matching branch wins; NULL => 'Other' ----
        CASE
            -- Parking & EV (before anything generic)
            WHEN a LIKE '%parking%' OR a LIKE '%ev charger%' OR a LIKE '%electric vehicle%'
                THEN 'Parking & EV'
            -- Safety & Security
            WHEN a LIKE '%smoke alarm%' OR a LIKE '%carbon monoxide%' OR a LIKE '%fire extinguisher%'
                 OR a LIKE '%first aid%' OR a LIKE '%lockbox%' OR a LIKE '%smart lock%'
                 OR a LIKE '%keypad%' OR a LIKE '%security camera%' OR a LIKE '%lock on%'
                 OR a LIKE '%safe%' OR a LIKE '%security%'
                 OR a LIKE '%window guard%' OR a LIKE '%noise%monitor%' OR a LIKE '%outlet cover%'
                THEN 'Safety & Security'
            -- Kitchen & Dining (consumes 'dishwasher' and 'hot water kettle')
            WHEN a LIKE '%kitchen%' OR a LIKE '%oven%' OR a LIKE '%stove%' OR a LIKE '%refrigerator%'
                 OR a LIKE '%fridge%' OR a LIKE '%freezer%' OR a LIKE '%microwave%' OR a LIKE '%dishwasher%'
                 OR a LIKE '%dishes%' OR a LIKE '%silverware%' OR a LIKE '%cutlery%' OR a LIKE '%cookware%'
                 OR a LIKE '%cooking%' OR a LIKE '%coffee%' OR a LIKE '%kettle%' OR a LIKE '%toaster%'
                 OR a LIKE '%blender%' OR a LIKE '%dining%' OR a LIKE '%wine glass%' OR a LIKE '%glassware%'
                 OR a LIKE '%baking%' OR a LIKE '%rice maker%' OR a LIKE '%bread maker%' OR a LIKE '%barbecue utensils%'
                 OR a LIKE '%trash compactor%'
                THEN 'Kitchen & Dining'
            -- Bathroom & Toiletries (before Laundry so 'hair dryer' isn't a 'dryer';
            -- conditioner guarded so 'air conditioner' falls through to Comfort)
            WHEN a LIKE '%hair dryer%' OR a LIKE '%shampoo%' OR a LIKE '%body soap%' OR a LIKE '%shower gel%'
                 OR a LIKE '%soap%' OR a LIKE '%bathtub%' OR a LIKE '%bidet%' OR a LIKE '%toiletr%'
                 OR a LIKE '%hot water%' OR (a LIKE '%conditioner%' AND a NOT LIKE '%air%')
                THEN 'Bathroom & Toiletries'
            -- Laundry & Cleaning
            WHEN a LIKE '%washer%' OR a LIKE '%dryer%' OR a LIKE 'iron%' OR a LIKE '% iron%'
                 OR a LIKE '%drying rack%' OR a LIKE '%laundr%' OR a LIKE '%cleaning products%'
                THEN 'Laundry'
            -- Connectivity & Entertainment
            WHEN a LIKE '%wifi%' OR a LIKE '%ethernet%' OR a LIKE '%internet%' OR a LIKE '%tv%'
                 OR a LIKE '%hdtv%' OR a LIKE '%television%' OR a LIKE '%sound system%' OR a LIKE '%speaker%'
                 OR a LIKE '%bluetooth%' OR a LIKE '%game%' OR a LIKE '%books%' OR a LIKE '%cable%'
                 OR a LIKE '%netflix%' OR a LIKE '%streaming%' OR a LIKE '%record player%'
                 OR a LIKE '%pool table%' OR a LIKE '%ping pong%' OR a LIKE '%piano%'
                THEN 'Connectivity & Entertainment'
            -- Bedroom & Comfort (air conditioning / heating / fans / linens)
            WHEN a LIKE '%air condition%' OR a LIKE '%heating%' OR a LIKE '%heater%' OR a LIKE '%fan%'
                 OR a LIKE '%bed linens%' OR a LIKE '%hangers%' OR a LIKE '%clothing storage%'
                 OR a LIKE '%wardrobe%' OR a LIKE '%closet%' OR a LIKE '%pillows%' OR a LIKE '%blankets%'
                 OR a LIKE '%room-darkening%' OR a LIKE '%blackout%' OR a LIKE '%essentials%' OR a LIKE '%mattress%'
                THEN 'Bedroom & Comfort'
            -- Family & Kids
            WHEN a LIKE '%crib%' OR a LIKE '%high chair%' OR a LIKE '%pack ’n play%' OR a LIKE '%pack n play%'
                 OR a LIKE '%travel crib%' OR a LIKE '%children%' OR a LIKE '%baby%' OR a LIKE '%kids%'
                 OR a LIKE '%toys%' OR a LIKE '%changing table%'
                THEN 'Family & Kids'
            -- Accessibility
            WHEN a LIKE '%elevator%' OR a LIKE '%single level%' OR a LIKE '%step-free%'
                 OR a LIKE '%wheelchair%' OR a LIKE '%accessible%' OR a LIKE '%wide entrance%'
                 OR a LIKE '%wide hallway%'
                THEN 'Accessibility'
            -- Wellness & Leisure (pool guarded against 'pool table')
            WHEN (a LIKE '%pool%' AND a NOT LIKE '%pool table%') OR a LIKE '%hot tub%' OR a LIKE '%sauna%'
                 OR a LIKE '%gym%' OR a LIKE '%exercise%' OR a LIKE '%fitness%' OR a LIKE '%fireplace%'
                 OR a LIKE '%jacuzzi%' OR a LIKE '%spa%'
                THEN 'Wellness & Leisure'
            -- Outdoor & Views
            WHEN a LIKE '%backyard%' OR a LIKE '%patio%' OR a LIKE '%balcony%' OR a LIKE '%bbq%'
                 OR a LIKE '%barbecue%' OR a LIKE '%grill%' OR a LIKE '%garden%' OR a LIKE '%view%'
                 OR a LIKE '%outdoor%' OR a LIKE '%terrace%' OR a LIKE '%yard%' OR a LIKE '%fire pit%'
                 OR a LIKE '%hammock%' OR a LIKE '%beach%'
                 OR a LIKE '%waterfront%' OR a LIKE '%lake access%' OR a LIKE '%sun lounger%' OR a LIKE '%bikes%'
                THEN 'Outdoor & Views'
            -- Host Services & Policies
            WHEN a LIKE '%self check-in%' OR a LIKE '%host greets%' OR a LIKE '%luggage%'
                 OR a LIKE '%long term%' OR a LIKE '%pets allowed%' OR a LIKE '%smoking%'
                 OR a LIKE '%breakfast%' OR a LIKE '%check-in%' OR a LIKE '%cleaning available%'
                 OR a LIKE '%housekeeping%' OR a LIKE '%concierge%'
                 OR a LIKE '%private entrance%' OR a LIKE '%building staff%'
                THEN 'Host Services & Policies'
            ELSE 'Other'
        END                                                   AS amenity_group,
        e._LOAD_TS
    FROM (SELECT *, LOWER(raw_amenity) AS a FROM exploded) e
)
SELECT
    listing_id,
    raw_amenity,
    base_type,
    amenity_group,
    _LOAD_TS
FROM grouped
WHERE raw_amenity IS NOT NULL
  AND raw_amenity <> ''
QUALIFY ROW_NUMBER() OVER (
            PARTITION BY listing_id, raw_amenity
            ORDER BY _LOAD_TS DESC
        ) = 1;                          -- one row per (listing, amenity), latest load wins
