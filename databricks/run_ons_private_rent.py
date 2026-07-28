# Databricks notebook source
# Runner notebook for the ONS Private Rent (PIPR) Bronze load.
# ============================================================
# Separate from run_bronze.py because this step needs openpyxl installed into the
# notebook environment first — the Snowflake original declared it in the procedure's
# PACKAGES = (...) clause, which has no Databricks counterpart.
#
# See databricks/run_bronze.py for why the loaders are imported by path rather than
# with a plain `import` (their filenames start with a digit).
# ============================================================

# MAGIC %pip install openpyxl

# COMMAND ----------

import importlib.util
import os
import sys

PROJECT_ROOT = "/Workspace/Users/ramjs016.310@gmail.com/airbnb-investment-app"

os.chdir(PROJECT_ROOT)                 # so find_project_root() resolves config/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def load_module(relative_path: str, name: str):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT_ROOT, relative_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ons = load_module("databricks/ingestion_layer/08_ons_private_rent_load.py", "ons_load")
ons.run(spark)  # noqa: F821 — `spark` is pre-bound by the Databricks runtime
