# Git: What to Commit vs Ignore

This guide explains which files should be committed to GitHub and which should be ignored via
`.gitignore` for the Airbnb Investment App.

For the project structure and the Bronze → Silver → Gold pipeline, see
[architecture.md](architecture.md). For naming conventions and how to run the pipeline, see the
[README](../README.md).

---

## Why use `.gitignore`?

A `.gitignore` file tells Git which files and folders should **not** be uploaded. Useful because
some files are temporary, private, large, automatically generated, machine-specific, or easy to
recreate by running the code again.

Rule of thumb: **commit** code, documentation, notebooks, and small reusable files; **ignore**
private files, virtual environments, raw data, and temporary outputs.

---

## Files & folders to ignore

### `__pycache__/`
Python auto-creates these compiled-bytecode folders when you run `.py` files. They speed Python
up slightly but are not needed in Git — Python recreates them automatically.
```gitignore
__pycache__/
```

### `.env`
Stores private values (API keys, passwords, tokens). **Never** commit it, even in a private
repo. Commit a non-secret template instead (`.env.example`).
```gitignore
.env
```

### `.venv/`  *(local-only path)*
> **Snowflake-native note:** this project runs **inside Snowflake**, so there is normally **no
> `.venv` and no `requirements.txt`** — Snowflake provides the Python environment and session.
> This rule only matters if you run the code **outside** Snowflake (laptop/CI). See the README
> "Where This Runs" section.

A local virtual environment can be large and machine-specific. If you use one, ignore it and
share a `requirements.txt` instead.
```gitignore
.venv/
```

### `data/`
> **Snowflake-native note:** data lives in Snowflake schemas (BRONZE / SILVER / GOLD), **not** a
> local `data/` folder. This rule applies only if you keep local copies.

Raw datasets can be large and don't belong in Git. Document where the data came from in
`docs/data_sources.md` rather than committing the files. Large local CSV/Parquet outputs should
be ignored the same way.
```gitignore
data/
*.csv
*.parquet
```
(Keep an exception if you intentionally commit a small sample or app-ready file.)

---

## What to commit vs ignore

**Commit:**
```text
config/                    # shared helpers (session, SQL runner, ingestion manifest)
setup/                     # one-time DB/warehouse/integration setup
etl/ingestion_layer/       # the pipeline (Bronze loader today; Silver/Gold later)
notebooks/                 # exploration + running the pipeline (when added)
docs/                      # documentation
app/                       # (later) Streamlit app
tests/                     # (later) validation
README.md
.gitignore
```
(No `requirements.txt` on the Snowflake-native path — see the note above.)

**Ignore:**
```text
.venv/
.env
__pycache__/
data/
.DS_Store
```

---

## If a folder was already committed before being ignored

Adding a folder to `.gitignore` does **not** untrack it if it was already committed. To stop
tracking it without deleting it locally:
```bash
git rm -r --cached <folder_name>/
git add .gitignore
git commit -m "Add gitignore rules"
```

---

## Summary

> Commit files that help the team understand, run, and improve the project. Ignore files that are
> private, temporary, large, or automatically generated.

For this project, the most important things to commit are the pipeline code (`config/`, `setup/`,
`etl/ingestion_layer/`), notebooks, documentation, the README, and `.gitignore`.
