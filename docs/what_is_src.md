# Where Reusable Logic Lives (the `src/` idea, Snowflake-native)

## In one sentence

Reusable logic — the code that actually *does the work* — lives in **shared Python modules**
so that every notebook and the app call the same code instead of copy-pasting it. The classic
name for that folder is `src/`. **In this project that role is filled by `config/` (shared
helpers) and `etl/` (the pipeline)**, and the work is executed through **Snowpark + SQL inside
Snowflake**, not local pandas.

> Why not a literal `src/`? Because we don't run pandas on a laptop reading `data/*.csv`.
> We run inside Snowflake: a Snowpark `session` sends SQL/Snowpark to the warehouse, and data
> lives in the BRONZE / SILVER / GOLD **schemas**. The *principle* below is identical; only the
> mechanics differ.

---

## The kitchen analogy 🍳

Imagine a restaurant:

- **Shared modules (`config/`, `etl/`) are the kitchen** — where the real logic gets cooked.
- **Notebooks and the app are the dining tables** — they don't cook, they *order* from the
  kitchen and serve the result.

If every table cooked its own food, you'd have 10 slightly different versions of the same
dish. With one kitchen, everyone gets the *same* dish, made the *same* way, every time.

Write the logic **once**, use it **everywhere**.

---

## The problem it solves

Without shared modules, the same logic gets copy-pasted across notebooks and breaks the moment
the data changes — and you *will* miss a copy. For example, a price-cleaning step repeated by
hand in three notebooks. Instead, it lives once as a SILVER transform (a SQL file or a Snowpark
function in `etl/`), and every consumer calls the same thing. Fix it once → everyone gets the fix. ✅

---

## What goes in a shared module vs what stays in a notebook?

| Put in a shared module (the kitchen)        | Keep in the notebook (the table)        |
|---------------------------------------------|-----------------------------------------|
| Load/COPY logic (`etl/02_bronze_load.py`)      | Looking at the data (`.show()`, charts) |
| Cleaning / typing transforms (SILVER)       | Trying ideas / experimenting            |
| The investment scoring formula (GOLD)       | Telling the "story" of the analysis     |
| Session / warehouse / stage config          | One-off checks                          |

**Rule of thumb:** if you'd copy-paste it into a second notebook, it belongs in a shared module.

---

## How it maps to our pipeline

Our pipeline flows **Bronze → Silver → Gold → Analysis → App**, all inside Snowflake:

| Stage | Where it runs | Shared module it uses | Example |
|-------|---------------|-----------------------|---------|
| **1. Ingestion (Bronze)** | `etl/01_bronze_ddl.sql` + `etl/02_bronze_load.py` | `config/ingestion_manifest.py` | `run(session)` loads every file/city |
| **2. Cleaning (Silver)**  | `etl/silver/` *(later)* | shared transforms | cast `price`, dedupe, type dates |
| **3. Features (Gold)**    | `etl/gold/` *(later)*   | shared transforms | area summaries, investment score |
| **4. Analysis**           | `notebooks/`            | reads GOLD schema     | price/location insights |
| **5. Modelling**          | `notebooks/` *(later)*  | model code            | review sentiment |
| **6. The App**            | `app/main.py` *(later)* | reads GOLD schema only | shows results to users |

The win: the **same** scoring logic powers the analyst's notebook, the QA checks, **and** the
Streamlit app — so they can never disagree.

---

## The shared helper you'll use constantly: `config/snowflake_context.py`

Instead of repeating connection/warehouse boilerplate in every file, it lives in one place:

```python
# config/snowflake_context.py  (already in the repo)
from snowflake.snowpark.context import get_active_session

WAREHOUSES = {"dev": "AIRBNB_DEV_WH", "query": "AIRBNB_APP_WH"}

def get_session(warehouse="dev"):
    session = get_active_session()                 # Snowflake provides the session
    session.sql(f"USE WAREHOUSE {WAREHOUSES[warehouse]}").collect()
    return session
```

and every file just calls it:

```python
from config.snowflake_context import get_session
session = get_session("dev")        # works from notebooks, etl/, setup/
```

This is the Snowflake-native equivalent of the old `src/config.py` "paths in one place" idea —
except it centralises the **session, warehouse, and stage path**, not local file paths.

---

## How imports work (no `pip install -e .`)

Because the code runs inside Snowflake, there is **no virtual env and no `pip install -e .`**.
Files in `etl/` and `setup/` import from `config/` using a small project-root bootstrap (see the
top of `etl/02_bronze_load.py` and `setup/run_setup.py`):

```python
# walk up until we find the config/ folder, then add the root to sys.path
PROJECT_ROOT = find_project_root("config")
sys.path.insert(0, str(PROJECT_ROOT))
from config.snowflake_context import get_session
```

That makes `from config... import ...` work from any folder, no install step required.

> **Outside Snowflake?** If you ever run this locally (not the supported path), *then* you'd use
> a virtual env + `requirements.txt` and swap `get_active_session()` for `Session.builder`.
> See the README "Where This Runs" section.
