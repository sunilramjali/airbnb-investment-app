-- Creates the ST_VS_LT_COMPARISON_CACHE table storing on-demand AI short-term vs long-term strategy narratives for page 1.1 (Area Comparison).
-- Co-authored with CoCo
--
-- Schema matches area_comparison_helper.check_cache / write_to_cache.
-- NEIGHBOURHOOD_GROUP is the sorted, comma-joined set of starred neighbourhood
-- names (see make_cache_key), so the cached narrative matches the exact trio
-- shown on the page.
-- The helper writes via a parameterized INSERT (only INSERT privilege required).
-- CREATE OR REPLACE resets grants, so re-grant the app role each time.

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT_DB.GOLD.ST_VS_LT_COMPARISON_CACHE (
    CITY                VARCHAR,
    NEIGHBOURHOOD_GROUP VARCHAR,
    PERSONA             VARCHAR,
    NEIGHBOURHOOD_COUNT NUMBER(4,0),
    AI_NARRATIVE        VARCHAR,
    MODEL_USED          VARCHAR,
    PROMPT_VERSION      VARCHAR,
    COMPUTED_AT         TIMESTAMP_NTZ
);

GRANT SELECT, INSERT ON TABLE AIRBNB_INVESTMENT_DB.GOLD.ST_VS_LT_COMPARISON_CACHE
    TO ROLE AIRBNB_APP_PUBLIC_ROLE;
