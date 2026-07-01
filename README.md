This is a guide for this project. Read the `docs/` files for more detailed information.

For the big-picture pipeline (Bronze → Silver → Gold), see [docs/architecture.md](docs/architecture.md).

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

# Quick Start

Run these in order. The first three are **one-time** per account; the last one runs **every
time** you want to (re)load data.

| # | Step | File | When |
|---|------|------|------|
| 1 | Create DB, warehouses, integrations | `setup/run_setup.py` | once |
| 2 | Create Bronze formats + S3 stage + audit | `etl/ingestion_layer/01_bronze_ddl.sql` | once |
| 3 | Complete the AWS IAM trust handshake | *(AWS console)* | once |
| 4 | Load all cities into Bronze | `etl/ingestion_layer/02_bronze_load.py` | every load |

The Airbnb steps above are the primary pipeline. **Land Registry Price Paid** is a second,
independent source that lands in the same `BRONZE` schema (see its section below):

| # | Step | File | When |
|---|------|------|------|
| 5 | Create Land Registry format + stage | `etl/ingestion_layer/03_land_registry_ddl.sql` | once |
| 6 | Load Price Paid years into Bronze | `etl/ingestion_layer/04_land_registry_load.sql` | every load |

Current project database and warehouses:

```text
AIRBNB_INVESTMENT_DB
├── BRONZE
├── SILVER
└── GOLD

DATA WAREHOUSES
├── AIRBNB_DEV_WH    (dev / ETL)
└── AIRBNB_APP_WH    (querying / app)
```

---

# Data Ingestion (Bronze)

Raw Airbnb files live in an **AWS S3 bucket** and are read by Snowflake through a
**storage integration** (no AWS keys are stored in Snowflake). A quarterly Lambda drops each
new snapshot into S3; the loader picks up the latest one automatically.

### S3 layout the loader expects

```text
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/
└── <city>/
    └── snapshot_date=<YYYY-MM-DD>/
        ├── listings/listings.csv.gz
        ├── calendar/calendar.csv.gz
        ├── reviews/reviews.csv.gz
        ├── neighbourhoods/neighbourhoods.csv
        └── neighbourhoods_geojson/neighbourhoods.geojson
```

### Step 1 — One-time setup (run once per account)

1. Run `etl/ingestion_layer/01_bronze_ddl.sql` (as `ACCOUNTADMIN`). It creates:
   - the CSV + GeoJSON file formats,
   - the `AIRBNB_S3_INT` storage integration,
   - the external stage `BRONZE.RAW_STAGE` (points at the bucket above),
   - the `BRONZE.LOAD_AUDIT` table.

2. Complete the **AWS IAM trust handshake** (the part only AWS can do):
   ```sql
   DESC INTEGRATION AIRBNB_S3_INT;
   ```
   Copy `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID` into the **trust policy** of
   the IAM role `snowflake-airbnb-s3-read` (template is in the `2c` comment block of the DDL).
   The role's read-only S3 **permission** policy must cover the bucket
   (`s3:GetObject`/`s3:GetObjectVersion` on `.../raw/*`, `s3:ListBucket` on the bucket).

3. Verify Snowflake can read S3:
   ```sql
   LIST @AIRBNB_INVESTMENT_DB.BRONZE.RAW_STAGE/london/;
   ```
   You should see the `snapshot_date=.../` files. If you get
   *"bucket does not exist or not authorized"*, the trust/permission policy or bucket name is
   wrong — fix that before loading.

### Step 2 — Load the data (run every time)

Run `etl/ingestion_layer/02_bronze_load.py`. For each city × dataset it:

- resolves that city's **latest** `snapshot_date=` folder automatically,
- creates the `RAW_*` table (CSV columns are loaded as TEXT — faithful, never fails),
- `COPY`s the file in, and records the outcome in `BRONZE.LOAD_AUDIT`.

It prints a per-file summary and a final row count per table. Bronze tables are rebuilt on
every run; `LOAD_AUDIT` history accumulates.

---

# Land Registry Price Paid (Bronze)

A **second, independent source**: UK **HM Land Registry Price Paid Data** (residential sales),
one CSV per year for **2021 to present**. It lands in the same bucket under a different prefix
and reuses the existing `AIRBNB_S3_INT` integration — **no new integration or IAM handshake**
(the role just needs `s3:ListBucket`/`s3:GetObject` on `raw/*`). A monthly Lambda refreshes the
current-year file.

### S3 layout

```text
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry/price_paid/
└── year=<YYYY>/pp-<YYYY>.csv
```

The files have **no header row** and a fixed **16-column** layout, so this source does *not*
use the manifest/`MATCH_BY_COLUMN_NAME` loader. Instead it uses a dedicated pair of SQL files
with **positional** column mapping (`$1..$16`).

### Step 1 — One-time setup

Run `etl/ingestion_layer/03_land_registry_ddl.sql` (as `ACCOUNTADMIN`). It creates:
- `BRONZE.CSV_NOHDR_FF` — a headerless CSV file format,
- `BRONZE.LAND_REGISTRY_STAGE` — external stage on the `hm_land_registry/price_paid/` prefix.

Verify Snowflake can read S3: `LIST @BRONZE.LAND_REGISTRY_STAGE;` (should list `pp-<YYYY>.csv`).

### Step 2 — Load (run every time)

Run `etl/ingestion_layer/04_land_registry_load.sql`. It:
- rebuilds `BRONZE.RAW_PRICE_PAID` (16 columns as TEXT + `_FILENAME`/`_FILE_ROW_NUMBER`/`_LOAD_TS`),
- `COPY`s all `pp-<YYYY>.csv` files (`PATTERN` excludes the `_manifests/` JSON),
- records the outcome in `BRONZE.LOAD_AUDIT` (sourced from `COPY_HISTORY`, robust to re-runs).

The table is rebuilt each run, so re-running after the monthly refresh is **idempotent** — no
duplicate rows. All columns stay TEXT (faithful Bronze); typing happens in SILVER.

---

# Configuring what gets ingested

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

