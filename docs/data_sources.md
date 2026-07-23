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

---

## Source: Overture Maps Places (Marketplace share)

Points of interest come from the **Overture Maps "Places"** dataset, provided by **CARTO** as a
**Snowflake Marketplace share** (not S3). Once acquired via *Get Data*, it mounts as the shared
database `OVERTURE_MAPS__PLACES`; the global places table
`OVERTURE_MAPS__PLACES.CARTO.PLACE` holds ~75M point POIs worldwide, each with a GEOGRAPHY point,
name/category VARIANTs, and a confidence score.

### Where it lives

A live share — there is **no S3 stage or file format**. The loader
[`etl/ingestion_layer/05_overture_poi_load.sql`](../etl/ingestion_layer/05_overture_poi_load.sql)
reads the share directly and writes a **spatially scoped** snapshot to `BRONZE.RAW_OVERTURE_POI` —
only POIs that fall inside the ingested borough polygons (London / Greater Manchester / Bristol),
via a bounding-box prefilter + exact point-in-polygon `ST_WITHIN` against
`SILVER.NEIGHBOURHOODS_GEO_CLEANED`. `CREATE OR REPLACE` keeps re-runs idempotent.

| Share object | Bronze table | Notes |
|---|---|---|
| `OVERTURE_MAPS__PLACES.CARTO.PLACE` | `RAW_OVERTURE_POI` | scoped to our boroughs; VARIANT names/categories |

### Prerequisite

`SILVER.NEIGHBOURHOODS_GEO_CLEANED` must exist first — it defines the spatial coverage filter.

### Licensing / attribution

Overture Maps data is released under open licences (Places: CDLA Permissive 2.0). Attribute the
**Overture Maps Foundation** in any published analysis or dashboard built on this data.

---

## Source: Ordnance Survey Code-Point Open (Marketplace share)

GB postcodes come from **Ordnance Survey "Code-Point Open"**, provided as a **Snowflake
Marketplace share**. Once acquired via *Get Data*, it mounts as the shared database
`POSTCODE_UNITS__GREAT_BRITAIN_CODEPOINT_OPEN`; its view
`PRS_CODE_POINT_OPEN_SCH.PRS_CODE_POINT_OPEN_VW` holds ~1.7M GB postcode units, each with a
GEOGRAPHY point and administrative area codes (county / district / ward, NHS codes).

### Where it lives

A live share — **no S3 stage or file format**. The loader
[`etl/ingestion_layer/06_code_point_load.sql`](../etl/ingestion_layer/06_code_point_load.sql)
writes a **faithful full snapshot** (all source columns, no filtering) to `BRONZE.RAW_CODE_POINT`.
The whole of GB is cheap to hold and future-proofs adding cities; spatial scoping and
postcode → neighbourhood attribution are deferred to later layers. `CREATE OR REPLACE` keeps
re-runs idempotent.

| Share object | Bronze table | Notes |
|---|---|---|
| `...PRS_CODE_POINT_OPEN_VW` | `RAW_CODE_POINT` | full GB copy; postcode + GEOGRAPHY + admin codes |

### Licensing / attribution

Code-Point Open is published under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Contains OS data © Crown copyright and database right. Attribute **Ordnance Survey** in any
published analysis or dashboard built on this data.

---

## Source: ONS Price Index of Private Rents (PIPR)

Long-term (traditional let) market rents come from the **Office for National Statistics'
[Price Index of Private Rents, UK: monthly price statistics](https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/priceindexofprivaterentsukmonthlypricestatistics)** —
official monthly average rents and rent indices by local authority, broken down by bedroom count
and property type.

A monthly AWS Lambda (`ons_pipr`) resolves the **latest** release from the ONS dataset's `/data`
JSON (filenames change every month, so nothing is hard-coded), downloads the workbook, and lands
the **raw `.xlsx` unchanged** in S3. The Lambda uses only the Python standard library + `boto3`
(no third-party packages), because the parsing is done **inside Snowflake** — `.xlsx` is not
`COPY`-loadable, so a Python stored proc (`openpyxl`, from Snowflake's Anaconda channel) reads it.

### Where it lives

**In S3** (same bucket, read via the existing `AIRBNB_S3_INT` integration):

```text
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/ons/private-rents/
└── pipruk_<YYYYMMDD>.xlsx
```

**In Snowflake** — the ingestion layer parses the workbook's **`Table 1`** tab (skipping the 2
title rows; the header is on row 3) and lands it faithfully:

| Source | Bronze table | Notes |
|---|---|---|
| `pipruk_<YYYYMMDD>.xlsx` (`Table 1`) | `RAW_ONS_PRIVATE_RENT` | one row per sheet row; cells as an `ARRAY` of TEXT + lineage |

Structural objects (stage + `openpyxl` parse proc) are in
[`etl/ingestion_layer/07_ons_private_rent_ddl.sql`](../etl/ingestion_layer/07_ons_private_rent_ddl.sql)
(run once); the table rebuild + `CALL` are in
[`etl/ingestion_layer/08_ons_private_rent_load.sql`](../etl/ingestion_layer/08_ons_private_rent_load.sql).
The load is idempotent (table rebuilt + newest file re-parsed each run).

### Silver scope

`SILVER.ONS_PRIVATE_RENT_CLEANED` reshapes the wide workbook into a **tidy-long** panel (one row
per `period × area × category`, with `category_type` = overall / bedroom / property_type and a
Flat/House `property_class` bridge), scoped by **area code** to the three investment areas:

| Area | ONS area code(s) |
|---|---|
| London (32 boroughs + region roll-up) | `E09%`, `E12000007` |
| Greater Manchester (10 districts) | `E08000001`–`E08000010` |
| Bristol | `E06000023` |

`SILVER.NEIGHBOURHOOD_ONS_AREA_MAP` is a crosswalk placing each Airbnb neighbourhood onto its ONS
area (London boroughs match 1:1; Manchester wards → Manchester; Bristol wards → city), with a
`rent_grain` flag (`exact` / `broadcast`). Downstream, `GOLD.FCT_AREA_RENT` and the strategy marts
use these observed rents (see the README "Long-term rent" note).

### Licensing / attribution

ONS PIPR is published under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Contains ONS data © Crown copyright and database right. Attribute the **Office for National
Statistics** in any published analysis or dashboard built on this data.
