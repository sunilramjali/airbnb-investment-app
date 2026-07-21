-- Builds the GOLD core/area app marts: MART_LISTING_CANDIDATES, MART_AREA_OVERVIEW, MART_AREA_POI, MART_AREA_SEASONAL.
-- Co-authored with CoCo
-- ============================================================
-- GOLD - APP MARTS (core / area). Split out of 03_app_marts.sql.
-- MART_LISTING_CANDIDATES is the per-listing source the property marts
-- read, so this file MUST run first in the marts sequence.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA GOLD;

-- ============================================================
-- MART_LISTING_CANDIDATES — grain: one row per listing.
-- The app's single per-listing source (detail + comparison screens).
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_LISTING_CANDIDATES
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready per-listing dataset: area (NEIGHBOURHOOD), mapping geo, property attributes, revenue metrics, and area x structure median sale-price cost benchmark.'
AS
SELECT
    s.LISTING_ID,
    s.HOST_ID,
    d.NAME,
    d.NEIGHBOURHOOD,
    d.LATITUDE,
    d.LONGITUDE,
    d.GEO_POINT,
    d.ROOM_TYPE,
    d.PROPERTY_TYPE,
    d.STRUCTURE_CLASS,
    d.PROPERTY_GROUP,
    d.ACCOMMODATES,
    d.BEDROOMS,
    d.BEDS,
    d.BATHROOMS,
    s.ADR,
    s.OCCUPANCY_NIGHTS,
    s.OCCUPANCY_RATE,
    (s.OCCUPANCY_NIGHTS >= 30) AS IS_ACTIVE,
    s.ANNUAL_REVENUE,
    s.REVPAR,
    (s.ANNUAL_REVENUE IS NOT NULL) AS HAS_REVENUE_DATA,
    c.MEDIAN_SALE_PRICE AS AREA_MEDIAN_SALE_PRICE,
    s.REVIEW_SCORES_RATING,
    s.NUMBER_OF_REVIEWS,
    h.HOST_IS_SUPERHOST,
    p.POI_COUNT_500M,
    p.TRANSPORT_COUNT_500M,
    p.DINING_COUNT_500M,
    d.INSTANT_BOOKABLE,
    d.LISTING_URL,
    d.PICTURE_URL
FROM GOLD.FCT_LISTING_SNAPSHOT s
JOIN GOLD.DIM_LISTING d
    ON s.LISTING_ID = d.LISTING_ID
LEFT JOIN GOLD.DIM_HOST h
    ON s.HOST_ID = h.HOST_ID
LEFT JOIN GOLD.FCT_LISTING_POI p
    ON s.LISTING_ID = p.LISTING_ID
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = d.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = d.STRUCTURE_CLASS;

-- ============================================================
-- MART_AREA_OVERVIEW — grain: one row per NEIGHBOURHOOD.
-- Area Overview screen: KPIs + GEOGRAPHY boundary for the map.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_OVERVIEW
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready per-neighbourhood summary: CITY, listing counts, revenue/occupancy aggregates, median sale price, in-area POI counts, and boundary GEOGRAPHY for mapping.'
AS
WITH listing_agg AS (
    SELECT
        NEIGHBOURHOOD,
        COUNT(*)                       AS LISTING_COUNT,
        ROUND(AVG(ADR), 2)             AS AVG_ADR,
        MEDIAN(ADR)                    AS MEDIAN_ADR,
        ROUND(AVG(OCCUPANCY_RATE), 4)  AS AVG_OCCUPANCY_RATE,
        ROUND(AVG(ANNUAL_REVENUE), 2)  AS AVG_ANNUAL_REVENUE,
        MEDIAN(ANNUAL_REVENUE)         AS MEDIAN_ANNUAL_REVENUE,
        ROUND(AVG(BEDROOMS), 2)        AS AVG_BEDROOMS,
        ROUND(AVG(REVIEW_SCORES_RATING), 2) AS AVG_RATING
    FROM GOLD.MART_LISTING_CANDIDATES
    GROUP BY NEIGHBOURHOOD
),
area_poi AS (
    -- POIs falling inside each neighbourhood boundary (point-in-polygon).
    SELECT
        n.NEIGHBOURHOOD,
        COUNT(*)                                                           AS POI_COUNT,
        COUNT(CASE WHEN p.IS_TRANSPORT THEN 1 END)                         AS TRANSPORT_COUNT,
        COUNT(CASE WHEN p.IS_DINING    THEN 1 END)                         AS DINING_COUNT
    FROM GOLD.DIM_NEIGHBOURHOOD n
    JOIN GOLD.DIM_POI p
        ON ST_CONTAINS(n.BOUNDARY, p.LOCATION)
    GROUP BY n.NEIGHBOURHOOD
)
SELECT
    la.NEIGHBOURHOOD,
    n.CITY,
    la.LISTING_COUNT,
    la.AVG_ADR,
    la.MEDIAN_ADR,
    la.AVG_OCCUPANCY_RATE,
    la.AVG_ANNUAL_REVENUE,
    la.MEDIAN_ANNUAL_REVENUE,
    la.AVG_BEDROOMS,
    la.AVG_RATING,
    c.MEDIAN_SALE_PRICE AS MEDIAN_SALE_PRICE,
    COALESCE(ap.POI_COUNT, 0)       AS POI_COUNT,
    COALESCE(ap.TRANSPORT_COUNT, 0) AS TRANSPORT_COUNT,
    COALESCE(ap.DINING_COUNT, 0)    AS DINING_COUNT,
    ROUND(COALESCE(ap.POI_COUNT, 0) / NULLIF(n.AREA_SQKM, 0), 2) AS POI_DENSITY_SQKM,
    n.AREA_SQKM,
    n.BOUNDARY
FROM listing_agg la
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON la.NEIGHBOURHOOD = n.NEIGHBOURHOOD
LEFT JOIN GOLD.FCT_AREA_SALE_PRICE c
    ON c.NEIGHBOURHOOD   = la.NEIGHBOURHOOD
   AND c.STRUCTURE_CLASS = 'All'
LEFT JOIN area_poi ap
    ON la.NEIGHBOURHOOD = ap.NEIGHBOURHOOD;

-- ============================================================
-- MART_AREA_POI — grain: one row per POI inside a neighbourhood.
-- Map-marker feed for the Area Overview screen. Consistent with
-- MART_AREA_OVERVIEW's POI counts (same point-in-polygon join). Reads
-- with a simple WHERE NEIGHBOURHOOD = :area filter.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_POI
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready POI markers per neighbourhood (point-in-polygon): name, category, amenity group, transport/dining flags, and lat/lon for map plotting.'
AS
SELECT
    n.NEIGHBOURHOOD,
    n.CITY,
    p.NAME                                                             AS POI_NAME,
    p.CATEGORY,
    p.AMENITY_GROUP,
    p.IS_TRANSPORT,
    p.IS_DINING,
    ST_Y(p.LOCATION)                                                   AS LATITUDE,
    ST_X(p.LOCATION)                                                   AS LONGITUDE
FROM GOLD.DIM_NEIGHBOURHOOD n
JOIN GOLD.DIM_POI p
    ON ST_CONTAINS(n.BOUNDARY, p.LOCATION);

-- ============================================================
-- MART_AREA_SEASONAL — grain: NEIGHBOURHOOD x MONTH (1-12).
-- Area-COMPARISON screen: seasonal popularity/occupancy trend for the
-- up-to-3 boroughs a user pins. Reads with WHERE NEIGHBOURHOOD IN (...).
--
-- METRIC: OCCUPANCY_RATE = BOOKED_NIGHTS / TOTAL_NIGHTS per (area, month),
-- where a booked night is AVAILABLE = FALSE in the calendar. This is the
-- honest seasonal signal for the trend chart.
--
-- NO REVENUE COLUMN — deliberately. The calendar carries no nightly price
-- (SILVER.CALENDAR_CLEANED price/adjusted_price are all-NULL in this scrape),
-- so any monthly revenue would be BOOKED_NIGHTS x a *static* scrape-time ADR
-- and its seasonal shape would just mirror OCCUPANCY_RATE, adding no signal.
-- Revenue is surfaced as an ANNUAL figure in MART_AREA_STRATEGY instead.
--
-- MONTH grain collapses the year: the scrape window (~Sep 2025 -> Sep 2026)
-- spans 13 months, so the boundary month is observed across two partial
-- years. Acceptable for a seasonality curve; not a same-year comparison.
-- OCCUPANCY is derived from FORWARD-LOOKING availability at scrape time.
-- ============================================================
CREATE OR REPLACE DYNAMIC TABLE GOLD.MART_AREA_SEASONAL
    TARGET_LAG = '1 day'
    WAREHOUSE  = AIRBNB_APP_WH
    COMMENT    = 'App-ready seasonal occupancy trend per neighbourhood x month (1-12): booked/total nights and occupancy rate from calendar availability. Occupancy-only by design (no monthly price exists); revenue lives in MART_AREA_STRATEGY.'
AS
SELECT
    d.NEIGHBOURHOOD,
    n.CITY,
    MONTH(c.CALENDAR_DATE)                                                       AS MONTH,
    COUNT(DISTINCT c.LISTING_ID)                                                 AS LISTING_COUNT,
    COUNT(*)                                                                     AS TOTAL_NIGHTS,
    COUNT(CASE WHEN c.AVAILABLE = FALSE THEN 1 END)                              AS BOOKED_NIGHTS,
    ROUND(COUNT(CASE WHEN c.AVAILABLE = FALSE THEN 1 END) / NULLIF(COUNT(*), 0), 4) AS OCCUPANCY_RATE
FROM GOLD.FCT_CALENDAR_DAILY c
JOIN GOLD.DIM_LISTING d
    ON c.LISTING_ID = d.LISTING_ID
LEFT JOIN GOLD.DIM_NEIGHBOURHOOD n
    ON d.NEIGHBOURHOOD = n.NEIGHBOURHOOD
GROUP BY d.NEIGHBOURHOOD, n.CITY, MONTH(c.CALENDAR_DATE);

-- ============================================================
-- COLUMN COMMENTS
-- ------------------------------------------------------------
-- Per-column documentation for the app marts, kept as COMMENT ON COLUMN
-- (rather than inline column lists) so they can be maintained without
-- re-running the mart bodies. Re-applied on every run AFTER the CREATE OR
-- REPLACE statements above, so they persist across rebuilds. Column names
-- must match the mart projections above.
-- ============================================================
-- ---- MART_LISTING_CANDIDATES ----
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LISTING_ID IS 'Airbnb listing id; row grain (unique per listing).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.HOST_ID IS 'Airbnb host id that owns the listing.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.NAME IS 'Listing title.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.NEIGHBOURHOOD IS 'Area name; the app area grain.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LATITUDE IS 'Listing latitude (WGS84).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LONGITUDE IS 'Listing longitude (WGS84).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.GEO_POINT IS 'Geospatial point for map plotting and spatial joins.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ROOM_TYPE IS 'Airbnb room type (Entire home, Private room, etc.).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.PROPERTY_TYPE IS 'Raw Airbnb property type text.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.STRUCTURE_CLASS IS 'Flat or House (NULL for hotel/boat/etc.); used for sale-price yield match.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.PROPERTY_GROUP IS 'Higher-level property grouping for the selection UI.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ACCOMMODATES IS 'Maximum guests the listing sleeps.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.BEDROOMS IS 'Number of bedrooms (NULL if unknown).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.BEDS IS 'Number of beds.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.BATHROOMS IS 'Number of bathrooms (may be fractional).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ADR IS 'Average daily rate = nightly price at scrape time.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.OCCUPANCY_NIGHTS IS 'Estimated booked nights over the trailing 365 days (scraper estimate).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.OCCUPANCY_RATE IS 'Estimated occupancy (0..1) = estimated booked nights / 365.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.IS_ACTIVE IS 'TRUE if OCCUPANCY_NIGHTS >= 30. The single shared active-listing definition consumed by the property (04) and strategy (05) marts.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.ANNUAL_REVENUE IS 'Estimated trailing-12-month revenue (scraper estimate).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.REVPAR IS 'Revenue per available night = ANNUAL_REVENUE / 365.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.HAS_REVENUE_DATA IS 'TRUE if ANNUAL_REVENUE is populated.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.AREA_MEDIAN_SALE_PRICE IS 'Land Registry median sale price for the area x structure (purchase-cost benchmark).';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.REVIEW_SCORES_RATING IS 'Overall guest review rating.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.NUMBER_OF_REVIEWS IS 'Total review count.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.HOST_IS_SUPERHOST IS 'Whether the host holds Superhost status.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.POI_COUNT_500M IS 'Count of points of interest within 500m.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.TRANSPORT_COUNT_500M IS 'Transport POIs within 500m.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.DINING_COUNT_500M IS 'Dining POIs within 500m.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.INSTANT_BOOKABLE IS 'Whether the listing allows instant booking.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.LISTING_URL IS 'Airbnb listing URL.';
COMMENT ON COLUMN GOLD.MART_LISTING_CANDIDATES.PICTURE_URL IS 'Listing cover photo URL.';

-- ---- MART_AREA_OVERVIEW ----
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.NEIGHBOURHOOD IS 'Area name; row grain.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.CITY IS 'City the neighbourhood belongs to (London / Greater Manchester / Bristol).';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.LISTING_COUNT IS 'Number of listings in the area.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_ADR IS 'Mean nightly rate across the area listings.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.MEDIAN_ADR IS 'Median nightly rate.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_OCCUPANCY_RATE IS 'Mean estimated occupancy (0..1).';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_ANNUAL_REVENUE IS 'Mean estimated annual revenue.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.MEDIAN_ANNUAL_REVENUE IS 'Median estimated annual revenue.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_BEDROOMS IS 'Mean bedrooms per listing.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AVG_RATING IS 'Mean guest review rating.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.MEDIAN_SALE_PRICE IS 'Land Registry median sale price for the area (purchase benchmark).';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.POI_COUNT IS 'POIs inside the neighbourhood boundary.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.TRANSPORT_COUNT IS 'Transport POIs inside the boundary.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.DINING_COUNT IS 'Dining POIs inside the boundary.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.POI_DENSITY_SQKM IS 'POIs per square km.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.AREA_SQKM IS 'Neighbourhood area in square km.';
COMMENT ON COLUMN GOLD.MART_AREA_OVERVIEW.BOUNDARY IS 'Neighbourhood boundary polygon (GEOGRAPHY) for mapping.';

-- ---- MART_AREA_POI ----
COMMENT ON COLUMN GOLD.MART_AREA_POI.NEIGHBOURHOOD IS 'Area the POI falls within.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.POI_NAME IS 'Point-of-interest name.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.CATEGORY IS 'POI category (raw).';
COMMENT ON COLUMN GOLD.MART_AREA_POI.AMENITY_GROUP IS 'Curated POI amenity group.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.IS_TRANSPORT IS 'TRUE if the POI is a transport category.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.IS_DINING IS 'TRUE if the POI is a dining amenity.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.LATITUDE IS 'POI latitude for map plotting.';
COMMENT ON COLUMN GOLD.MART_AREA_POI.LONGITUDE IS 'POI longitude for map plotting.';

-- ---- MART_AREA_SEASONAL ----
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.NEIGHBOURHOOD IS 'Area name.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.CITY IS 'City of the neighbourhood.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.MONTH IS 'Calendar month 1-12 (year collapsed for seasonality).';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.LISTING_COUNT IS 'Distinct listings contributing in the month.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.TOTAL_NIGHTS IS 'Listing-nights observed in the month.';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.BOOKED_NIGHTS IS 'Nights not available (proxy for booked).';
COMMENT ON COLUMN GOLD.MART_AREA_SEASONAL.OCCUPANCY_RATE IS 'BOOKED_NIGHTS / TOTAL_NIGHTS (0..1); the seasonal signal.';

