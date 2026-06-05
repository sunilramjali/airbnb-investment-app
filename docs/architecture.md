# Project Architecture

This document is the **map of the whole project** — it shows how the folders fit together,
how data flows through the pipeline, and who owns what. Read this first to understand the
big picture, then dive into the linked docs for details.

- New to `src/`? → [what_is_src.md](what_is_src.md)
- How we use Git/branches? → [branching_strategy.md](branching_strategy.md)

> **Status:** This describes the *target* structure we are building toward. Some folders
> (`src/`, `tests/`, `app/`, the numbered notebook folders) may not exist yet — they are
> created as each part of the project is built.

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

| Layer | Folder | Holds | Example files |
|-------|--------|-------|---------------|
| Bronze | `data/bronze/` | Raw / lightly standardised | `listings.csv`, `reviews.csv`, `calendar.csv`, `neighbourhoods.geojson` |
| Silver | `data/silver/` | Cleaned & validated | `listings_cleaned.csv`, `reviews_cleaned.csv` |
| Gold | `data/gold/` | Final app-ready outputs | `app_ready_dataset.csv`, `investment_scores.csv`, `area_summary.csv` |

---

## Folder layout

```text
airbnb-investment-app/
├── README.md            # main project guide (start here)
├── CHEATSHEET.md        # quick copy-paste commands
├── requirements.txt     # Python packages
├── setup.py             # makes src/ importable (pip install -e .)
│
├── data/                # datasets (gitignored — not uploaded to GitHub)
│   ├── bronze/          # raw
│   ├── silver/          # cleaned
│   └── gold/            # app-ready
│
├── notebooks/           # exploration + running the pipeline, by stage
│   ├── 01_bronze_ingestion/
│   ├── 02_silver_cleaning/
│   ├── 03_gold_features/
│   ├── 04_analysis/
│   └── 05_modelling/
│
├── src/                 # reusable code the notebooks & app import (the "kitchen")
│   ├── config.py        # data paths in one place
│   ├── ingestion.py     # load raw data
│   ├── cleaning.py      # clean each dataset
│   ├── features.py      # area summaries, investment score
│   └── modelling.py     # review sentiment, scoring model
│
├── tests/               # pytest checks for src/ functions
├── app/                 # Streamlit app (reads data/gold only)
│
└── docs/                # project documentation
    ├── architecture.md      # ← you are here
    ├── what_is_src.md
    ├── branching_strategy.md
    └── data_sources.md      # where the raw data came from
```

---

## What each top-level folder is for

- **`data/`** — all datasets, split into bronze/silver/gold. Ignored by Git (too large /
  recreatable). See `data_sources.md` for where the raw files came from.
- **`notebooks/`** — where we *explore* data and *run* the pipeline, organised by stage so
  the data flow reads top-to-bottom. One notebook = one focused job.
- **`src/`** — the reusable logic notebooks and the app share. Full explanation in
  [what_is_src.md](what_is_src.md).
- **`tests/`** — automated checks (`pytest`) that the `src/` functions behave correctly.
- **`app/`** — the Streamlit dashboard users see. It only reads from `data/gold/`.
- **`docs/`** — guides for the team (this file, the Git workflow, the `src/` guide).

---

## Who owns what (role → folder)

Roles come from [branching_strategy.md](branching_strategy.md). Each role mainly works in
these areas:

| Role | Works in | Produces |
|------|----------|----------|
| Data Engineer | `notebooks/01–03`, `src/ingestion,cleaning,features` | bronze → silver → gold data |
| Data Analyst | `notebooks/04_analysis/` | EDA, price/location insights, metrics |
| AI Engineer | `notebooks/05_modelling/`, `src/modelling.py` | review sentiment, scoring model |
| Frontend Dev | `app/` | the Streamlit dashboard |
| QA Tester | `tests/` | validation of data & `src/` functions |

This keeps two people from editing the same file at once, which reduces merge conflicts.

---

## Rules everyone follows

1. **Data flows downward only:** bronze → silver → gold. Never overwrite bronze by hand.
2. **The app reads gold only** — never bronze or silver.
3. **Logic lives in `src/`, not copy-pasted across notebooks** (see [what_is_src.md](what_is_src.md)).
4. **No hardcoded paths** — import them from `src/config.py`.
5. **One notebook = one focused job**, with a number prefix so order is clear.
6. **Never commit** `data/`, `.venv/`, `.env`, secrets, or `.ipynb_checkpoints/`.
7. **No direct pushes to `main`** — branch + Pull Request (see [branching_strategy.md](branching_strategy.md)).

---

## How a change flows through the project (example)

> Goal: add an "investment score" column the app can show.

1. **Silver** — `src/cleaning.clean_listings()` produces clean listings (notebook in `02_`).
2. **Gold** — `src/features.investment_score()` computes the score; a `03_gold_features/`
   notebook writes `data/gold/investment_scores.csv`.
3. **Test** — `tests/test_features.py` checks the score is between 0 and 100.
4. **App** — `app/main.py` imports `investment_score` results and displays them.

The same `investment_score()` function powers the gold dataset, the test, and the app — so
they can never disagree.
