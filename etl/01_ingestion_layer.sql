USE DATABASE AIRBNB_INVESTMENT_DB
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Create file formats
---------------------------------------------

-- 1a. CSV Files (Single header-aware CSV format sued by ALL csv loads)
CREATE FILE_FORMAT IF NOT EXISTS BRONZE.CSV_HDR_FF
    TYPE = CSV
    PARSE_HEADER = TRUE                     -- columnn names come from row 1 (do NOT use SKIP_HEADER)
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'      -- handles commas inside quoted text fields
    ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE  -- required to INCLUDE_METADATA
    NULL_IF = ('', 'NULL', 'null', 'N/A')   -- normalise common null markers
    EMPTY_FIELD_AS_NULL = TRUE
    TRIM_SPACE = TRUE
    ENCODING = 'UTF8'
    COMMENT = 'HEADER-name CSV parse for all Airbnb CSV files';

-- 1b. GeoJson Files
CREATE FILE_FORMAT IF NOT EXISTS BRONZE.GEOJSON_FF
    TYPE = JSON
    STRIP_OUTER_ARRAY = FALSE -- FeatureCollection loads as one Variant row
    COMMENT = 'JSON parse rules for GeoJSON FeatureCollection files';

--------------------------------------------------------
-- 2. Create Stage for Raw Files (Format-Neutral stage)
--------------------------------------------------------

CREATE STAGE IF NOT EXISTS BRONZE.RAW_STAGE
    COMMENT = 'Landing zone for raw Airbnb CSV files and GeoJSON files';


--------------------------------------------------------
-- 3. EXTERNAL STAGE (AWS3)
--------------------------------------------------------

--------------------------------------------------------
-- 4. Load
--------------------------------------------------------

CREATE OR REPLACE TABLE BRONZE.RAW_LISTINGS
USING TEMPLATE(
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
    WITHIN GROUP(ORDER BY id)
    FROM TABLE(
        INFER_SCHEMA(
            LOCATION => '@BRONZE.RAW_STAGE/london/listings.csv',
            FILE_FORMAT = 'BRONZE.CSV_HDR_FF'
            )
        )
    )