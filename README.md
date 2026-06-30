This is a guide for this project. Read doc files for more detailed information. 


----------------------------------------------------------


# Branches and File/Folder Naming Conventions

branches = hyphens
folders/files = underscores

Branch:
role/data-engineer/feature/data-ingestion

Folder:
setup/run_setup.py


----------------------------------------------------------



# Where This Runs — Snowflake-native

This project is built to run **inside Snowflake** (Snowflake Workspaces / Snowsight
notebooks), not on a local machine.

- The Python code uses Snowpark's `get_active_session()` — Snowflake hands the code a
  ready-made, authenticated session. **No local install, no credentials, no `.env`.**
- Packages it relies on (`snowflake-snowpark-python`, `sqlparse`) are already available in
  Snowflake's Python/Anaconda environment, so there is intentionally **no `requirements.txt`**.
- The SQL runs server-side; data lands on Snowflake stages and tables directly.

### If you want to run it outside Snowflake (local laptop, CI, Airflow)

This is **not** the supported path, but if a teammate needs it, the recommendation is:

1. Create a virtual env and install deps explicitly (add a `requirements.txt`):
   ```text
   snowflake-snowpark-python
   sqlparse
   ```
2. Replace `get_active_session()` with an explicit connection — `Session.builder` reading a
   `connections.toml` or environment variables. **Never hardcode account/user/password.**
3. Keep `data/`, secrets, and `connections.toml` out of git (already covered by `.gitignore`).

Treat the in-Snowflake path as the source of truth; the local path is a convenience for
testing/automation only.

---

# Project Guide

Run setup/run_setup.py to integrate git workspace with project remote repository and setup project database and warehouse.

Current project database and warehouse:

```text
AIRBNB_INVESTMENT_DB
├── BRONZE
├── SILVER
└── GOLD

DATA WAREHOUSE
├── AIRBNB_DEV_WH
└── AIRBNB_APP_WH
```
---

# Bronze → Silver (Cleaning) — User Guide

The **silver layer** turns the faithful, all-TEXT `BRONZE.RAW_*` tables into typed,
validated, analysis-ready `SILVER.*_CLEANED` tables. It lives in `etl/cleaning_layer/`
and is driven by a single Python file.

### Prerequisites

1. Bronze must be loaded first — run `etl/ingestion_layer/02_bronze_load.py`.
2. The `AIRBNB_INVESTMENT_DB` database and a warehouse exist (`setup/run_setup.py`).

### How to run

Open `etl/cleaning_layer/cleaning_layer.py` in a Snowflake Workspace and run it.
It uses Snowpark's `get_active_session()` (no credentials needed) and executes, in order:

1. `01_silver_ddl.sql` — creates the `SILVER` schema and the `SILVER.CLEAN_AUDIT` table.
2. `02_silver_listings.sql` → `06_silver_neighbourhoods_geo.sql` — one cleaning transform each.

### What it produces

```text
AIRBNB_INVESTMENT_DB.SILVER
├── LISTINGS_CLEANED              # from BRONZE.RAW_LISTINGS
├── CALENDAR_CLEANED             # from BRONZE.RAW_CALENDAR
├── REVIEWS_CLEANED              # from BRONZE.RAW_REVIEWS
├── NEIGHBOURHOODS_CLEANED       # from BRONZE.RAW_NEIGHBOURHOODS
├── NEIGHBOURHOODS_GEO_CLEANED   # from BRONZE.RAW_NEIGHBOURHOODS_GEO (GeoJSON -> GEOGRAPHY)
└── CLEAN_AUDIT                  # one row per table per run (rows in/out/dropped)
```

Each `*_CLEANED` table is rebuilt (`CREATE OR REPLACE`) on every run; `CLEAN_AUDIT`
accumulates history.

### Cleaning principles

- **`TRY_CAST` everywhere** — a bad value becomes a countable `NULL`, never a lost row.
- **Parse dirty strings** — price `"$1,250.00"` → `1250.00`, rates `"95%"` → `95`, flags `"t"/"f"` → `TRUE/FALSE`.
- **Deduplicate** — one row per natural key (latest load wins, via `QUALIFY ROW_NUMBER()`).
- **Validate** — drop rows with no usable id or impossible coordinates.
- **Carry every bronze column** plus `_FILENAME` / `_LOAD_TS` lineage for traceability.

### Auditing a run

```sql
SELECT * FROM AIRBNB_INVESTMENT_DB.SILVER.CLEAN_AUDIT ORDER BY CLEAN_TS DESC;
```

`ROWS_DROPPED = ROWS_IN - ROWS_OUT` captures everything removed by validation + dedup,
so silently filtered rows leave a durable, queryable trace.

### Adding a new cleaning transform

1. Write `etl/cleaning_layer/0N_silver_<table>.sql` (a `CREATE OR REPLACE TABLE ... AS SELECT`).
2. Add one `(source, target, sql)` entry to the `TRANSFORMS` list in `cleaning_layer.py`.

That's it — the driver runs it in order and records its audit row automatically.

---

