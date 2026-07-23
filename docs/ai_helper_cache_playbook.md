# AI Helper + Cache Playbook (airbnb-investment-app)

Repeatable pattern for adding a persona-based AI summary to a Streamlit page:
**page → helper → check cache → generate from GOLD tables → store in cache**.
Modeled on `2_property_types.py` (single recommendation) and
`2.1_property_types_comparison.py` / `1.1_area_comparison.py` (comparison).

## Architecture
- **Pages**: `Streamlit/airbnb-app/pages/*.py`
- **Shared helpers**: `scripts/ai/*_helper.py` (imported by pages via `sys.path`; live outside the app dir)
- **Gemini gateway**: `Streamlit/airbnb-app/gemini.py` — single `generate(prompt, api_key=None)`;
  resolves key/model from `st.secrets` (top-level `gemini_api_key`/`gemini_model`, then nested `[gemini]`)
- **Session helper**: `db.py` → `get_session()`
- **Cache tables**: `AIRBNB_INVESTMENT_DB.GOLD.<NAME>_CACHE`
- **App role**: `AIRBNB_APP_PUBLIC_ROLE` (read-only + INSERT on cache tables only)

## Step 1 — Cache table + grants
Create `setup/<name>_cache.sql` and run it as ACCOUNTADMIN:
```sql
-- <desc>
-- Co-authored with CoCo
CREATE OR REPLACE TABLE AIRBNB_INVESTMENT_DB.GOLD.<NAME>_CACHE (
    CITY            VARCHAR,
    ...             ,          -- key columns used in check_cache
    PERSONA         VARCHAR,
    AI_NARRATIVE    VARCHAR,
    MODEL_USED      VARCHAR,
    PROMPT_VERSION  VARCHAR,
    COMPUTED_AT     TIMESTAMP_NTZ
);
GRANT SELECT, INSERT ON TABLE AIRBNB_INVESTMENT_DB.GOLD.<NAME>_CACHE
    TO ROLE AIRBNB_APP_PUBLIC_ROLE;
```
Rules:
- **UPPERCASE columns** (standard identifiers) — so `check_cache` can use unquoted names.
- `CREATE OR REPLACE` **resets grants** → always keep the GRANT in the file and re-run both.
- Verify with a round-trip: `INSERT … SELECT …, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ;` then `SELECT` then `DELETE`.

## Step 2 — Helper (`scripts/ai/<name>_helper.py`)
First two lines: `# <desc>` then `# Co-authored with CoCo`.

- **Public entry**: `get_or_generate_*(session, api_key, city, <keys…>, persona)` → returns JSON string or `None`.
- **`check_cache()`** — SELECT with **bind params**, UPPERCASE columns, filter on `PROMPT_VERSION`:
  ```python
  session.sql(f"""SELECT AI_NARRATIVE FROM {DB}.{SCHEMA}.{CACHE_TABLE}
      WHERE CITY=? AND ... AND PERSONA=? AND PROMPT_VERSION=? LIMIT 1""",
      params=[city, ..., persona, PROMPT_VERSION]).to_pandas()
  # read result.iloc[0]['AI_NARRATIVE']
  ```
- **`write_to_cache()`** — parameterized **INSERT**, NOT `write_pandas` (the app role lacks the
  temp-stage/CREATE rights `write_pandas` needs; that failure is silent and leaves the cache empty):
  ```python
  session.sql(f"""INSERT INTO {DB}.{SCHEMA}.{CACHE_TABLE} (CITY,...,PROMPT_VERSION,COMPUTED_AT)
      SELECT ?,?,...,?, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ""",
      params=[...]).collect()
  # raise on failure — don't swallow
  ```
- **`call_gemini()`** — delegate to the app gateway:
  ```python
  from gemini import generate as gemini_generate
  try:
      return gemini_generate(system + '\n\n' + user, api_key=api_key)
  except Exception:
      return None
  ```
  Do NOT use `from google import genai` / `genai.Client` (that SDK isn't installed).
- **`ensure_cache_table()`** (if present) must be **best-effort** — log, never `raise`
  (app role can't CREATE; table is pre-created in Step 1).
- Persona keys are **UPPERCASE** (`YIELD_MAXIMISER`, `OCCUPANCY_OPTIMISER`, `QUALITY_HOST`).

## Step 3 — Page wiring (`pages/*.py`)
First two lines: `# <desc>` then `# Co-authored with CoCo`. Import convention (helpers live outside app dir):
```python
import os, sys, json
_SCRIPTS_AI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "ai"))
if _SCRIPTS_AI not in sys.path:
    sys.path.insert(0, _SCRIPTS_AI)
import <name>_helper as h
```
Also `from db import get_session`, and `from nav import render_breadcrumb`/`render_logo`
(import what you call!).

Call pattern:
```python
persona = st.session_state.get("persona")
api_key = st.secrets.get("gemini", {}).get("api_key")
# guard: if persona is None / not api_key -> st.info(...)
with st.spinner("Generating..."):
    narrative_json = h.get_or_generate_*(session, api_key, city, <keys>, str(persona).upper())
if narrative_json:
    data = json.loads(narrative_json)
    st.write(data.get("...", ""))   # render the helper's JSON keys
```
Optional in-memory speed layer: `@st.cache_data(ttl=3600)` wrapper with leading-underscore
`_session`/`_api_key` and a **hashable tuple** for list args (rebuild dicts inside).

## Step 4 — Deploy config
Add any new shared root module to `Streamlit/airbnb-app/snowflake.yml` `artifacts:`
(already lists `db.py`, `gemini.py`, `nav.py`). Helpers in `scripts/ai/` are loaded via `sys.path`
(present in Workspace; not in artifacts).

## Gotchas checklist
- **Column case**: `DESCRIBE TABLE` shows lowercase → columns are quoted-lowercase (created by
  `write_pandas`); need quoted `"col"` in SQL. Standard tables show UPPERCASE → use unquoted.
  New cache tables: use UPPERCASE.
- **Silent cache-miss loop** = `write_pandas` permission failure → switch to INSERT.
- **Missing INSERT grant** → `GRANT SELECT, INSERT` (siblings `LISTING_COMPARISON_CACHE`,
  `ST_VS_LT_COMPARISON_CACHE` show the pattern).
- **`NameError`** for `render_breadcrumb`/etc. → add the `from nav import …` import.
- **`ImportError: cannot import name 'genai' from 'google'`** → helper using wrong SDK; delegate to `gemini.py`.
- **Trial account**: External Access Integrations are blocked, so live Gemini calls only work
  **outside** Snowflake (Community Cloud with `[gemini] api_key`). Inside SiS, only pre-cached rows
  render. `setup/gemini_external_access.sql` is ready for a non-trial account.
- **Attribution**: every `.sql`/`.py` needs `-- Co-authored with CoCo` / `# Co-authored with CoCo`
  in the first two lines.
- **GOLD data source tables** (from `SHARED_AI_DB.GOLD`, copied via `setup/copy_shared_gold.sql`):
  `BOROUGH_SUMMARY`, `REVIEW_THEMES`, `INVESTMENT_SCORES`, plus local `MART_*`
  (`MART_LISTING_CANDIDATES`, `MART_BEDROOMS`, `MART_ST_VS_LT`, `MART_PROPERTY_SEASONAL`).

## Current examples to copy from
| Page | Helper | Cache table | Public fn |
|---|---|---|---|
| `2_property_types.py` | `property_type_helper.py` | `PROPERTY_TYPE_CACHE` | `get_or_generate_recommendation` |
| `2.1_property_types_comparison.py` | `property_types_comparison_helper.py` | `PROPERTY_COMPARISON_CACHE` | `get_or_generate_comparison` |
| `1.1_area_comparison.py` | `area_comparison_helper.py` | `ST_VS_LT_COMPARISON_CACHE` | `get_or_generate_comparison` |
| `3_listing_candidates.py` | `listing_comparison_helper.py` | `LISTING_COMPARISON_CACHE` | `get_or_generate_comparison` |
