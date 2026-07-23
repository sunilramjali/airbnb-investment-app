-- Creates the LISTING_COMPARISON_CACHE table storing on-demand AI top-vs-bottom listing comparison narratives for page 3 (Listing Candidates).
-- Co-authored with CoCo
--
-- Schema matches listing_comparison_helper.write_to_cache / check_cache.
-- The helper writes via a parameterized INSERT (only INSERT privilege required).
-- CREATE OR REPLACE resets grants, so re-grant the app role each time.

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT_DB.GOLD.LISTING_COMPARISON_CACHE (
    CITY                   VARCHAR,
    NEIGHBOURHOOD_CLEANSED VARCHAR,
    PERSONA                VARCHAR,
    PROPERTY_GROUP         VARCHAR,
    TOP_LISTING_NAME       VARCHAR,
    LISTING_COUNT          NUMBER(4,0),
    AI_NARRATIVE           VARCHAR,
    MODEL_USED             VARCHAR,
    PROMPT_VERSION         VARCHAR,
    COMPUTED_AT            TIMESTAMP_NTZ
);

GRANT SELECT, INSERT ON TABLE AIRBNB_INVESTMENT_DB.GOLD.LISTING_COMPARISON_CACHE
    TO ROLE AIRBNB_APP_PUBLIC_ROLE;
