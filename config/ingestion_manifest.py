# ============================================================
# INGESTION MANIFEST  —  the declarative "what" of Bronze.
# ------------------------------------------------------------
# Adding a new file to ingest  = add one dict to DATASETS.
# Adding a new city            = add one string to CITIES.
# The "how" (infer/copy logic) lives in etl/02_bronze_load.py.
# ============================================================

# Cities to ingest. Each must have its files uploaded to
# @BRONZE.RAW_STAGE/<city>/ before the loader runs.
CITIES = [
    "london",
    # "manchester",
    # "edinburgh",
]

# One dict per source file.
#   name   = target table created in the BRONZE schema
#   file   = exact filename on the stage (must match the upload, incl. .gz if compressed)
#   format = which loader path to use: "csv" or "geojson"
DATASETS = [
    {"name": "RAW_LISTINGS",           "file": "listings.csv",           "format": "csv"},
    {"name": "RAW_CALENDAR",           "file": "calendar.csv",           "format": "csv"},
    {"name": "RAW_REVIEWS",            "file": "reviews.csv",            "format": "csv"},
    {"name": "RAW_NEIGHBOURHOODS",     "file": "neighbourhoods.csv",     "format": "csv"},
    {"name": "RAW_NEIGHBOURHOODS_GEO", "file": "neighbourhoods.geojson", "format": "geojson"},
]
