# import pathlib for effective file pathing
from pathlib import Path
import sqlparse # sql spliiter

# function to run sql, takes two inputs: session acts as a connection to let python send SQL commands to Snowflake, and the location of file to run.
def run_sql_file(session, sql_file_path):
    """
    Runs a SQL file in Snowflake using the active Snowpark session.

    Parameters:
        session: Snowflake active session
        sql_file_path: path to the SQL file
    """

    # convert file path into a file object
    sql_file_path = Path(sql_file_path)
    
    # handle error by checking if the file path exists
    if not sql_file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")

    # open sql file in read mode
    with open(sql_file_path, "r", encoding = "utf-8") as file:
        sql = file.read() # read the sql file and store it in a varaiable called sql

    # remove empty statement using strip() and split sql text every time there is a semicolon
    statements = [stmt.strip() for stmt in sqlparse.split(sql) if stmt.strip()]

    # execute each statement with numbered progress and error context
    for i, statement in enumerate(statements, 1):
        print(f"[{i}/{len(statements)}] Running: {statement[:100]}...")
        try:
            session.sql(statement).collect()
        except Exception as e:
            raise RuntimeError(f"Statement {i} failed:\n{statement}") from e