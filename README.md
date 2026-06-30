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

# Configuring what gets ingested

Ingestion is **declarative** — edit `config/ingestion_manifest.py`, not the loader:

- **Add a city:** add its folder name (must match S3 exactly) to `CITIES`.
- **Add a source file:** add a dict to `DATASETS` with:
  - `name`  — target Bronze table (e.g. `RAW_LISTINGS`),
  - `dir`   — the dataset subfolder on the stage (e.g. `listings`),
  - `file`  — exact filename incl. `.gz` if compressed,
  - `format`— `"csv"` or `"geojson"`.

No loader changes are needed for either — the manifest drives the loop.

---

# Verifying a load

Check the audit table after any run:

```sql
-- per-file outcome of the most recent loads
SELECT TABLE_NAME, FILE_NAME, ROWS_LOADED, ERRORS_SEEN, LOAD_TS
FROM AIRBNB_INVESTMENT_DB.BRONZE.LOAD_AUDIT
ORDER BY LOAD_TS DESC;

-- rows silently skipped by ON_ERROR = CONTINUE (should be 0)
SELECT * FROM AIRBNB_INVESTMENT_DB.BRONZE.LOAD_AUDIT WHERE ERRORS_SEEN > 0;
```

---

# Snapshots & quarterly refresh

Each quarter the Lambda writes a new `snapshot_date=<date>/` folder per city. To ingest it,
just re-run `etl/ingestion_layer/02_bronze_load.py` — `latest_snapshot()` finds and loads the
newest folder for each city independently (cities can be on different snapshot dates). No code
or manifest change is required.

---

# Project Guide

Run `setup/run_setup.py` to integrate the git workspace with the project remote repository and
set up the project database and warehouse. After that, follow the **Quick Start** above.

Next layers (not built yet): **Silver** (`etl/silver/`, cleaning + typing) and **Gold**
(`etl/gold/`, features + scoring). See [docs/architecture.md](docs/architecture.md).
