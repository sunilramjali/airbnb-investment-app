# import packages
import sys # interact with the Python runtime environment
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

# function 1
def add_project_root_to_path():
    """
    Allows Python files inside folders like setup/ to import from config/.
    """
    # check whether the project root is already in Python's import search path
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.append(str(PROJECT_ROOT)) # add teh main project folder to Python's import search path

# function 2
def get_session(warehouse = "dev"):
    """
    Gets the active Snowflake session and sets the correct warehouse.
    """
    # Error handling when the warehouse is not in dictionary
    if warehouse not in WAREHOUSES:
        raise ValueError(
            f"Unknown warehouse '{warehouse}'. Choose from: {list(WAREHOUSES.keys())}"
        )
        
    # get an active Snowflake session
    session = get_active_session()
    # look warehouses in the dictionary
    warehouse_name = WAREHOUSES[warehouse]
    # direct Snowflake to choose warehouse
    session.sql(f"USE WAREHOUSE {warehouse_name}").collect()
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