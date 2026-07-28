# Databricks notebook source
# Runner notebook for the ONS Postcode Directory (ONSPD) Bronze load.
# ============================================================
# Separate from run_bronze.py because ONSPD is not an Inside Airbnb source — it is
# the replacement for the Ordnance Survey Code-Point Open Marketplace share, which
# has no Databricks equivalent (see databricks/ingestion_layer/06_onspd_load.py).
# Keeping it its own runner means a Code-Point/ONSPD re-load never forces a rerun of
# the 37.5M-row calendar load.
#
# No %pip install needed — unlike run_ons_private_rent.py, this reads plain CSV.
#
# See databricks/run_bronze.py for why the loaders are imported by path rather than
# with a plain `import` (their filenames start with a digit).
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


onspd = load_module("databricks/ingestion_layer/06_onspd_load.py", "onspd_load")
onspd.run(spark)  # noqa: F821 — `spark` is pre-bound by the Databricks runtime
