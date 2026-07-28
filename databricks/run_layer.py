# Databricks notebook source
# MAGIC %pip install openpyxl

# COMMAND ----------

# Single parameterised runner for every ETL layer.
# ============================================================
# Replaces run_bronze / run_silver / run_gold / run_onspd / run_ons_private_rent.
#
# USAGE
#   Job:         pass a `layer` base parameter  (bronze | silver | gold | onspd | ons_rent)
#   Interactive: set the `layer` widget, then Run All
#
# ============================================================
# WHY ONE RUNNER INSTEAD OF FIVE
# ------------------------------------------------------------
# The five previous runners each hardcoded:
#
#     PROJECT_ROOT = "/Workspace/Users/<an-email-address>/airbnb-investment-app"
#
# so nobody else could clone the repo and run it, and the author's email address
# was committed to a public repository five times over. The root is now DERIVED,
# and consolidating to one runner means that derivation lives in exactly one
# place instead of being copy-pasted five times.
#
# ⚠️ CELL ORDER IS LOAD-BEARING. `%pip install` RESTARTS THE PYTHON INTERPRETER,
#    discarding every variable, sys.path entry and chdir set before it. It is
#    therefore the FIRST cell, before any state is established. Moving it below
#    the PROJECT_ROOT derivation would silently wipe that derivation and the
#    notebook would fail on `import config...` with no obvious cause.
#
#    The install is unconditional because a notebook magic cannot live inside an
#    `if`. Only ons_rent needs openpyxl (it parses the ONS .xlsx workbook; the
#    Snowflake original declared it in the procedure's PACKAGES = (...) clause).
#    Making it conditional would mean a second runner — the exact duplication
#    this file removes — so a few seconds on every run is the cheaper trade.
# ============================================================

import importlib.util
import os
import sys

# COMMAND ----------

dbutils.widgets.dropdown(  # noqa: F821
    "layer", "bronze", ["bronze", "silver", "gold", "onspd", "ons_rent"], "Layer to run"
)

# COMMAND ----------

# ============================================================
# HOW PROJECT_ROOT IS FOUND (first strategy yielding a real directory wins)
# ------------------------------------------------------------
#   1. AIRBNB_PROJECT_ROOT environment variable — explicit override for jobs, CI
#      or an unusual layout. Always wins.
#   2. This notebook's own workspace path, two levels up. Works for BOTH Git
#      folder layouts (/Workspace/Repos/<user>/… and /Workspace/Users/<email>/…)
#      because it never assumes which one it is sitting in.
#   3. Walk up from the working directory looking for `config/` — the same
#      marker-directory trick the loaders already use in find_project_root().
#
# If all three fail it RAISES, listing what it tried. It deliberately does not
# fall back to a guess: a wrong root surfaces as a confusing ImportError deep
# inside a loader rather than as "I could not find the project".
# ============================================================


def _has_project(path: str) -> bool:
    """A real project root contains both config/ and databricks/."""
    return bool(path
                and os.path.isdir(os.path.join(path, "config"))
                and os.path.isdir(os.path.join(path, "databricks")))


def find_project_root() -> str:
    tried = []

    override = os.environ.get("AIRBNB_PROJECT_ROOT")
    if override:
        tried.append(f"AIRBNB_PROJECT_ROOT={override}")
        if _has_project(override):
            return override

    try:
        nb = (dbutils.notebook.entry_point.getDbutils()  # noqa: F821
              .notebook().getContext().notebookPath().get())
        # notebookPath is workspace-relative ('/Users/…' or '/Repos/…'); the FUSE
        # mount that makes it a real directory lives under /Workspace.
        candidate = "/Workspace" + os.path.dirname(os.path.dirname(nb))
        tried.append(f"notebookPath -> {candidate}")
        if _has_project(candidate):
            return candidate
    except Exception as e:            # noqa: BLE001 — any runtime lacking the API
        tried.append(f"notebookPath unavailable ({type(e).__name__})")

    d = os.getcwd()
    tried.append(f"cwd={d}")
    while True:
        if _has_project(d):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent

    raise RuntimeError(
        "Could not locate the project root. Tried:\n  - "
        + "\n  - ".join(tried)
        + "\n\nSet AIRBNB_PROJECT_ROOT to the folder containing config/ and databricks/."
    )


PROJECT_ROOT = find_project_root()
print(f"PROJECT_ROOT = {PROJECT_ROOT}")

os.chdir(PROJECT_ROOT)                 # so the loaders' own find_project_root() resolves
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)   # so `import config.databricks_context` works

# COMMAND ----------

# Loader filenames start with a digit, so they are not valid module names and are
# imported by path rather than with a plain `import`.
LAYERS = {
    "bronze":   "databricks/ingestion_layer/02_bronze_load.py",
    "onspd":    "databricks/ingestion_layer/06_onspd_load.py",
    "ons_rent": "databricks/ingestion_layer/08_ons_private_rent_load.py",
    "silver":   "databricks/cleaning_layer/cleaning_layer.py",
    "gold":     "databricks/aggregation_layer/aggregation_layer.py",
}


def load_module(relative_path: str, name: str):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT_ROOT, relative_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


layer = dbutils.widgets.get("layer")  # noqa: F821
if layer not in LAYERS:
    raise ValueError(f"Unknown layer {layer!r}. Expected one of {sorted(LAYERS)}.")

print(f"Running layer: {layer}")
mod = load_module(LAYERS[layer], f"etl_{layer}")
mod.run(spark)  # noqa: F821 — `spark` is pre-bound by the Databricks runtime
