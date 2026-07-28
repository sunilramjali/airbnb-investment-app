# Databricks notebook source
# Runner notebook for the Bronze ingestion layer.
# ============================================================
# WHY THIS FILE EXISTS
# ------------------------------------------------------------
# The Snowflake loaders were run directly (`python 02_bronze_load.py`, or a
# Snowflake notebook cell). On Databricks the loaders run inside a job or
# notebook against serverless compute, and two mechanical problems get in the way:
#
#   1) The loader filenames start with a digit (02_bronze_load.py), so they are not
#      valid Python module names and cannot be `import`ed. They are loaded by path
#      via importlib instead.
#   2) The loaders call find_project_root() which walks up from the CURRENT WORKING
#      DIRECTORY looking for config/. A notebook's cwd is not the repo root, so we
#      chdir to the uploaded project root first.
#
# Neither is a migration decision — just scaffolding so the ported files can stay
# byte-identical to how they would run locally.
#
# USAGE: run this notebook on serverless. Set STEP to pick which loader to run.
# ============================================================

import importlib.util
import os
import sys

# Root of the uploaded project in the workspace (config/ + databricks/ live here).
PROJECT_ROOT = "/Workspace/Users/ramjs016.310@gmail.com/airbnb-investment-app"

os.chdir(PROJECT_ROOT)                 # so find_project_root() resolves config/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)   # so `import config.databricks_context` works


def load_module(relative_path: str, name: str):
    """Import a loader whose filename is not a valid module name (leading digit)."""
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT_ROOT, relative_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# COMMAND ----------

bronze = load_module("databricks/ingestion_layer/02_bronze_load.py", "bronze_load")
bronze.run(spark)  # noqa: F821 — `spark` is pre-bound by the Databricks runtime
