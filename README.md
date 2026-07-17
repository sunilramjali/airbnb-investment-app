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
| 7 | Load Overture Places POIs into Bronze | `etl/ingestion_layer/05_overture_poi_load.sql` | every load |
| 8 | Load OS Code-Point postcodes into Bronze | `etl/ingestion_layer/06_code_point_load.sql` | every load |
| 9 | Create ONS rent stage + xlsx parse proc | `etl/ingestion_layer/07_ons_private_rent_ddl.sql` | once |
| 10 | Load ONS private rents into Bronze | `etl/ingestion_layer/08_ons_private_rent_load.sql` | every load |

Once Bronze is loaded, build the upper layers:

| # | Step | File | When |
|---|------|------|------|
| 11 | Build Silver (`*_CLEANED` tables) | `etl/cleaning_layer/cleaning_layer.py` | every build |
| 12 | Build Gold (star + app marts) | `etl/aggregation_layer/aggregation_layer.py` | every build |

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
2. `02_silver_listings.sql` → `14_silver_neighbourhood_ons_area_map.sql` — one cleaning transform
   each (listings, calendar, reviews, neighbourhoods, neighbourhoods-geo, price-paid, POI,
   code-point, property-group map, amenities, postcode→neighbourhood map, ONS private rents,
   neighbourhood→ONS-area crosswalk).

### What it produces

```text
AIRBNB_INVESTMENT_DB.SILVER
├── LISTINGS_CLEANED              # from BRONZE.RAW_LISTINGS
├── CALENDAR_CLEANED             # from BRONZE.RAW_CALENDAR
├── REVIEWS_CLEANED              # from BRONZE.RAW_REVIEWS
├── NEIGHBOURHOODS_CLEANED       # from BRONZE.RAW_NEIGHBOURHOODS
├── NEIGHBOURHOODS_GEO_CLEANED   # from BRONZE.RAW_NEIGHBOURHOODS_GEO (GeoJSON -> GEOGRAPHY)
├── PRICE_PAID_CLEANED           # from BRONZE.RAW_PRICE_PAID (HM Land Registry; London/Manchester/Bristol only)
├── POI_CLEANED                  # from BRONZE.RAW_OVERTURE_POI (investment-relevant amenities + GEOGRAPHY)
├── CODE_POINT_CLEANED           # from BRONZE.RAW_CODE_POINT (postcodes -> normalized POSTCODE_KEY)
├── PROPERTY_GROUP_MAP           # property_type -> property_group lookup
├── LISTING_AMENITIES            # from BRONZE.RAW_LISTINGS (exploded listing × amenity, classified)
├── POSTCODE_NEIGHBOURHOOD_MAP   # postcode -> neighbourhood spatial bridge (point-in-polygon)
├── ONS_PRIVATE_RENT_CLEANED     # from BRONZE.RAW_ONS_PRIVATE_RENT (tidy-long rent panel; London/Manchester/Bristol)
├── NEIGHBOURHOOD_ONS_AREA_MAP   # neighbourhood -> ONS area crosswalk (exact/broadcast rent_grain)
└── CLEAN_AUDIT                  # one row per table per run (rows in/out/dropped)
```

> **`PRICE_PAID_CLEANED` specifics.** HM Land Registry Price Paid sales, typed and decoded
> (property type, tenure, build status, PPD category as readable labels), deduped by
> transaction id. It is **restricted at clean time** to the three investment areas —
> `COUNTY IN ('GREATER LONDON', 'GREATER MANCHESTER', 'CITY OF BRISTOL')` — where
> `GREATER LONDON` covers *all* of London (City of London is a district within it). A
> deterministic `quality_flag` column marks each row `ok` (~80%, arm's-length market sale),
> `non_standard` (~20%, PPD category B — repossessions, portfolio/company transfers), or
> `price_suspect` (<0.1%, price outside £10k–£20M sanity bounds). Filter
> `WHERE quality_flag = 'ok'` for true market price stats. Because the county filter runs
> inside the transform, this table's `CLEAN_AUDIT.ROWS_DROPPED` is large (~4.4M) by design —
> that is the non-target counties plus validation.

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

# Silver → Gold (Aggregation) — User Guide

The **gold layer** turns the clean `SILVER.*_CLEANED` tables into the **app-ready** GOLD
schema: a Kimball **star** (dimensions + facts) plus **denormalised marts** the app reads
directly. It lives in `etl/aggregation_layer/` and is driven by a single Python file.

### Prerequisites

1. Silver must be built first — run `etl/cleaning_layer/cleaning_layer.py`.
2. **Change tracking must be enabled** on the SILVER source tables that feed the dynamic
   tables, or the refresh fails with *"Change tracking is not enabled..."*:
   ```sql
   ALTER TABLE SILVER.LISTINGS_CLEANED           SET CHANGE_TRACKING = TRUE;
   ALTER TABLE SILVER.CALENDAR_CLEANED           SET CHANGE_TRACKING = TRUE;
   ALTER TABLE SILVER.POI_CLEANED                SET CHANGE_TRACKING = TRUE;
   ALTER TABLE SILVER.NEIGHBOURHOODS_GEO_CLEANED SET CHANGE_TRACKING = TRUE;
   ALTER TABLE SILVER.ONS_PRIVATE_RENT_CLEANED   SET CHANGE_TRACKING = TRUE;
   ALTER TABLE SILVER.NEIGHBOURHOOD_ONS_AREA_MAP SET CHANGE_TRACKING = TRUE;
   ```

### How to run

Open `etl/aggregation_layer/aggregation_layer.py` in a Snowflake Workspace and run it. It
uses `get_active_session()` (no credentials) on `AIRBNB_APP_WH` and executes, in order:

1. `01_dimensions.sql` — conformed dimensions + generated `DIM_DATE`.
2. `02_facts.sql` — facts at listing / listing×date grain.
3. `03_app_marts.sql` — the app-facing consumer marts.

It prints a `COUNT(*)` for every object it builds.

### What it produces

```text
AIRBNB_INVESTMENT_DB.GOLD
├── DIM_LISTING            # one row per listing (+ GEO_POINT, STRUCTURE_CLASS, PROPERTY_GROUP)
├── DIM_HOST               # one row per host
├── DIM_NEIGHBOURHOOD      # one row per neighbourhood (+ CITY, BOUNDARY geography, AREA_SQKM)
├── DIM_PROPERTY_GROUP     # the 7 property groups (selection lookup)
├── DIM_POI                # points of interest (+ LOCATION geography)
├── DIM_DATE               # generated calendar dimension (static table)
├── FCT_LISTING_SNAPSHOT   # per-listing investment metrics (ADR, occupancy, revenue, RevPAR)
├── FCT_CALENDAR_DAILY     # daily availability per listing (listing × date)
├── FCT_LISTING_POI        # POI proximity counts per listing (500m)
├── FCT_AREA_SALE_PRICE    # median/avg sale price per neighbourhood × structure_class (HM Land Registry)
├── FCT_AREA_RENT          # observed ONS rent per neighbourhood × category (overall/structure/bedroom)
│
├── MART_LISTING_CANDIDATES # APP: denormalised per-listing (detail + comparison screens)
├── MART_AREA_OVERVIEW      # APP: per-neighbourhood summary + map boundary (area overview)
├── MART_PROPERTY_GROUP     # APP: neighbourhood × property group (+ median sale-price cost)
├── MART_AREA_POI           # APP: per-POI map markers inside each neighbourhood
├── MART_AREA_STRATEGY      # APP: ST (Airbnb) vs LT (let) gross-yield per neighbourhood × structure_class
└── MART_AREA_STRATEGY_BEDROOMS # APP: the same ST-vs-LT comparison, faceted by bedroom bucket
```

### How the app consumes it

The app reads the **GOLD marts only** (`MART_*`), on `AIRBNB_APP_WH`, with **no
query-time joins** — the marts are already denormalised, one per screen:

| Screen | Mart |
|--------|------|
| Home (KPIs + maximiser leaderboards) | `MART_AREA_OVERVIEW` + `MART_LISTING_CANDIDATES` |
| Area Overview (stats + map) | `MART_AREA_OVERVIEW` + `MART_AREA_POI` (map markers) |
| Property selection (per group + cost) | `MART_PROPERTY_GROUP` |
| Listing Comparison | `MART_LISTING_CANDIDATES` |
| Area Strategy (ST vs LT yield, incl. by bedroom) | `MART_AREA_STRATEGY` + `MART_AREA_STRATEGY_BEDROOMS` |

Three usage notes:
- **`HAS_REVENUE_DATA`** — 34% of listings have no `price`/revenue in the source scrape.
  Filter `WHERE HAS_REVENUE_DATA = TRUE` for any revenue-ranked view; the flag keeps the
  rest visible without fabricating numbers.
- **Cost benchmark** — `AREA_MEDIAN_SALE_PRICE` (listing) and `MEDIAN_SALE_PRICE` (area)
  come from HM Land Registry, matched by neighbourhood × Flat/House.
- **Long-term rent (ONS)** — `MART_AREA_STRATEGY(_BEDROOMS)` now compare short-term (Airbnb)
  vs long-term (let) **gross yield** using *observed* ONS rents (`GOLD.FCT_AREA_RENT`), not a
  flat per-city assumption. `LT_GROSS_YIELD_PCT = ONS annual rent / median sale price`, and
  `LT_RENT_SOURCE` flags each row `observed` or `assumed` (the per-city assumption is the
  documented fallback where ONS has no figure — e.g. City of London, or Studio/Unknown bedroom
  buckets). ONS is local-authority grain, so `FCT_AREA_RENT.RENT_GRAIN` marks whether a rent is
  `exact` (London borough / GM district) or `broadcast` (shared across Manchester/Bristol wards).

### Refresh model

Gold uses **dynamic tables** so Snowflake refreshes incrementally. The **marts** carry the
explicit `TARGET_LAG = '1 day'` freshness anchor; the upstream **dims/facts** use
`TARGET_LAG = DOWNSTREAM` and refresh only as needed to serve the marts.
(`FCT_CALENDAR_DAILY` keeps its own `'1 day'` lag as nothing consumes it yet.)

### Adding a new gold object

1. Add the `CREATE OR REPLACE DYNAMIC TABLE ...` to the relevant SQL file
   (`01_dimensions.sql` / `02_facts.sql` / `03_app_marts.sql`).
2. Add its fully-qualified name to that step's `produces` list in `aggregation_layer.py`
   so the runner verifies its row count.

---

