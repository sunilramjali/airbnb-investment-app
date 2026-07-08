# Git: What to Commit vs Ignore

This guide explains which files should be committed to GitHub and which should be ignored via
`.gitignore` for the Airbnb Investment App.

For the project structure and the Bronze → Silver → Gold pipeline, see
[architecture.md](architecture.md). For naming conventions and how to run the pipeline, see the
[README](../README.md).

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

The gold layer stores the final, app-ready datasets — the outputs the dashboard actually
reads. This is where the star schema (dimensions + facts) and the denormalised marts live.

Gold data answers:

> What does the app show?

Example files:

```text
data/gold/mart_listing.csv
data/gold/mart_area.csv
data/gold/mart_area_structure.csv
```

> **Implemented:** in this project the gold layer is built in `etl/aggregation_layer/`
> (driven by `aggregation_layer.py`) and lands in the Snowflake `GOLD` schema — not a local
> `data/gold/` folder. The `data/gold/` paths above describe the medallion *concept*. See the
> README "Silver → Gold (Aggregation) — User Guide" for how to run it and what it produces.
>
> The real GOLD objects are a Kimball **star** — `DIM_LISTING`, `DIM_HOST`,
> `DIM_NEIGHBOURHOOD`, `DIM_POI`, `DIM_DATE`, `FCT_LISTING_SNAPSHOT`, `FCT_CALENDAR_DAILY`,
> `FCT_LISTING_POI` — plus the **app-facing marts** the Streamlit app reads directly:
> `MART_LISTING` (per-listing), `MART_AREA` (per-neighbourhood + map boundary), and
> `MART_AREA_STRUCTURE` (neighbourhood × Flat/House + median sale-price cost). They are
> **dynamic tables**, refreshed incrementally (marts anchor `TARGET_LAG='1 day'`; dims/facts
> use `DOWNSTREAM`).

The app reads the **GOLD schema only** — never Bronze or Silver.

