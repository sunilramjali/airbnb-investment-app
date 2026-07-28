# Databricks notebook source
# Runner notebook for the Silver cleaning layer.
# ============================================================
# Runs all 14 Silver transforms in dependency order and writes SILVER.CLEAN_AUDIT.
#
# See databricks/run_bronze.py for why the loaders are imported by path rather
# than with a plain `import` (their filenames start with a digit). This one is a
# normal module name, but the same chdir is needed so find_project_root()
# resolves config/.
#
# PREREQUISITE: Bronze loaded (9 of 9 tables).
# ============================================================

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


silver = load_module("databricks/cleaning_layer/cleaning_layer.py", "silver_cleaning")
silver.run(spark)  # noqa: F821 — `spark` is pre-bound by the Databricks runtime
