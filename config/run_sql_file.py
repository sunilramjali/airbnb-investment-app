# import pathlib for effective file pathing
from pathlib import Path
import re          # strip comments when testing for executable SQL
import sqlparse # sql spliiter


# returns True if a split chunk is nothing but comments (line and/or block).
# sqlparse keeps trailing comment blocks (e.g. a "-- Verify" section) as their
# own statement; sending one to Snowflake fails as an empty SQL statement, so
# these are filtered out before execution.
def _is_comment_only(statement):
    without_block = re.sub(r"/\*.*?\*/", "", statement, flags=re.DOTALL)
    code_lines = [
        line for line in without_block.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    return not code_lines

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

    # split sql text every time there is a semicolon; drop empties and any
    # chunk that is only comments (sqlparse keeps trailing "-- ..." blocks,
    # which Snowflake rejects as empty SQL statements).
    statements = [
        stmt.strip()
        for stmt in sqlparse.split(sql)
        if stmt.strip() and not _is_comment_only(stmt)
    ]

    # execute each statement with numbered progress and error context
    for i, statement in enumerate(statements, 1):
        print(f"[{i}/{len(statements)}] Running: {statement[:100]}...")
        try:
            session.sql(statement).collect()
        except Exception as e:
            raise RuntimeError(f"Statement {i} failed:\n{statement}") from e