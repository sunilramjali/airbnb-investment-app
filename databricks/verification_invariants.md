# Verification Invariants — the replacement for Snowflake parity

**Why this file exists.** The Snowflake free trial expired on **2026-07-28** and the account is
inaccessible. A new trial gives an empty account, not the old tables, so there is **no Snowflake
to compare against and no way to get one back**. Every "row counts must match Snowflake" gate in
the original migration plan is permanently unpassable.

This file is what replaced it. Each entry is a fact that is true **independently of any
platform** — a uniqueness rule, a ratio, a documented coverage figure, or a real-world
coordinate. A table is verified when its invariants hold and every number has a stated
expectation attached.

> **A number with no expectation attached is not verification.** The 141,206 incident (`LOG.md`
> session 3) was a probe result mistaken for a baseline, and it survived two sessions because
> nobody had written down what the number *should* be.

**Append to this file whenever you establish a new invariant.** Mark each one with where it came
from, because provenance decides how much it is worth:

| Tag | Meaning | Trust |
|---|---|---|
| 📄 **documented** | Recorded in `docs/` or a SQL header while Snowflake worked | High — a real observation of the old system |
| 🔬 **structural** | True by definition of the grain (PK uniqueness, ratios) | High — independent of both platforms |
| 🌍 **ground truth** | Checked against the outside world (coordinates, published totals) | Highest — catches bugs counts cannot |
| 🧪 **measured** | Observed on Databricks this migration, no prior expectation | **Low — this is a record, not a gate** |

---

## Bronze — status: ✅ COMPLETE, 9 of 9 (sessions 3 & 5)

| Table | Rows | Invariant | Tag |
|---|---|---|---|
| `raw_listings` | 102,591 | `count(*) == count(distinct id)` **per city** | 🔬 |
| `raw_calendar` | 37,510,686 | ≈365 rows per listing per city — london 365.6 · manchester 365.9 · bristol 365.0 | 🔬 |
| `raw_reviews` | 2,676,100 | none established | 🧪 |
| `raw_neighbourhoods` | 108 | matches the borough count used by Overture and the 108/108 name check below | 🔬📄 |
| `raw_neighbourhoods_geo` | 3 | exactly one VARIANT `FeatureCollection` per city | 🔬 |
| `raw_price_paid` | 5,249,688 | `count(*) == count(distinct TRANSACTION_UID)` across all 6 years | 🔬 |
| `raw_overture_poi` | 634,958 | landmark coordinates match reality (below) | 🌍 |
| `raw_ons_private_rent` | 48,910 | row 3 is the header, data starts row 4 — Silver depends on this | 🔬📄 |
| `raw_onspd` | 2,700,777 | `count(*) == count(distinct pcds)` — see the ONSPD section | 🔬 |

**Ground-truth coordinate checks** (these caught the SRID bug that row counts missed):

| Landmark | Loaded | True |
|---|---|---|
| British Museum | `-0.12703, 51.51954` | 51.5194°N, 0.1270°W |
| Tate Modern | `-0.09935, 51.5076` | 51.5076°N, 0.0994°W |

**Bronze reading rule — not optional.** Airbnb CSVs require **both** `multiLine => true` **and**
`escape => '"'`. With `multiLine` alone the London file yields 93,672 rows / 92,966 distinct ids —
706 phantom duplicates. Only both together give `92,638 == 92,638`. The `count(*) ==
count(distinct id)` invariant is what detects this; a row count alone never will.

---

## Silver — the four surviving documented invariants

These were measured on the working Snowflake system and written into `docs/` and SQL headers.
They are the closest thing to a real baseline that still exists. **Treat a miss as a blocker.**

### 1. Postcode → neighbourhood coverage — 99.95% 📄
`157,638 / 157,725` of **Price Paid `ok` postcodes** map to a neighbourhood.
Source: `docs/data_pipeline.md:87`, `etl/cleaning_layer/12_silver_postcode_neighbourhood_map.sql:23`.

✅ **This transfers to ONSPD.** The denominator is derived from `PRICE_PAID_CLEANED` (an unchanged
source), *not* from the postcode table — so swapping Code-Point Open for ONSPD does not move it.
The numerator is how many of those postcodes land inside a neighbourhood polygon.

⚠️ **But expect the number to shift, and understand why before accepting it.** ONSPD contains
**terminated postcodes** (`doterm`) and is all-UK; Code-Point Open is live postcodes only. Historic
sales referencing since-retired postcodes may now resolve, which would push coverage **above**
99.95%. That is plausible and good — but only if you can show it comes from `doterm IS NOT NULL`
rows. An unexplained move in either direction is a blocker.

### 2. Neighbourhood name match — 108/108 📄
Every neighbourhood name in the geo boundaries matches Inside Airbnb exactly.
Source: `docs/data_pipeline.md:88`. Corroborated by `raw_neighbourhoods` = 108 rows in Bronze.

### 3. London borough crosswalk — 32/32 exact 📄
All 32 London boroughs map 1:1 to their ONS area with `rent_grain = 'exact'`. The London regional
roll-up `E12000007` is excluded so only district-level areas match.
Source: `docs/data_pipeline.md:96,101` → `14_silver_neighbourhood_ons_area_map.sql`.

### 4. Zero polygon overlaps 📄🔬
`POSTCODE_NEIGHBOURHOOD_MAP` observed **0** polygon overlaps; the `QUALIFY ROW_NUMBER()` is purely
defensive. Source: `12_silver_postcode_neighbourhood_map.sql:17-19`.

**Test it as a no-op:** count postcodes matching more than one polygon *before* the `QUALIFY`. If
that is non-zero on Databricks, the geometry port is wrong — most likely the SRID trap from
`LOG.md` session 3, where `st_geomfromwkb` returns SRID 0 and `st_geomfromgeojson` returns 4326,
making `st_within` semantically undefined while still appearing to work.

### 5. Declared grain is unique — every table 🔬
From `docs/data_pipeline.md:33-39`. Assert `count(*) == count(distinct <grain>)` on each:

| Silver table | Grain | Also drops |
|---|---|---|
| `LISTINGS_CLEANED` | `listing_id` | null id; lat/long outside `[-90,90]`/`[-180,180]` |
| `CALENDAR_CLEANED` | `listing_id × date` | null in either grain column |
| `REVIEWS_CLEANED` | `review_id` | null `review_id` or `listing_id` |
| `PRICE_PAID_CLEANED` | transaction | county-filtered to the 3 cities; null txn id; `price <= 0`; unparseable date |
| `POI_CLEANED` | POI id | anything off the curated amenity allow-list; missing name or geometry |
| `POSTCODE_NEIGHBOURHOOD_MAP` | `POSTCODE_KEY` | — |

Every one dedupes with `QUALIFY ROW_NUMBER() ... ORDER BY _LOAD_TS DESC` (latest load wins), so
uniqueness is guaranteed by construction — which means **a duplicate is evidence the port broke
the dedupe**, not evidence of bad source data.

### 6. Price Paid quality flags 🔬📄
`quality_flag ∈ {ok, non_standard, price_suspect}` and the three are exhaustive.
`non_standard` (PPD category B) should be **~20% of rows** — `docs/data_pipeline.md:47-48`.
Bounds are fixed, not percentile-based (`< £10,000`, `> £20,000,000`), so they are **exactly
reproducible on Databricks**. A different distribution means the parse changed, not the data.

### 7. Rows are dropped only where documented 🔬
Guiding principle 1 (`docs/data_pipeline.md:18-20`): `TRY_CAST` everything so a bad value becomes a
**countable NULL, never a lost row**. So for each Silver table, `bronze_rows - silver_rows` must be
fully attributable to the documented drop rules in the table above. An unexplained gap is a
blocker — this is the invariant that replaces "row counts match Snowflake" most directly.

---

## Gold — ⚠️ the weakest gate

**No surviving numbers exist for any of the 20 marts.** No mart row count, no aggregate, nothing.
Verification here is structural only. **Report Gold as reviewed, not proven** — say those words.

1. **Cross-layer reconciliation.** Each mart ties back to its source fact: totals and row counts
   agree across the boundary. `MART_AREA_OVERVIEW` ← `FCT_AREA_SALE_PRICE` on
   `STRUCTURE_CLASS = 'All'`; `MART_LISTING_CANDIDATES` ← `FCT_LISTING_SNAPSHOT` ⋈ `DIM_LISTING`.
2. **Declared grain unique on every mart** — e.g. `MART_ST_VS_LT` at
   `CITY × NEIGHBOURHOOD × STRUCTURE_CLASS × BEDROOM_BUCKET`.
3. **LEFT joins must not drop rows.** `MART_LISTING_CANDIDATES` LEFT joins `DIM_HOST`,
   `FCT_LISTING_POI`, `FCT_AREA_SALE_PRICE` precisely so a listing never disappears
   (`docs/data_pipeline.md:143-146`). Row count in == row count out. An inner-join regression during
   the port is silent and would look like clean data.
4. **No numeric column unexpectedly all-NULL.** The likeliest Databricks-specific failure, given
   the VARIANT→STRUCT accessor change on Overture (`NAMES:primary::STRING` → `NAMES.primary`).
5. **Conformed flags stay conformed.** `IS_ACTIVE` (`OCCUPANCY_NIGHTS >= 30`) is set once in
   `FCT_LISTING_SNAPSHOT` and reused by every mart — it must not be re-derived anywhere.
6. **Thin-cell guards behave.** `SUFFICIENT_SAMPLE` = `LISTING_COUNT >= 5`, `ROBUST_SAMPLE` = `>= 10`,
   amenity gap = `TOP_N >= 5 AND REST_N >= 15`.
7. **London's 90-night cap is visible.** `DIM_CITY_ASSUMPTIONS`: London = 90, Manchester/Bristol =
   365. If London's capped ST income doesn't show the cap biting in `MART_ST_VS_LT`, the join to
   the assumptions table is broken.
8. **`LT_RENT_SOURCE` covers the fallback chain** — `observed_bedroom` / `observed_structure` /
   `assumed` — and no row is `assumed` where an observed rent exists.

### 🌍 The strongest Gold check available: the geospatial unit trap
`FCT_LISTING_POI` counts POIs within **500m** of each listing. Snowflake's `ST_DWITHIN` takes
GEOGRAPHY and measures **metres**; Databricks' measures in **SRID units — degrees for 4326**. A
naive port computes a 500-*degree* radius and still returns plausible-looking counts.

Verify by reprojecting to EPSG:27700 (British National Grid) and checking a known distance. The
session-2 London test pair is true ≈730 m: `st_distancesphere` gave 729.1 m,
`st_distance(st_transform(...,27700))` gave 730.9 m. **A POI count alone cannot detect this.**

---

## ONSPD — ✅ landed and column-verified (2026-07-28)

File: `raw/ons/postcode_directory/ONSPD_FEB_2024_UK.csv` — 1.45 GB, **53 columns**.

| Measure | Value | Tag |
|---|---|---|
| Total rows | **2,700,777** | 🧪 |
| `count(*) == count(distinct pcds)` | ✅ **holds** — one row per postcode | 🔬 |
| Terminated (`doterm` set) | 901,381 | 🧪 |
| Live | 1,799,396 | 🧪 |

⚠️ **The sanity band is ~2.7M for UK ONSPD, not the ~1.7–1.8M written in the original notes.**
That figure was Code-Point Open (GB, live-only) and it coincidentally equals ONSPD's *live* subset
— so a wrong expectation would have passed here for entirely the wrong reason. Corrected in
`06_onspd_load.py`.

### ✅ All column mappings confirmed against the real header
Verified 2026-07-28 from row 1 (`AB1 0AA`, a terminated Aberdeen postcode). Nothing is a guess.

| Code-Point Open (old) | ONSPD | Evidence |
|---|---|---|
| `POSTCODE` | `pcds` | `AB1 0AA` |
| `ADMIN_DISTRICT_CODE` | `oslaua` | `S12000033` |
| `ADMIN_WARD_CODE` | `osward` | `S13002843` |
| `COUNTRY_CODE` | **`ctry`** | `S92000003` = Scotland — correct for an AB postcode |
| `ADMIN_COUNTY_CODE` | **`oscty`** | `S99999999` = the "not applicable" pseudo-code |
| `POSITIONAL_QUALITY_INDICATOR` | **`osgrdind`** | `1` |
| `NHS_HA_CODE` | **`oshlthau`** | `S08000020` |
| `NHS_REGIONAL_HA_CODE` | **`nhser`** | `S99999999` |
| `GEOMETRY` / `GEOGRAPHY` | none — build in Silver: `st_setsrid(st_point(try_cast(long AS DOUBLE), try_cast(lat AS DOUBLE)), 4326)` | `57.101474`, `-2.242851` |

### 🔴 The edition is stale — do not judge the coverage invariant on it
ONSPD ships quarterly (Feb/May/Aug/Nov). The landed file is **February 2024**; the current release
as of 2026-07-28 is **May 2026** — about nine releases behind.

Two effects act on the 99.95% coverage invariant in **opposite** directions:

| Effect | Direction |
|---|---|
| Postcodes created after Feb 2024 are absent → 2024–26 new-build sales in Price Paid can't resolve | coverage **down** |
| 901,381 terminated postcodes present that Code-Point Open never carried → historic 2021–23 sales on retired postcodes now resolve | coverage **up** |

The net is unpredictable and, worse, **unattributable** — a coverage figure from this edition
cannot be explained, and rule #5 requires explanation. **Land the May 2026 edition before running
the Silver coverage gate.**

Upgrading is a pure file drop: `newest_csv()` selects by `modification_time` and the write is
`CREATE OR REPLACE`. No code change is needed for a new edition.

### Silver decision required: keep or drop terminated postcodes
Code-Point Open carried live postcodes only; ONSPD carries both. Keeping the terminated ones is
probably *right* here (Price Paid is historic, so retired postcodes are exactly what old sales
reference) — but it is a **behaviour change from Snowflake** and must be a stated decision in
`09_silver_code_point.sql`, not an accident of the source swap.

⚠️ **Foursquare "OS" is *Open Source*, not *Ordnance Survey*.** It has no GB postcode units and
cannot substitute for this. Already checked — do not re-litigate.
