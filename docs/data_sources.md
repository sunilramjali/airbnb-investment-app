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

---

## Source: HM Land Registry — Price Paid Data

UK residential property sale prices come from **HM Land Registry's [Price Paid Data](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads)** —
the official record of (nearly) every property sale in England & Wales registered for value.

Files are published per year (`pp-<YYYY>.csv`) and land in S3 under
`raw/hm_land_registry/price_paid/year=<YYYY>/`, loaded all-TEXT into the bronze table below.

| File | Bronze table | Notes |
|---|---|---|
| `pp-<YYYY>.csv` | `RAW_PRICE_PAID` | one row per registered sale, all years, all-TEXT |

**Standard Price Paid schema** (no header row in source): transaction id, price, date of
transfer, postcode, property type (D/S/T/F/O), old/new (Y/N), duration (F/L), PAON, SAON,
street, locality, town/city, district, county, PPD category (A/B), record status.

### Silver scope

`SILVER.PRICE_PAID_CLEANED` restricts to the three investment areas by `COUNTY`:

| Area | `COUNTY` value |
|---|---|
| London (all, incl. City of London district) | `GREATER LONDON` |
| Greater Manchester | `GREATER MANCHESTER` |
| Bristol | `CITY OF BRISTOL` |

It types/decodes the coded fields, dedupes by transaction id, and adds a `quality_flag`
(`ok` / `non_standard` / `price_suspect`). See the README "Bronze → Silver" section.

### Licensing / attribution

Price Paid Data is published under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Contains HM Land Registry data © Crown copyright and database right. Attribute HM Land
Registry in any published analysis or dashboard built on this data.
