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

## Source: HM Land Registry Price Paid Data

UK residential property sales are sourced from **HM Land Registry Price Paid Data (PPD)** —
one CSV per calendar year, published publicly (no auth). We ingest **2021 to present**; the
current-year file is cumulative and refreshed by Land Registry roughly monthly.

A monthly AWS Lambda (`land_registry_ppd`) downloads each yearly file and lands it in this
project's S3 bucket. The files have **no header row** and a fixed **16-column** layout
(transaction id, price, date of transfer, postcode, property type, old/new, duration, PAON,
SAON, street, locality, town/city, district, county, PPD category type, record status).

### Where it lives

**In S3** (under the same bucket, read via the existing `AIRBNB_S3_INT` integration):

```text
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/hm_land_registry/price_paid/
└── year=<YYYY>/pp-<YYYY>.csv
```

**In Snowflake** — landed into `BRONZE.RAW_PRICE_PAID` (all columns TEXT + lineage columns).
Structural objects (file format + stage) are created by
[`etl/ingestion_layer/03_land_registry_ddl.sql`](../etl/ingestion_layer/03_land_registry_ddl.sql)
(run once); the table + load are in
[`etl/ingestion_layer/04_land_registry_load.sql`](../etl/ingestion_layer/04_land_registry_load.sql).
The load is idempotent (table rebuilt + all years re-COPYd each run), so re-running after a
monthly refresh produces no duplicates. Typing/casting happens in SILVER.

---

## Source: Overture Maps — Places

Landmarks and visitor attractions are sourced from the **Overture Maps "Places"**
dataset, consumed as a **Snowflake Marketplace share** from CARTO (free, open data).
Unlike the S3-based sources, there is **no ingestion pipeline** — the data is a live
share, queried directly.

The share mounts as the database `OVERTURE_MAPS__PLACES`; the global POI table is
`OVERTURE_MAPS__PLACES.CARTO.PLACE` (~75M point POIs worldwide, geometry as native
`GEOGRAPHY`, categories/names as VARIANT).

### Where it lives

**In the share** — `OVERTURE_MAPS__PLACES.CARTO.PLACE` (read-only, refreshed by CARTO).

**In Snowflake** — we materialise a spatially scoped copy into our own schemas:

| Object | Notes |
|---|---|
| `BRONZE.RAW_OVERTURE_POI` | POIs whose point falls **inside our borough polygons** (`SILVER.NEIGHBOURHOODS_GEO_CLEANED`), so only London / Greater Manchester / Bristol are copied — not the global 75M. Faithful source column shape + lineage. |
| `SILVER.ATTRACTIONS_CLEANED` | one row per landmark/attraction: name, category, `ATTRACTION_TYPE` bucket, borough, `LOCATION GEOGRAPHY`. Non-attraction POIs are dropped by a category allow-pattern. |
| `SILVER.LISTING_ATTRACTION_PROXIMITY` | per-listing features: nearest attraction (m) + counts within 500 m / 1 km / 3 km. |

Structural + load logic:
[`etl/ingestion_layer/05_overture_poi_load.sql`](../etl/ingestion_layer/05_overture_poi_load.sql)
(Bronze, run each refresh — idempotent `CREATE OR REPLACE`);
[`etl/cleaning_layer/07_silver_attractions.sql`](../etl/cleaning_layer/07_silver_attractions.sql)
and
[`etl/cleaning_layer/08_silver_listing_proximity.sql`](../etl/cleaning_layer/08_silver_listing_proximity.sql)
(Silver, driven by `cleaning_layer.py`).

**Prerequisite:** acquire the share once via the Marketplace UI (accept terms, name the
database `OVERTURE_MAPS__PLACES`):
[listing GZT0Z4CM1E9KR](https://app.snowflake.com/marketplace/listing/GZT0Z4CM1E9KR).

---

## Licensing / attribution

Inside Airbnb data is provided under a Creative Commons licence
([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)). Attribute Inside Airbnb as the
source in any published analysis or dashboard built on this data.

HM Land Registry Price Paid Data is provided under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
It contains public sector information licensed under the OGL and must carry the attribution:
*"Contains HM Land Registry data © Crown copyright and database right {year}. This data is
licensed under the Open Government Licence v3.0."*

Overture Maps data is open and its Places theme is licensed under
[CDLA Permissive 2.0](https://cdla.dev/permissive-2-0/). Attribute both **Overture Maps
Foundation** and **CARTO** (the Marketplace distributor) in any published analysis or
dashboard built on this data. Overture derives Places in part from OpenStreetMap and
other sources — see the per-record `SOURCES` field for provenance.
