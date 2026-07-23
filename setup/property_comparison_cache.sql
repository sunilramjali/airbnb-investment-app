-- Creates the PROPERTY_COMPARISON_CACHE table storing on-demand AI property-type comparison narratives for page 2.1.
-- Co-authored with CoCo
--
-- Schema matches property_types_comparison_helper.ensure_cache_table.
-- The helper writes via a parameterized INSERT (only INSERT privilege required).
-- CREATE OR REPLACE resets grants, so re-grant the app role each time.

CREATE OR REPLACE TABLE AIRBNB_INVESTMENT_DB.GOLD.PROPERTY_COMPARISON_CACHE (
    CITY                VARCHAR,
    PROPERTY_TYPE_GROUP VARCHAR,
    PERSONA             VARCHAR,
    COMBO_COUNT         NUMBER(2,0),
    AI_NARRATIVE        VARCHAR,
    MODEL_USED          VARCHAR,
    PROMPT_VERSION      VARCHAR,
    COMPUTED_AT         TIMESTAMP_NTZ
);

GRANT SELECT, INSERT ON TABLE AIRBNB_INVESTMENT_DB.GOLD.PROPERTY_COMPARISON_CACHE
    TO ROLE AIRBNB_APP_PUBLIC_ROLE;
