-- Creates the SILVER schema and a durable CLEAN_AUDIT table for bronze->silver runs.
-- Databricks port of etl/cleaning_layer/01_silver_ddl.sql.
-- ============================================================
-- SILVER PREPROCESSING — DDL (schema + clean audit)
-- ------------------------------------------------------------
-- Run this ONCE (idempotent) before any cleaning transform.
-- The per-table cleaning logic lives in 02_silver_*.sql and is
-- driven by databricks/cleaning_layer/cleaning_layer.py.
--
-- FLOW:
--   1) Run this file            -> silver schema + silver.clean_audit.
--   2) Run 02_silver_listings.sql via cleaning_layer.py
--                               -> creates silver.listings_cleaned.
--
-- ============================================================
-- WHAT CHANGED FROM SNOWFLAKE
-- ------------------------------------------------------------
--   USE DATABASE <db>          -> USE CATALOG <catalog>
--   two-level SCHEMA.TABLE     -> three-level catalog.schema.table
--   NUMBER AUTOINCREMENT       -> BIGINT GENERATED ALWAYS AS IDENTITY
--   NUMBER                     -> BIGINT
--   COMMENT = '...'            -> COMMENT '...'   (no equals sign)
--   DEFAULT CURRENT_TIMESTAMP  -> needs an explicit Delta table feature, below
--
-- The schema itself already exists (created in Session 2 alongside bronze and
-- gold), so the CREATE SCHEMA below is a no-op in practice. It is kept so this
-- file still bootstraps a fresh catalog from nothing.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;

---------------------------------------------
-- 1. Create the SILVER schema
---------------------------------------------
CREATE SCHEMA IF NOT EXISTS AIRBNB_INVESTMENT.SILVER
    COMMENT 'Cleaned & validated, analysis-ready data (medallion silver layer).';

USE SCHEMA SILVER;

--------------------------------------------------------
-- 2. CLEAN AUDIT — durable record of every cleaning run.
--     One row per table per run: rows in (bronze) vs rows
--     out (silver) and rows dropped by validation/dedup, so
--     silently filtered rows leave a queryable trace.
--     IF NOT EXISTS (not OR REPLACE) so HISTORY accumulates
--     across runs — unlike the *_CLEANED tables, which are
--     rebuilt each run.
--
--     Inspect after a run:
--       SELECT * FROM AIRBNB_INVESTMENT.SILVER.CLEAN_AUDIT ORDER BY CLEAN_TS DESC;
--
--     ⚠️ ROWS_DROPPED IS NOW THE PRIMARY VERIFICATION SIGNAL. With Snowflake
--     gone there is no row-count parity to check Silver against, so the
--     documented drop rules in docs/data_pipeline.md:33-39 are the gate:
--     rows_in - rows_out must be fully attributable to them. See
--     databricks/verification_invariants.md.
--------------------------------------------------------
CREATE TABLE IF NOT EXISTS AIRBNB_INVESTMENT.SILVER.CLEAN_AUDIT (
    AUDIT_ID     BIGINT GENERATED ALWAYS AS IDENTITY,  -- was NUMBER AUTOINCREMENT
    TABLE_NAME   STRING,          -- target silver.*_cleaned table
    SOURCE_TABLE STRING,          -- source bronze.raw_* table
    ROWS_IN      BIGINT,          -- rows read from bronze
    ROWS_OUT     BIGINT,          -- rows written to silver
    ROWS_DROPPED BIGINT,          -- rows removed by validation + dedup
    CLEAN_TS     TIMESTAMP_NTZ DEFAULT current_timestamp()
)
COMMENT 'Per-table cleaning outcome for every Silver run; history accumulates.'
-- Delta refuses a column DEFAULT unless this table feature is enabled first
-- (WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED). Snowflake needed no
-- equivalent opt-in. Same trap as BRONZE.LOAD_AUDIT.
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');
