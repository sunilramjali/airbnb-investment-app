# Shared Databricks session/context helpers for the Airbnb investment project.
# Databricks counterpart of config/snowflake_context.py — same function names and
# call shape on purpose, so the ported loaders in databricks/ stay diffable against
# their Snowflake originals in etl/.
# ============================================================
# WHAT CHANGED FROM SNOWFLAKE
# ------------------------------------------------------------
#   get_active_session()      -> the pre-bound `spark` (notebooks/jobs) or Databricks Connect
#   USE WAREHOUSE <name>      -> DROPPED. Free Edition is serverless; there is no
#                                warehouse to select and no size to tune, so the
#                                WAREHOUSES dict has no counterpart here. This is a
#                                deliberate omission, not an oversight.
#   USE DATABASE <db>         -> USE CATALOG <catalog>
#   two-level SCHEMA.TABLE    -> three-level catalog.schema.table
# ============================================================

# import packages
from pathlib import Path  # object-oriented file pathing

# find the main project folder; Path(__file__) turns path into object, .resolve() grabs
# absolute path, and .parents[] goes up levels depending on number.
# __file__ exists only when running a .py file; in notebooks we fall back to cwd.
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path.cwd()

# project-wide settings
WORKSPACE_NAME = "airbnb-investment-app"
CATALOG = "airbnb_investment"   # every layer lives in this Unity Catalog catalog

# CLI profile used for the Databricks Connect fallback and for any CLI calls.
PROFILE = "airbnb"

# Raw S3 landing zone, exposed through Unity Catalog external locations.
# Snowflake reached these through @BRONZE.RAW_STAGE (one STORAGE INTEGRATION, three
# stages). Unity Catalog needs one EXTERNAL LOCATION per prefix instead — a location
# at the shared raw/ parent fails credential validation even though the IAM role
# grants raw/* (see setup/databricks/README.md for the evidence).
S3_BUCKET = "s3://airbnb-investment-app-988261629236-eu-west-2-an"
RAW_ROOT = f"{S3_BUCKET}/raw"

RAW_PATHS = {
    "inside_airbnb":  f"{RAW_ROOT}/inside_airbnb",      # external location airbnb_raw
    "land_registry":  f"{RAW_ROOT}/hm_land_registry",   # external location airbnb_raw_lr
    "ons":            f"{RAW_ROOT}/ons",                # external location airbnb_raw_ons
}


def get_session():
    """
    Return the active SparkSession.

    Two runtimes, one entry point:

    1. Databricks notebook / job — `spark` is already bound in the global namespace
       by the runtime. This is the proven path; every Session 2 probe ran this way.

    2. Local / VS Code — fall back to Databricks Connect against the `airbnb` CLI
       profile.

       UNVERIFIED: Databricks Connect has not been confirmed to work against Free
       Edition serverless compute. If this branch raises, the fallback is to run the
       loaders as workspace notebooks or jobs instead — nothing in the pipeline
       depends on local execution.
    """
    try:
        return spark  # noqa: F821 — pre-bound by the Databricks runtime
    except NameError:
        from databricks.connect import DatabricksSession
        return DatabricksSession.builder.profile(PROFILE).getOrCreate()


def use_schema(session, schema: str = "bronze"):
    """
    Anchor the catalog + schema so two-level names (LOAD_AUDIT) resolve.

    Snowpark sessions did not inherit USE DATABASE from a separately-run SQL file;
    the same is true of Spark sessions and USE CATALOG, so the loaders set context
    explicitly rather than relying on workspace defaults.
    """
    session.sql(f"USE CATALOG {CATALOG}")
    session.sql(f"USE SCHEMA {schema}")
    return schema


def confirm_context(session):
    """Return and print the catalog/schema currently in use."""
    catalog, schema = session.sql(
        "SELECT current_catalog(), current_schema()"
    ).collect()[0]
    print(f"Current context: {catalog}.{schema}")
    return catalog, schema


def table(name: str, schema: str = "bronze") -> str:
    """Fully-qualify a table name: table('RAW_LISTINGS') -> airbnb_investment.bronze.raw_listings.

    Unity Catalog lower-cases identifiers, so names are normalised here rather than
    left to chance at each call site.
    """
    return f"{CATALOG}.{schema}.{name}".lower()
