# import packages
import sys # interact with current Python env
from pathlib import Path # list of folders for pathing

# find the project root by walking up from the current directory
# until folder is found containing config/ — works in scripts and notebooks
def find_project_root(marker: str = "config") -> Path:
    p = Path.cwd().resolve()
    for candidate in [p, *p.parents]:
        if (candidate / marker).is_dir():
            return candidate
    raise FileNotFoundError(f"Could not find '{marker}/' above {p}")

PROJECT_ROOT = find_project_root()

# check whether the project root is already inside sys.path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT)) # convert to string as sys.path stores paths as text, (0) gives the project priority

# import functions from config files
from config.snowflake_context import get_session, confirm_warehouse # find config/ folder
from config.run_sql_file import run_sql_file 

# create a Snowflake session using your helper function.
session = get_session("dev")

# find all .sql files in setup/ and sort by filename
setup_dir = PROJECT_ROOT / "setup"
sql_files = sorted(setup_dir.glob("*.sql"))

# error handle an empty or wrong folder
if not sql_files:
    raise FileNotFoundError(f"No .sql files found in {setup_dir}")

# run each setup SQL file in order
for sql_file in sql_files:
    print(f"Running setup file: {sql_file.name}")
    run_sql_file(session, sql_file)

# confirm active warehouse
confirm_warehouse(session)
print("Setup Complete.")