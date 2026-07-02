-- Creates the GOLD star-core schema plus the two consumption schemas (SERVING_APP, FEATURES_ML) for the aggregation layer.
-- Co-authored with CoCo
-- ============================================================
-- AGGREGATION LAYER — DDL (schemas + grants)
-- ------------------------------------------------------------
-- Run this ONCE (idempotent) before any gold transform.
--
-- WHY THREE SCHEMAS (not one big GOLD):
--   * GOLD        -> conformed star core (single source of truth):
--                    DIM_*, FCT_*, AGG_* built as DYNAMIC TABLES.
--   * SERVING_APP -> denormalized/aggregated marts the Streamlit
--                    app reads (fast reads, per-page views).
--   * FEATURES_ML -> one flat feature row per listing for the
--                    AI recommender.
--   Separate schemas give clean per-consumer grants (app role sees
--   only SERVING_APP, model role only FEATURES_ML) and stable
--   contracts, while dynamic tables span schemas with zero friction.
--
-- FLOW:
--   1) Run this file        -> GOLD / SERVING_APP / FEATURES_ML schemas.
--   2) 01_dimensions.sql    -> DIM_* (incl. GEO_POINT), DIM_DATE.
--   3) 02_facts.sql         -> FCT_CALENDAR_DAILY, FCT_LISTING_SNAPSHOT.
--   4) 03_sales_codepoint.sql (after Code-Point Open is Got).
--   5) 04_marts.sql / 05_features.sql / 09_validate.sql.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;

---------------------------------------------
-- 1. Conformed star core (dims + facts + aggregates)
---------------------------------------------
CREATE SCHEMA IF NOT EXISTS AIRBNB_INVESTMENT_DB.GOLD
    COMMENT = 'Conformed dimensional star core (medallion gold): DIM_*, FCT_*, AGG_* as dynamic tables. Single source of truth for both app and recommender.';

---------------------------------------------
-- 2. Serving layer for the Streamlit app
---------------------------------------------
CREATE SCHEMA IF NOT EXISTS AIRBNB_INVESTMENT_DB.SERVING_APP
    COMMENT = 'Denormalized/aggregated marts + per-page views for the Streamlit app. Reads from GOLD.';

---------------------------------------------
-- 3. Feature layer for the AI recommender
---------------------------------------------
CREATE SCHEMA IF NOT EXISTS AIRBNB_INVESTMENT_DB.FEATURES_ML
    COMMENT = 'Flat, one-row-per-listing feature tables for the AI recommender. Reads from GOLD.';

---------------------------------------------
-- 4. Grants (least-privilege, per consumer)
--     Uncomment and set the real role names once the app/model
--     service roles exist. Kept commented so this file stays
--     runnable before those roles are created.
---------------------------------------------
-- GRANT USAGE ON SCHEMA AIRBNB_INVESTMENT_DB.SERVING_APP  TO ROLE <APP_ROLE>;
-- GRANT SELECT ON ALL DYNAMIC TABLES IN SCHEMA AIRBNB_INVESTMENT_DB.SERVING_APP  TO ROLE <APP_ROLE>;
-- GRANT SELECT ON FUTURE DYNAMIC TABLES IN SCHEMA AIRBNB_INVESTMENT_DB.SERVING_APP TO ROLE <APP_ROLE>;
-- GRANT USAGE ON SCHEMA AIRBNB_INVESTMENT_DB.FEATURES_ML  TO ROLE <MODEL_ROLE>;
-- GRANT SELECT ON ALL DYNAMIC TABLES IN SCHEMA AIRBNB_INVESTMENT_DB.FEATURES_ML TO ROLE <MODEL_ROLE>;
-- GRANT SELECT ON FUTURE DYNAMIC TABLES IN SCHEMA AIRBNB_INVESTMENT_DB.FEATURES_ML TO ROLE <MODEL_ROLE>;
