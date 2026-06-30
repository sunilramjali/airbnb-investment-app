-- Creates the SILVER schema and a durable CLEAN_AUDIT table for bronze->silver runs.
-- Co-authored with CoCo
-- ============================================================
-- SILVER PREPROCESSING — DDL (schema + clean audit)
-- ------------------------------------------------------------
-- Run this ONCE (idempotent) before any cleaning transform.
-- The per-table cleaning logic lives in 02_silver_*.sql and is
-- driven by cleaning_layer.py.
--
-- FLOW:
--   1) Run this file            -> SILVER schema + SILVER.CLEAN_AUDIT.
--   2) Run 02_silver_listings.sql via cleaning_layer.py
--                               -> creates SILVER.LISTINGS_CLEANED.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;

---------------------------------------------
-- 1. Create the SILVER schema
---------------------------------------------
CREATE SCHEMA IF NOT EXISTS AIRBNB_INVESTMENT_DB.SILVER
    COMMENT = 'Cleaned & validated, analysis-ready data (medallion silver layer).';

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
--       SELECT * FROM SILVER.CLEAN_AUDIT ORDER BY CLEAN_TS DESC;
--------------------------------------------------------
CREATE TABLE IF NOT EXISTS SILVER.CLEAN_AUDIT (
    AUDIT_ID     NUMBER AUTOINCREMENT START 1 INCREMENT 1,
    TABLE_NAME   STRING,          -- target SILVER.*_CLEANED table
    SOURCE_TABLE STRING,          -- source BRONZE.RAW_* table
    ROWS_IN      NUMBER,          -- rows read from bronze
    ROWS_OUT     NUMBER,          -- rows written to silver
    ROWS_DROPPED NUMBER,          -- rows removed by validation + dedup
    CLEAN_TS     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Per-table cleaning outcome for every Silver run; history accumulates.';
