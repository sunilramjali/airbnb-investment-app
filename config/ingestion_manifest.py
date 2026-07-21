# Declarative ingestion manifest: which cities and source files Bronze loads.
# Co-authored with CoCo
# ============================================================
# INGESTION MANIFEST  —  the declarative "what" of Bronze.
# ------------------------------------------------------------
# Adding a new file to ingest  = add one dict to DATASETS.
# Adding a new city            = add one string to CITIES.
# The "how" (infer/copy logic) lives in etl/ingestion_layer/02_bronze_load.py.
# ============================================================

# Cities to ingest. Each must have a folder uploaded by the Lambda under
# s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/<city>/ before the loader runs.
# Names must match the S3 folder names exactly.
CITIES = [
    "london",
    "greater_manchester",
    "bristol",
]

# One dict per source file.
#   name   = target table created in the BRONZE schema
#   dir    = dataset subfolder on the stage (under <city>/snapshot_date=.../)
#   file   = exact filename in that subfolder (incl. .gz if compressed)
#   format = which loader path to use: "csv" or "geojson"
# Full stage path = <city>/snapshot_date=<YYYY-MM-DD>/<dir>/<file>.
# CSV files are gzipped; the CSV file format's default COMPRESSION=AUTO
# decompresses .csv.gz transparently on INFER_SCHEMA and COPY.
DATASETS = [
    {"name": "RAW_LISTINGS",           "dir": "listings",             "file": "listings.csv.gz",        "format": "csv"},
    {"name": "RAW_CALENDAR",           "dir": "calendar",             "file": "calendar.csv.gz",        "format": "csv"},
    {"name": "RAW_REVIEWS",            "dir": "reviews",              "file": "reviews.csv.gz",         "format": "csv"},
    {"name": "RAW_NEIGHBOURHOODS",     "dir": "neighbourhoods",       "file": "neighbourhoods.csv",     "format": "csv"},
    {"name": "RAW_NEIGHBOURHOODS_GEO", "dir": "neighbourhoods_geojson","file": "neighbourhoods.geojson", "format": "geojson"},
]
