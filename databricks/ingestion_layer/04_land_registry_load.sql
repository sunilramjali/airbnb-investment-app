-- Land Registry Price Paid — Bronze load. Databricks port of etl/ingestion_layer/04_land_registry_load.sql.
-- ============================================================
-- LAND REGISTRY PRICE PAID  —  LOAD (run EVERY load).
-- ------------------------------------------------------------
-- Depends on the external location `airbnb_raw_lr` (see 03_land_registry_ddl.sql).
-- Rebuilds RAW_PRICE_PAID from all year files, so re-running (e.g. after the
-- monthly current-year refresh) is idempotent — no duplicate rows. Bronze stays
-- faithful (all columns TEXT); typing happens in SILVER.
--
-- Steps 1 and 2 may be run independently — unlike the Snowflake original, whose
-- audit INSERT had to run immediately after the COPY (it read RESULT_SCAN /
-- COPY_HISTORY). Here the audit is derived by grouping the loaded table itself,
-- so ordering does not matter and a re-run cannot produce a broken audit row.
--
-- ============================================================
-- SNOWFLAKE -> DATABRICKS TRANSLATION NOTES
-- ------------------------------------------------------------
--   COPY INTO ... FROM (SELECT $1..$16 FROM @STAGE)
--       -> CREATE OR REPLACE TABLE AS SELECT ... FROM read_files(...). Databricks
--          has no positional $1..$16; a headerless CSV read yields _c0.._c15, which
--          are aliased explicitly below. The alias list IS the positional mapping,
--          so a column-order change in a future Land Registry file shows up as a
--          renamed column here rather than silently shifting every value one over.
--
--   ⚠️ schemaHints IS LOAD-BEARING, NOT DECORATION.
--       read_files() INFERS CSV column types by default — verified: without hints
--       _c1 (price) comes back as INT and _c2 (date_of_transfer) as TIMESTAMP.
--       That breaks the all-TEXT Bronze discipline, and casting back to STRING
--       afterwards is NOT equivalent: an inferred TIMESTAMP re-rendered as text
--       gives '2026-04-30T00:00:00.000Z', whereas the raw file holds
--       '2026-04-30 00:00'. Forcing STRING at parse time preserves the source
--       bytes, which is the whole point of Bronze.
--       (The Airbnb loader avoids this differently — spark.read with
--       inferSchema=false — because it uses the DataFrame API, not read_files.)
--
--   PATTERN = '.*pp-[0-9]{4}\.csv'  -> pathGlobFilter. Glob syntax, not regex.
--
--   METADATA$FILENAME          -> _metadata.file_path
--   METADATA$START_SCAN_TIME   -> current_timestamp()
--   METADATA$FILE_ROW_NUMBER   -> synthetic row_number(); see the note on the column.
--
--   NULL_IF = ('','NULL','null','N/A')  -> nullValue only accepts one marker, so the
--       set is applied with a NULLIF chain in the SELECT below.
--
--   ⚠️ Databricks auto-derives a `year` column from the Hive-style year=<YYYY>
--       partition folder. It is deliberately NOT selected: the Snowflake table has
--       exactly 16 source columns + 3 lineage columns, and the year is already
--       recoverable from _FILENAME. Adding it would be a silent schema divergence
--       that SILVER does not expect.
--
--   INFORMATION_SCHEMA.COPY_HISTORY -> no equivalent. See step 2.
-- ============================================================

USE CATALOG AIRBNB_INVESTMENT;
USE SCHEMA BRONZE;

---------------------------------------------
-- 1. Bronze table: the 16 documented PPD columns as TEXT + lineage columns.
--    Column order matches the Land Registry file layout exactly.
--    Rebuilt each run (OR REPLACE) to keep the load idempotent.
---------------------------------------------
CREATE OR REPLACE TABLE BRONZE.RAW_PRICE_PAID
COMMENT 'Bronze Land Registry Price Paid — all years, all-TEXT, rebuilt each run.'
AS
WITH src AS (
    SELECT
        *,
        _metadata.file_path AS _FILENAME
    FROM read_files(
        's3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry/price_paid/',
        format         => 'csv',
        header         => false,          -- LR yearly files have NO header row
        quote          => '"',            -- FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        escape         => '"',            -- doubled quotes inside quoted fields (RFC4180)
        multiLine      => true,           -- tolerate newlines inside quoted text fields
        encoding       => 'UTF-8',        -- ENCODING = 'UTF8'
        ignoreLeadingWhiteSpace  => true, -- TRIM_SPACE = TRUE
        ignoreTrailingWhiteSpace => true,
        pathGlobFilter => 'pp-[0-9][0-9][0-9][0-9].csv',   -- was PATTERN '.*pp-[0-9]{4}\\.csv'
        schemaHints    => '_c0 string, _c1 string, _c2 string, _c3 string, _c4 string, _c5 string, _c6 string, _c7 string, _c8 string, _c9 string, _c10 string, _c11 string, _c12 string, _c13 string, _c14 string, _c15 string'
    )
)
SELECT
    -- NULLIF chain = Snowflake's NULL_IF = ('', 'NULL', 'null', 'N/A').
    NULLIF(NULLIF(NULLIF(NULLIF(_c0 , ''), 'NULL'), 'null'), 'N/A') AS TRANSACTION_UID,   -- $1  transaction unique identifier (GUID)
    NULLIF(NULLIF(NULLIF(NULLIF(_c1 , ''), 'NULL'), 'null'), 'N/A') AS PRICE,             -- $2  sale price (GBP)
    NULLIF(NULLIF(NULLIF(NULLIF(_c2 , ''), 'NULL'), 'null'), 'N/A') AS DATE_OF_TRANSFER,  -- $3  date of transfer (YYYY-MM-DD HH:MM)
    NULLIF(NULLIF(NULLIF(NULLIF(_c3 , ''), 'NULL'), 'null'), 'N/A') AS POSTCODE,          -- $4
    NULLIF(NULLIF(NULLIF(NULLIF(_c4 , ''), 'NULL'), 'null'), 'N/A') AS PROPERTY_TYPE,     -- $5  D/S/T/F/O
    NULLIF(NULLIF(NULLIF(NULLIF(_c5 , ''), 'NULL'), 'null'), 'N/A') AS OLD_NEW,           -- $6  Y (new build) / N
    NULLIF(NULLIF(NULLIF(NULLIF(_c6 , ''), 'NULL'), 'null'), 'N/A') AS DURATION,          -- $7  F (freehold) / L (leasehold)
    NULLIF(NULLIF(NULLIF(NULLIF(_c7 , ''), 'NULL'), 'null'), 'N/A') AS PAON,              -- $8  primary addressable object name
    NULLIF(NULLIF(NULLIF(NULLIF(_c8 , ''), 'NULL'), 'null'), 'N/A') AS SAON,              -- $9  secondary addressable object name
    NULLIF(NULLIF(NULLIF(NULLIF(_c9 , ''), 'NULL'), 'null'), 'N/A') AS STREET,            -- $10
    NULLIF(NULLIF(NULLIF(NULLIF(_c10, ''), 'NULL'), 'null'), 'N/A') AS LOCALITY,          -- $11
    NULLIF(NULLIF(NULLIF(NULLIF(_c11, ''), 'NULL'), 'null'), 'N/A') AS TOWN_CITY,         -- $12
    NULLIF(NULLIF(NULLIF(NULLIF(_c12, ''), 'NULL'), 'null'), 'N/A') AS DISTRICT,          -- $13
    NULLIF(NULLIF(NULLIF(NULLIF(_c13, ''), 'NULL'), 'null'), 'N/A') AS COUNTY,            -- $14
    NULLIF(NULLIF(NULLIF(NULLIF(_c14, ''), 'NULL'), 'null'), 'N/A') AS PPD_CATEGORY_TYPE, -- $15 A (standard) / B (additional)
    NULLIF(NULLIF(NULLIF(NULLIF(_c15, ''), 'NULL'), 'null'), 'N/A') AS RECORD_STATUS,     -- $16 A / C / D (monthly file only)
    _FILENAME,                                                        -- lineage: source file (encodes year=)
    -- Synthetic row id. Snowflake's METADATA$FILE_ROW_NUMBER was the PHYSICAL line
    -- number in the file; Databricks exposes no such value. row_number() over the
    -- file gives a stable unique id per file, which is all any downstream consumer
    -- uses it for. ⚠️ It is NOT a file line number — the ordering reflects Spark's
    -- read order. Do not use it to locate a row in the source CSV.
    row_number() OVER (PARTITION BY _FILENAME ORDER BY monotonically_increasing_id())
                                                        AS _FILE_ROW_NUMBER,
    CAST(current_timestamp() AS TIMESTAMP_NTZ)          AS _LOAD_TS   -- lineage: load timestamp
FROM src;

---------------------------------------------
-- 2. Audit the load into the shared BRONZE.LOAD_AUDIT (created by 01_bronze_ddl.sql)
--    so Land Registry loads appear in the same audit queries as Airbnb loads.
--
--    Snowflake read INFORMATION_SCHEMA.COPY_HISTORY, chosen over RESULT_SCAN because
--    it survives a zero-file re-run. Databricks has NEITHER: there is no persistent,
--    queryable per-file COPY history, and Databricks COPY INTO returns only one
--    summary row per statement.
--
--    So the audit is derived from the loaded table itself, grouped by _FILENAME.
--    This is strictly better than the COPY INTO result would be — it restores true
--    PER-FILE granularity, matching the Snowflake audit rather than degrading to one
--    row per statement — and it is order-independent, so it can be re-run at any time.
--
--    ROWS_PARSED = ROWS_LOADED and ERRORS_SEEN = 0 because the all-TEXT read cannot
--    reject a row: every value is valid as a string. That mirrors the Snowflake
--    outcome for this file, where ON_ERROR = CONTINUE never had anything to skip.
---------------------------------------------
INSERT INTO BRONZE.LOAD_AUDIT
    (TABLE_NAME, FILE_NAME, STATUS, ROWS_PARSED, ROWS_LOADED,
     ERRORS_SEEN, FIRST_ERROR, FIRST_ERROR_LINE)
SELECT 'RAW_PRICE_PAID', _FILENAME, 'LOADED', COUNT(*), COUNT(*), 0, NULL, NULL
FROM BRONZE.RAW_PRICE_PAID
GROUP BY _FILENAME;

---------------------------------------------
-- 3. Verify (uncomment to run interactively):
--   -- rows loaded per transfer year
--   SELECT year(try_cast(left(DATE_OF_TRANSFER, 10) AS DATE)) AS transfer_year,
--          COUNT(*) AS rows
--   FROM BRONZE.RAW_PRICE_PAID
--   GROUP BY 1 ORDER BY 1;
--
--   -- most recent Land Registry load outcome
--   SELECT * FROM BRONZE.LOAD_AUDIT
--   WHERE TABLE_NAME = 'RAW_PRICE_PAID' ORDER BY LOAD_TS DESC;
---------------------------------------------
