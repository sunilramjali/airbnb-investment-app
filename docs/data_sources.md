# Data Sources

Where the raw data in this project comes from, and how it lands in Snowflake.

For how the data is ingested, see the [README](../README.md). For the pipeline overview, see
[architecture.md](architecture.md).

---

## Source: Inside Airbnb

All raw data originates from **[Inside Airbnb](https://insideairbnb.com/get-the-data/)**, an
independent project that publishes scraped snapshots of Airbnb listings, calendars, reviews, and
neighbourhood boundaries for cities worldwide.

Data is published as periodic **snapshots** (one dated capture per city). A quarterly AWS Lambda
copies each new snapshot into this project's S3 bucket.

---

## Cities

| City | Folder name (S3 / `CITIES`) | Ingested |
|---|---|---|
| London | `london` | yes |
| Greater Manchester | `greater_manchester` | yes |
| Bristol | `bristol` | yes |

The list of cities actually loaded is controlled by `CITIES` in
[`config/ingestion_manifest.py`](../config/ingestion_manifest.py).

---

## Files per snapshot

Each city/snapshot folder contains these source files:

| File | Bronze table | Notes |
|---|---|---|
| `listings/listings.csv.gz` | `RAW_LISTINGS` | one row per listing |
| `calendar/calendar.csv.gz` | `RAW_CALENDAR` | one row per listing per day (largest table) |
| `reviews/reviews.csv.gz` | `RAW_REVIEWS` | one row per review |
| `neighbourhoods/neighbourhoods.csv` | `RAW_NEIGHBOURHOODS` | neighbourhood lookup |
| `neighbourhoods_geojson/neighbourhoods.geojson` | `RAW_NEIGHBOURHOODS_GEO` | neighbourhood polygons (one VARIANT row) |

CSV files are gzipped; `neighbourhoods.csv` and the GeoJSON are plain.

---

## Where it lives

**In S3** (read by Snowflake via the `AIRBNB_S3_INT` storage integration):

```text
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/
└── <city>/snapshot_date=<YYYY-MM-DD>/<dataset>/<file>
```

A new `snapshot_date=<date>/` folder is added per city each quarter; the loader auto-selects the
latest one per city.

**In Snowflake** — landed into the `BRONZE` schema of `AIRBNB_INVESTMENT_DB` as the `RAW_*`
tables above. Data is **not** stored in this repository; only the code that loads it is.

---

## Licensing / attribution

Inside Airbnb data is provided under a Creative Commons licence
([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)). Attribute Inside Airbnb as the
source in any published analysis or dashboard built on this data.
