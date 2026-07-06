# Project Architecture

This document is the **map of the whole project** — it shows how the folders fit together,
how data flows through the pipeline, and who owns what. Read this first to understand the
big picture, then dive into the linked docs for details.

- New to `src/`? → [what_is_src.md](what_is_src.md)
- How we use Git/branches? → [branching_strategy.md](branching_strategy.md)

> **Status:** This describes the *target* structure we are building toward. Some folders
> (`src/`, `tests/`, `app/`, the numbered notebook folders) may not exist yet — they are
> created as each part of the project is built.
>
> **Runtime reality:** the project runs **inside Snowflake** (Snowpark
> `get_active_session()`). Data lives in Snowflake **schemas** (BRONZE / SILVER / GOLD), not a
> local `data/` folder, and there is no `.venv` / `requirements.txt` (see README "Where This
> Runs"). The ingestion layer is built today under `config/` + `etl/`, not `src/`.

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
| Bronze | `BRONZE` | Raw / lightly standardised | `RAW_LISTINGS`, `RAW_REVIEWS`, `RAW_CALENDAR`, `RAW_NEIGHBOURHOODS_GEO` |
| Silver | `SILVER` | Cleaned & validated | `LISTINGS_CLEANED`, `REVIEWS_CLEANED` |
| Gold | `GOLD` | Final app-ready outputs | `APP_READY_DATASET`, `INVESTMENT_SCORES`, `AREA_SUMMARY` |

---

## Folder layout

```text
airbnb-investment-app/
├── README.md            # main project guide (start here)
│
├── config/              # shared helpers (EXISTS)
│   ├── snowflake_context.py   # session + warehouse helpers
│   ├── run_sql_file.py        # client-side SQL runner
│   └── ingestion_manifest.py  # declarative list of Bronze datasets
│
├── setup/               # one-time DB/warehouse/integration setup (EXISTS)
│   ├── run_setup.py
│   ├── 00_setup_api_integration.sql
│   └── 01_setup_database_and_warehouse.sql
│
├── etl/                 # the pipeline, by layer (Bronze EXISTS)
│   ├── 01_bronze_ddl.sql      # file formats + stage (run once)
│   ├── 02_bronze_load.py         # generic loader, driven by the manifest
│   ├── silver/ (later)        # cleaning / typing
│   └── gold/   (later)        # features / scoring
│
├── notebooks/           # exploration + running the pipeline
│   └── preprocessing_layer.ipynb
│
├── app/  (later)        # Streamlit app (reads GOLD schema only)
├── tests/ (later)       # validation of data & loader behaviour
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
- **`etl/`** — the pipeline itself, by layer (Bronze loader today; Silver/Gold later).
- **`notebooks/`** — where we *explore* data and *run* the pipeline. One notebook = one focused job.
- **`src/`** *(aspirational)* — the reusable-logic pattern; today that role is filled by
  `config/` + `etl/`. Full explanation in [what_is_src.md](what_is_src.md).
- **`tests/`** *(later)* — automated checks (`pytest`) for loader behaviour and data validity.
- **`app/`** *(later)* — the Streamlit dashboard users see. It only reads from the GOLD schema.
- **`docs/`** — guides for the team (this file, the Git workflow, the shared-logic guide).

---

## Who owns what (role → folder)

Roles come from [branching_strategy.md](branching_strategy.md). Each role mainly works in
these areas:

| Role | Works in | Produces |
|------|----------|----------|
| Data Engineer | `etl/` (Bronze loader today), `config/` | bronze → silver → gold tables |
| Data Analyst | `notebooks/04_analysis/` | EDA, price/location insights, metrics |
| AI Engineer | `notebooks/`, model code | review sentiment, scoring model |
| Frontend Dev | `app/` *(later)* | the Streamlit dashboard |
| QA Tester | `tests/` *(later)* | validation of data & loader behaviour |

This keeps two people from editing the same file at once, which reduces merge conflicts.

---

## Rules everyone follows

1. **Data flows downward only:** BRONZE → SILVER → GOLD. Never overwrite Bronze by hand.
2. **The app reads the GOLD schema only** — never Bronze or Silver.
3. **Logic lives in shared modules (`config/` + `etl/`), not copy-pasted across notebooks** (see [what_is_src.md](what_is_src.md)).
4. **No hardcoded connection details** — use `config/snowflake_context.py`.
5. **One notebook / one script = one focused job**, with a number prefix so order is clear.
6. **Never commit** `data/`, `.venv/`, `.env`, secrets, or `.ipynb_checkpoints/`.
7. **No direct pushes to `main`** — branch + Pull Request (see [branching_strategy.md](branching_strategy.md)).

---

## How a change flows through the project (example)

> Goal: add an "investment score" column the app can show.

1. **Silver** — a shared cleaning transform produces clean listings in the SILVER schema.
2. **Gold** — a shared scoring transform computes the score and writes
   `GOLD.INVESTMENT_SCORES`.
3. **Test** — a QA check confirms the score is between 0 and 100.
4. **App** — `app/main.py` reads `GOLD.INVESTMENT_SCORES` and displays it.

The same scoring logic powers the GOLD table, the test, and the app — so they can never disagree.
