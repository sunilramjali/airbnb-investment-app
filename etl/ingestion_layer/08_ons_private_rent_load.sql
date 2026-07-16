-- ONS Price Index of Private Rents (PIPR) — Bronze load (table rebuild + parse proc + audit).
-- Co-authored with CoCo
-- ============================================================
-- ONS PRIVATE RENT (PIPR)  —  LOAD (run EVERY load).
-- ------------------------------------------------------------
-- Depends on 07_ons_private_rent_ddl.sql (ONS_PRIVATE_RENT_STAGE + the
-- BRONZE.LOAD_ONS_PRIVATE_RENT parse proc).
--
-- Rebuilds RAW_ONS_PRIVATE_RENT, then CALLs the proc, which parses the NEWEST
-- .xlsx on the stage with openpyxl and appends one faithful row per spreadsheet
-- row (all cells as an ARRAY of TEXT). Rebuild + single-file parse keeps the
-- load idempotent — re-running after the monthly Lambda refresh yields no
-- duplicates. Bronze stays faithful (untyped); typing happens in SILVER.
--
-- The proc also writes the BRONZE.LOAD_AUDIT row itself: a Python load produces
-- no COPY_HISTORY, so the COPY_HISTORY-based audit used by the CSV loaders
-- (03/04, 07-old) does not apply here.
-- ============================================================

USE DATABASE AIRBNB_INVESTMENT_DB;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Bronze table: faithful, untyped landing of the ONS workbook.
--    Each spreadsheet row -> one table row: the cells as an ARRAY of TEXT
--    (survives ONS's multi-row titles / merged headers) + lineage columns.
--    Rebuilt each run (OR REPLACE) to keep the load idempotent.
--    SILVER will locate the header row and reshape CELLS into typed columns.
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_ONS_PRIVATE_RENT (
    SHEET             STRING,               -- workbook tab the row came from
    CELLS             ARRAY,                -- ordered cell values as TEXT (NULLs preserved)
    _FILENAME         STRING,               -- lineage: source file (relative path on stage)
    _FILE_ROW_NUMBER  NUMBER,               -- lineage: 1-based row position within the sheet
    _LOAD_TS          TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()  -- lineage: load time
)
COMMENT = 'Bronze ONS PIPR workbook — faithful, one ARRAY row per sheet row, rebuilt each run.';

---------------------------------------------
-- 2. Parse + load the newest .xlsx (proc refreshes the stage directory itself).
--    Reads the 'Table 1' tab and skips the 2 ONS title rows above the header,
--    so the header (original row 3) is the first landed row and data follows.
--    Returns a summary string and writes a BRONZE.LOAD_AUDIT row.
---------------------------------------------
CALL BRONZE.LOAD_ONS_PRIVATE_RENT('Table 1', 2);

---------------------------------------------
-- 3. Verify (uncomment to run interactively):
--   -- most recent ONS load outcome
--   SELECT * FROM BRONZE.LOAD_AUDIT
--   WHERE TABLE_NAME = 'RAW_ONS_PRIVATE_RENT' ORDER BY LOAD_TS DESC;
--
--   -- row count + first rows: row 3 is the header, data is _FILE_ROW_NUMBER >= 4
--   SELECT COUNT(*) AS rows, MAX(_LOAD_TS) AS last_load FROM BRONZE.RAW_ONS_PRIVATE_RENT;
--   SELECT _FILE_ROW_NUMBER, CELLS
--   FROM BRONZE.RAW_ONS_PRIVATE_RENT ORDER BY _FILE_ROW_NUMBER LIMIT 30;
