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

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA SILVER;

CREATE OR REPLACE TABLE SILVER.PROPERTY_GROUP_MAP AS
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
            'loft', 'guest suite', 'floor', 'home/apt'
        ) THEN 'Flat'
        WHEN property_type IN (
            'home', 'townhouse', 'bungalow', 'villa', 'cottage', 'cabin', 'chalet',
            'vacation home', 'guesthouse', 'bed and breakfast'
        ) THEN 'House'
        ELSE NULL   -- no residential sale comparator (hotels, unique stays, outdoor, ambiguous)
    END AS property_class
FROM (
    SELECT DISTINCT property_type
    FROM SILVER.LISTINGS_CLEANED
    WHERE property_type IS NOT NULL
);

-- Re-enable change tracking: CREATE OR REPLACE TABLE above drops it, and the
-- incremental dynamic table GOLD.DIM_LISTING reads this table -> its refresh
-- fails without change tracking. Re-assert it on every rebuild.
ALTER TABLE SILVER.PROPERTY_GROUP_MAP SET CHANGE_TRACKING = TRUE;
