-- Builds SILVER.PROPERTY_GROUP_MAP mapping property_type to property_group and a Flat/House property_class (sale-price bridge).
-- Databricks port of etl/cleaning_layer/10_silver_property_group_map.sql.
--
-- Builds SILVER.PROPERTY_GROUP_MAP: lookup mapping each cleaned property_type to a
-- higher-level property_group category, plus a coarser property_class.
--
-- Grain : one row per distinct cleaned property_type (from SILVER.LISTINGS_CLEANED).
-- Source: SILVER.LISTINGS_CLEANED.property_type (already lowercased & prefix-stripped
--         by 02_silver_listings.sql).
-- Usage : LEFT JOIN on property_type, wrapped in COALESCE(..., 'Other / Unknown').
--
-- property_class : the residential-sale bridge to HM Land Registry Price Paid, which
--         only distinguishes Flat vs House. Values:
--           'Flat'  -> maps to Price Paid Flat/Maisonette
--           'House' -> maps to Price Paid Terraced / Semi-Detached / Detached
--           NULL    -> NO residential sale comparator (hotels, unique stays, outdoor,
--                      ambiguous/unknown). These listings are KEPT in the data but
--                      excluded from the long-term (buy) vs short-term (Airbnb)
--                      comparison via `WHERE property_class IS NOT NULL`.
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE
-- ------------------------------------------------------------
--   USE DATABASE / two-level names -> USE CATALOG / three-level names
--
--   ALTER TABLE ... SET CHANGE_TRACKING = TRUE  -> DELETED, not ported.
--       The Snowflake original re-asserted change tracking on every rebuild
--       because CREATE OR REPLACE dropped it and the incremental DYNAMIC TABLE
--       GOLD.DIM_LISTING refused to refresh without it.
--
--       Delta maintains change data implicitly, so there is no flag to set and
--       nothing to re-assert. The line is removed rather than commented out
--       because it has no counterpart at all — see the translation reference in
--       .claude/agents/snowflake-to-databricks-migrator.md.
--
--       ⚠️ This does NOT mean the Gold dependency disappeared. When the 20
--       Dynamic Tables become a Lakeflow pipeline, GOLD.DIM_LISTING still reads
--       this table; the pipeline just declares that dependency instead of
--       relying on a per-table flag.
--
--   The escaped apostrophe in 'shepherd''s hut' ports unchanged (both engines
--   double the quote). The curly-apostrophe variant 'shepherd’s hut' is kept
--   alongside it — Airbnb hosts type both.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT.SILVER.PROPERTY_GROUP_MAP AS
SELECT
    property_type,
    CASE
        WHEN property_type IN (
            'rental unit', 'condo', 'serviced apartment', 'aparthotel'
        ) THEN 'Apartment / Flat'
        WHEN property_type IN (
            'home', 'townhouse', 'bungalow', 'villa', 'cottage', 'cabin', 'chalet', 'vacation home'
        ) THEN 'House'
        WHEN property_type IN (
            'guesthouse', 'guest suite', 'bed and breakfast', 'loft'
        ) THEN 'Guest Accommodation'
        WHEN property_type IN (
            'hotel', 'boutique hotel', 'hostel', 'resort', 'nature lodge'
        ) THEN 'Hotel / Hospitality'
        WHEN property_type IN (
            'treehouse', 'boat', 'houseboat', 'tiny home', 'camper/rv', 'yurt', 'castle',
            'lighthouse', 'cave', 'dome', 'hut', 'shepherd''s hut', 'shepherd’s hut',
            'barn', 'farm stay', 'shipping container', 'earthen home'
        ) THEN 'Unique Stay'
        WHEN property_type IN (
            'campsite', 'tent'
        ) THEN 'Outdoor / Land'
        ELSE 'Other / Unknown'
    END AS property_group,
    CASE
        WHEN property_type IN (
            'rental unit', 'condo', 'serviced apartment', 'aparthotel',
            'loft', 'floor', 'home/apt'
        ) THEN 'Flat'
        WHEN property_type IN (
            'home', 'townhouse', 'bungalow', 'villa', 'cottage', 'cabin', 'chalet',
            'vacation home'
        ) THEN 'House'
        ELSE NULL   -- no residential sale comparator (hotels, guest accommodation,
                    -- unique stays, outdoor, ambiguous). NOTE: guest suite / guesthouse /
                    -- bed and breakfast are NOT purchasable dwellings -> NULL (excluded
                    -- from the buy-vs-Airbnb yield comparison), though they remain grouped
                    -- as 'Guest Accommodation' in property_group above.
    END AS property_class
FROM (
    SELECT DISTINCT property_type
    FROM AIRBNB_INVESTMENT.SILVER.LISTINGS_CLEANED
    WHERE property_type IS NOT NULL
);
