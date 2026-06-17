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

