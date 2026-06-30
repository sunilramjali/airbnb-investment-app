# Branches and File/Folder Naming Conventions

branches = hyphens
folders/files = underscores

Branch:
role/data-engineer/feature/data-ingestion

Folder:
setup/run_setup.py


----------------------------------------------------------



# Project Architecture Guide

This project follows a simple Medallion data pipeline structure based on the **Bronze → Silver → Gold** architecture.

The purpose of this structure is to keep the project organised, easy to understand, and easy for the team to collaborate on.

> **Runtime:** this project runs **inside Snowflake** (Snowpark `get_active_session()`),
> so the data lives in Snowflake **tables/stages**, not in a local `data/` folder. See the
> README "Where This Runs" section. The `data/bronze|silver|gold` examples below describe the
> medallion *concept*; in practice each layer is a Snowflake schema (BRONZE / SILVER / GOLD).

Current project structure:

```text
airbnb-investment-app/
├── README.md
├── config/
│   ├── __init__.py
│   ├── snowflake_context.py       # session + warehouse helpers
│   ├── run_sql_file.py            # client-side SQL runner
│   └── ingestion_manifest.py      # declarative list of Bronze datasets to load
├── setup/
│   ├── run_setup.py
│   ├── 00_setup_api_integration.sql
│   └── 01_setup_database_and_warehouse.sql
├── etl/
│   ├── 01_bronze_ddl.sql          # file formats + RAW_STAGE (run once)
│   └── 02_bronze_load.py             # generic loader, driven by the manifest
├── notebooks/
│   └── preprocessing_layer.ipynb
└── docs/
```

---

## What each folder is for

### `README.md`

This is the main project guide.

It explains:

* what the project is about
* how the repository is structured
* how to set up the project
* how the data pipeline works
* how the team should collaborate

The README should be the first file a new team member reads.

---

## Data folder

The `data/` folder stores the datasets used and produced by the project.

This project uses three main data layers:

```text
data/
├── bronze/
├── silver/
└── gold/
```

---

## Bronze layer

```text
data/bronze/
```

The bronze layer stores the first official version of the data after loading it into the project.

This data is usually close to the original source, with only light changes such as:

* standardising column names
* adding ingestion dates
* converting files into a consistent format
* applying basic schema checks

Bronze data answers:

> What data did we receive from the original source?

Example files:

```text
data/bronze/airbnb_listings.csv
data/bronze/airbnb_reviews.csv
data/bronze/crime_data.csv
data/bronze/house_prices.csv
```

The bronze layer should not contain heavily cleaned or final analysis-ready data.

---

## Silver layer

```text
data/silver/
```

> **Implemented:** in this project the silver layer is built in `etl/cleaning_layer/`
> (driven by `cleaning_layer.py`) and lands in the Snowflake `SILVER` schema as
> `*_CLEANED` tables — not a local `data/silver/` folder. See the README
> "Bronze → Silver (Cleaning) — User Guide". The `data/silver/` paths below describe
> the medallion *concept*.

The silver layer stores cleaned and validated data.

This is where the main preprocessing work happens.

The silver layer may include:

* removed duplicates
* fixed missing values
* corrected data types
* cleaned date columns
* standardised area names
* cleaned location fields
* joined lookup tables
* created useful features

Silver data answers:

> Is the data clean and ready for analysis?

Example files:

```text
data/silver/listings_cleaned.csv
data/silver/reviews_cleaned.csv
data/silver/crime_cleaned.csv
data/silver/house_prices_cleaned.csv
```

The silver layer can be used for analysis, modelling, and enrichment.

---

## Gold layer

```text
data/gold/
```

The gold layer stores the final