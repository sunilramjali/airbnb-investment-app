# Project Architecture

This document is the **map of the whole project** — it shows how the folders fit together,
how data flows through the pipeline, and who owns what. Read this first to understand the
big picture, then dive into the linked docs for details.

- New to `src/`? → [what_is_src.md](what_is_src.md)
- How we use Git/branches? → [branching_strategy.md](branching_strategy.md)

> **Runtime reality:** the project runs **inside Snowflake** (Snowpark
> `get_active_session()`). Data lives in Snowflake **schemas** (BRONZE / SILVER / GOLD), not a
> local `data/` folder, and there is no `.venv` / `requirements.txt` for the pipeline (see
> README "Where This Runs"). The reusable logic lives in `config/` + `etl/`, not a `src/` folder.

---

## The big idea: Bronze → Silver → Gold

We use a **medallion architecture** — data moves through three quality layers, getting
cleaner and more useful at each step:

```text
   Raw source files
          │
          ▼
   🥉 BRONZE   raw data, lightly standardised   ("what did we receive?")
          │     clean it
          ▼
   🥈 SILVER   cleaned & validated data          ("is it analysis-ready?")
          │     aggregate / score it
          ▼
   🥇 GOLD     final app-ready datasets          ("what does the app show?")
          │
          ▼
   📊 App / dashboard / analysis
```

**Golden rule:** data only flows **downward**. Never edit bronze by hand; cleaned data goes
to silver; final app-ready data goes to gold. The app reads from **gold only**.

| Layer | Snowflake schema | Holds | Example tables |
|-------|------------------|-------|----------------|
| Bronze | `BRONZE` | Raw / lightly standardised | `RAW_LISTINGS`, `RAW_REVIEWS`, `RAW_CALENDAR`, `RAW_NEIGHBOURHOODS_GEO`, `RAW_PRICE_PAID`, `RAW_OVERTURE_POI`, `RAW_CODE_POINT`, `RAW_ONS_PRIVATE_RENT` |
| Silver | `SILVER` | Cleaned & validated | `LISTINGS_CLEANED`, `CALENDAR_CLEANED`, `REVIEWS_CLEANED`, `NEIGHBOURHOODS_CLEANED`, `NEIGHBOURHOODS_GEO_CLEANED`, `PRICE_PAID_CLEANED`, `POI_CLEANED`, `CODE_POINT_CLEANED`, `PROPERTY_GROUP_MAP`, `LISTING_AMENITIES`, `POSTCODE_NEIGHBOURHOOD_MAP`, `ONS_PRIVATE_RENT_CLEANED`, `NEIGHBOURHOOD_ONS_AREA_MAP` |
| Gold | `GOLD` | Star (dims + facts) + app-ready marts | `DIM_LISTING`, `DIM_HOST`, `DIM_NEIGHBOURHOOD`, `DIM_PROPERTY_GROUP`, `DIM_POI`, `DIM_CITY_ASSUMPTIONS`, `DIM_DATE`, `FCT_LISTING_SNAPSHOT`, `FCT_CALENDAR_DAILY`, `FCT_LISTING_POI`, `FCT_AREA_SALE_PRICE`, `FCT_AREA_RENT`, `MART_LISTING_CANDIDATES`, `MART_AREA_OVERVIEW`, `MART_AREA_POI`, `MART_AREA_SEASONAL`, `MART_PROPERTY_TYPE`, `MART_BEDROOMS`, `MART_PROPERTY_SEASONAL`, `MART_ST_VS_LT`, `MART_AREA_AMENITIES`, `MART_AREA_AMENITY_GAP` |

---

## Why this design

The pipeline combines four well-known patterns, each chosen for a specific reason:

- **Medallion architecture** (Bronze → Silver → Gold). Data flows one direction and each
  layer has one job, so failures and fixes stay localised — you can rebuild Gold without
  re-ingesting, or fix a cleaning bug without touching raw data.
- **Kimball dimensional modelling** (the `DIM_*` / `FCT_*` star). Conformed dimensions are
  reused across many facts (one `DIM_LISTING` serves the snapshot, POI, and calendar
  facts), which is query-efficient and analyst-friendly.
- **Denormalised data marts / serving layer** (the `MART_*` tables). The joins and
  aggregates are computed *once* at refresh time and stored in the shape each app screen
  needs, so the app does trivial single-table `SELECT`s — low, predictable latency and no
  duplicated metric logic. (This mirrors the **CQRS** idea: separate the write/transform
  model from the read model.)
- **Incremental dynamic tables with `DOWNSTREAM` chaining**. You declare *what* each table
  is and a freshness target; Snowflake decides *how* and *when* to refresh. The marts carry
  the explicit lag anchor and upstream layers refresh only as needed — no hand-written
  orchestration, no redundant full rebuilds.

In short: a **medallion pipeline with a Kimball star at the core and a denormalised,
materialised serving layer on top**, refreshed incrementally — a single source of truth for
every metric, with all the expensive work pushed to refresh time so reads stay cheap.

---

## Folder layout

```text
airbnb-investment-app/
├── README.md            # main project guide (start here)
│
├── config/              # shared helpers
│   ├── snowflake_context.py   # session + warehouse helpers
│   ├── run_sql_file.py        # client-side SQL runner
│   └── ingestion_manifest.py  # declarative list of Bronze datasets
│
├── setup/               # one-time DB/warehouse/integration setup
│   ├── run_setup.py
│   ├── 00_setup_api_integration.sql
│   ├── 01_setup_database_and_warehouse.sql
│   └── 02_public_service_user.sql
│
├── etl/                 # the pipeline, by layer (Bronze + Silver + Gold)
│   ├── ingestion_layer/
│   │   ├── 01_bronze_ddl.sql           # Airbnb file formats + S3 integration + stage (run once)
│   │   ├── 02_bronze_load.py           # generic Airbnb loader, driven by the manifest
│   │   ├── 03_land_registry_ddl.sql    # Land Registry headerless format + stage (run once)
│   │   ├── 04_land_registry_load.sql   # Land Registry table + COPY + audit (run each load)
│   │   ├── 05_overture_poi_load.sql    # Overture Places POIs (Marketplace share; scoped to boroughs)
│   │   ├── 06_code_point_load.sql      # OS Code-Point Open postcodes (Marketplace share; full GB copy)
│   │   ├── 07_ons_private_rent_ddl.sql # ONS Private Rents stage + openpyxl parse proc (run once)
│   │   └── 08_ons_private_rent_load.sql# ONS Private Rents table + CALL parse (run each load)
│   ├── cleaning_layer/                 # Silver transforms, driven by cleaning_layer.py
│   │   ├── 01_silver_ddl.sql           # SILVER schema + CLEAN_AUDIT
│   │   ├── 02..10_silver_*.sql         # listings, calendar, reviews, neighbourhoods(+geo), price_paid, POI, code_point, property_group_map
│   │   ├── 11_silver_amenities.sql     # exploded listing × amenity, classified into AMENITY_GROUPs
│   │   ├── 12_silver_postcode_neighbourhood_map.sql  # postcode -> neighbourhood spatial bridge
│   │   ├── 13_silver_ons_private_rent.sql            # ONS private rent panel (tidy-long)
│   │   └── 14_silver_neighbourhood_ons_area_map.sql  # neighbourhood -> ONS area crosswalk
│   └── aggregation_layer/              # Gold star + app marts, driven by aggregation_layer.py
│       ├── 01_dimensions.sql           # DIM_* conformed dimensions + DIM_CITY_ASSUMPTIONS + DIM_DATE
│       ├── 02_facts.sql                # FCT_* at listing / listing×date / area grain
│       ├── 03_app_marts_core.sql       # MART_LISTING_CANDIDATES, MART_AREA_OVERVIEW, MART_AREA_POI, MART_AREA_SEASONAL
│       ├── 04_app_marts_property.sql   # MART_PROPERTY_TYPE, MART_BEDROOMS, MART_PROPERTY_SEASONAL
│       ├── 05_app_marts_strategy.sql   # MART_ST_VS_LT (ST vs LT yield comparison)
│       └── 06_app_marts_amenities.sql  # MART_AREA_AMENITIES, MART_AREA_AMENITY_GAP
│
├── scripts/             # offline / local scripts
│   └── ai/              # AI narrative & recommendation generation (Gemini)
│
├── notebooks/           # exploration + running the pipeline
│
├── Streamlit/           # the Streamlit app (reads GOLD schema only)
│   └── airbnb-app/      # multi-page app (landing, area overview, property types, listings, docs)
│
└── docs/                # project documentation
    ├── architecture.md      # ← you are here
    ├── what_is_src.md       # note: src/ is aspirational; today logic lives in config/ + etl/
    ├── branching_strategy.md
    └── data_sources.md      # where the raw data came from

# Data itself is NOT in this repo — it lives in Snowflake schemas:
#   AIRBNB_INVESTMENT_DB.{BRONZE, SILVER, GOLD}
```

---

## What each top-level folder is for

- **Data** — lives in Snowflake schemas (BRONZE / SILVER / GOLD), **not** a local `data/`
  folder. See `data_sources.md` for where the raw files came from.
- **`config/`** — shared helpers (session, SQL runner, ingestion manifest) every layer imports.
- **`setup/`** — one-time database, warehouse, and integration setup.
- **`etl/`** — the pipeline itself, by layer (Bronze loader + Silver cleaning + Gold aggregation).
- **`scripts/`** — offline scripts (AI narrative/recommendation generation via Gemini).
- **`notebooks/`** — exploration notebooks and pipeline execution.
- **`Streamlit/`** — the multi-page Streamlit dashboard. It only reads from the GOLD schema.
- **`docs/`** — guides for the team (this file, the Git workflow, the shared-logic guide).

---

## Who owns what (role → folder)

Roles come from [branching_strategy.md](branching_strategy.md). Each role mainly works in
these areas:

| Role | Works in | Produces |
|------|----------|----------|
| Data Engineer | `etl/`, `config/` | bronze → silver → gold tables |
| Data Analyst | `notebooks/` | EDA, price/location insights, metrics |
| AI Engineer | `scripts/ai/`, `notebooks/` | narratives, recommendations, scoring |
| Frontend Dev | `Streamlit/airbnb-app/` | the Streamlit dashboard |

This keeps two people from editing the same file at once, which reduces merge conflicts.

---

## Rules everyone follows

1. **Data flows downward only:** BRONZE → SILVER → GOLD. Never overwrite Bronze by hand.
2. **The app reads the GOLD schema only** — never Bronze or Silver.
3. **Logic lives in shared modules (`config/` + `etl/`), not copy-pasted across notebooks** (see [what_is_src.md](what_is_src.md)).
4. **No hardcoded connection details** — use `config/snowflake_context.py`.
5. **One notebook / one script = one focused job**, 
