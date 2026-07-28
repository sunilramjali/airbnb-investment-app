# Databricks notebook source
# Runner notebook for the Gold aggregation layer.
# ============================================================
# Builds all 20 Gold objects (7 dimensions, 5 facts, 8 marts) in dependency
# order and prints a row-count summary.
#
# See databricks/run_bronze.py for why the loaders are imported by path.
#
# PREREQUISITE: Silver built (14 of 14 tables).
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


gold = load_module("databricks/aggregation_layer/aggregation_layer.py", "gold_aggregation")
gold.run(spark)  # noqa: F821 — `spark` is pre-bound by the Databricks runtime
