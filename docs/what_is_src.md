# What is the `src/` Folder?

## In one sentence

`src/` is where we keep our **reusable Python code** — the functions that actually *do the
work* — so that every notebook and the app can share the same code instead of copy-pasting it.

---

## The kitchen analogy 🍳

Imagine a restaurant:

- **`src/` is the kitchen** — this is where the food (the real logic) gets cooked.
- **Notebooks and the app are the dining tables** — they don't cook, they just *order* from
  the kitchen and serve the result.

If every table cooked its own food, you'd have 10 slightly different versions of the same
dish. With one kitchen, everyone gets the *same* dish, made the *same* way, every time.

That's `src/`: write the logic **once**, use it **everywhere**.

---

## Why bother? The problem it solves

Without `src/`, the same code gets copy-pasted into many notebooks:

```python
# notebook 1
listings['price'] = listings['price'].str.replace('$','').astype(float)
# notebook 2 (someone pasted the same line...)
# notebook 3 (...and again)
```

When the data changes, you must fix it in **every** notebook — and you *will* miss one.

With `src/`, the logic lives in one place:

```python
# src/cleaning.py
def clean_listings(df):
    df['price'] = df['price'].str.replace('$','').astype(float)
    return df
```

and every notebook just *calls* it:

```python
from src.cleaning import clean_listings
listings = clean_listings(listings)
```

Fix it once → everyone gets the fix. ✅

---

## What goes in `src/` vs what stays in a notebook?

| Put in `src/` (the kitchen)        | Keep in the notebook (the table)        |
|------------------------------------|-----------------------------------------|
| Cleaning/transform functions        | Looking at the data (`.head()`, charts) |
| The investment scoring formula      | Trying ideas / experimenting            |
| File paths (in `config.py`)         | Telling the "story" of the analysis     |
| Loading & saving data               | One-off checks                          |

**Rule of thumb:** if you'd copy-paste it into a second notebook, it belongs in `src/`.

---

## How `src/` is used at each stage of our project

Our pipeline flows **Bronze → Silver → Gold → Analysis → App**. `src/` helps at every stage:

| Stage | Notebook folder | `src/` file it calls | Example |
|-------|-----------------|----------------------|---------|
| **1. Ingestion (bronze)** | `01_bronze_ingestion/` | `src/ingestion.py` | `load_bronze("listings")` |
| **2. Cleaning (silver)**  | `02_silver_cleaning/`  | `src/cleaning.py`   | `clean_listings(df)` |
| **3. Features (gold)**    | `03_gold_features/`    | `src/features.py`   | `area_summary(df)` |
| **4. Analysis**           | `04_analysis/`         | `src/features.py`   | `investment_score(df)` |
| **5. Modelling**          | `05_modelling/`        | `src/modelling.py`  | `review_sentiment(text)` |
| **6. The App**            | `app/main.py`          | all of the above    | shows results to users |

The big win: the **same** `investment_score()` function is used by the analyst's notebook,
the QA tests, **and** the Streamlit app — so they can never disagree.

---

## One shared file you'll use constantly: `config.py`

Instead of writing file paths by hand (which break when you move a notebook into a folder):

```python
# ❌ fragile
listings = pd.read_csv('../data/bronze/listings.csv')
```

we keep paths in one place:

```python
# src/config.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = ROOT / "data" / "bronze"
SILVER_DIR = ROOT / "data" / "silver"
GOLD_DIR   = ROOT / "data" / "gold"
```

and use it like:

```python
# ✅ works from ANY notebook, any folder
from src.config import BRONZE_DIR
listings = pd.read_csv(BRONZE_DIR / "listings.csv")
```

---

## How to use `src/` (one-time setup)

From the project root, run this once after activating your virtual environment:

```bash
pip install -e .
```

This makes `src` importable from anywhere, so `from src.cleaning import clean_listings`
just works — in notebooks, the app, and tests. You only do this once per machine.

---

