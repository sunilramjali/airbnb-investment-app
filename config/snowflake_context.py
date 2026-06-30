# Shared Snowflake session/context helpers for the Airbnb investment project.
# Co-authored with CoCo
# import packages
from pathlib import Path 
from snowflake.snowpark.context import get_active_session # access current connection

# find the main project folder; Path(__file__)turns path into object, .resolve() grabs absolute path, and .parents[] goes up levels depending on number
# __file__ exists only when running a .py file; in notebooks we fall back to the current working directory
try:
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
except NameError:
    PROJECT_ROOT = Path.cwd()

# warehouse dictionary of existing project warehouses
WAREHOUSES = {
    "dev": "AIRBNB_DEV_WH",
    "query": "AIRBNB_APP_WH"
}
# project-wide settings
WORKSPACE_NAME = "airbnb-investment-app"
DATABASE = "AIRBNB_INVESTMENT_DB"   # every layer lives in this database

def get_session(warehouse = "dev", set_context = True):
    """
    Gets the active Snowflake session and (optionally) sets the warehouse + database.

    set_context=False returns a bare session WITHOUT issuing USE WAREHOUSE / USE DATABASE.
    Use this to bootstrap a fresh account, where those objects do not exist yet and are
    created by the setup SQL itself (CREATE WAREHOUSE / CREATE DATABASE are metadata DDL
    and do not require an active warehouse).
    """
    # get an active Snowflake session
    session = get_active_session()

    # bootstrap path: no context yet (objects may not exist)
    if not set_context:
        return session

    # Error handling when the warehouse is not in dictionary
    if warehouse not in WAREHOUSES:
        raise ValueError(
            f"Unknown warehouse '{warehouse}'. Choose from: {list(WAREHOUSES.keys())}"
        )

    # look warehouses in the dictionary
    warehouse_name = WAREHOUSES[warehouse]
    # direct Snowflake to choose warehouse
    session.sql(f"USE WAREHOUSE {warehouse_name}").collect()
    # anchor the database context so schema-qualified names (BRONZE.x) resolve.
    # Snowpark sessions do NOT inherit USE DATABASE from a separately-run SQL file.
    session.sql(f"USE DATABASE {DATABASE}").collect()
    return session

# function 3
def confirm_warehouse(session):
    """
    Returns and prints the warehouse currently being used.
    """
    wh = session.sql("SELECT CURRENT_WAREHOUSE()").collect()[0][0]
    print(f"Current warehouse: {wh}")
    return wh

# function 4
def workspace_stage_path(folder: str = "") -> str:
    """Build a snow:// path to a folder on the live workspace stage."""
    base = f'snow://workspace/USER$.PUBLIC."{WORKSPACE_NAME}"/versions/live'
    return f"{base}/{folder}" if folder else base