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

## Silver — Phase A ✅ PASSED (2026-07-28): 01 DDL + 02, 03, 04, 05, 07

Every drop is attributable to a documented rule. Nothing is unexplained.

| Table | Bronze in | Silver out | Dropped | Grain unique? |
|---|---|---|---|---|
| `listings_cleaned` | 102,591 | **102,591** | 0 | ✅ `listing_id` |
| `calendar_cleaned` | 37,510,686 | **37,510,686** | 0 | ✅ `listing_id × date` |
| `reviews_cleaned` | 2,676,100 | **2,676,100** | 0 | ✅ `review_id` |
| `neighbourhoods_cleaned` | 108 | **108** | 0 | ✅ `neighbourhood` |
| `price_paid_cleaned` | 5,249,688 | **871,514** | 4,378,174 | ✅ `transaction_uid` |

**The Price Paid drop is fully accounted for.** Bronze rows in the three target counties =
**871,514**, and Silver = 871,514 — so **zero rows were lost to validation**; the entire gap is
the documented county filter (`docs/data_pipeline.md:38`). This is the row-accounting gate
(invariant 7 below) passing on its first real test.

📄 **Two documented invariants reproduced on Databricks:**
- `neighbourhoods_cleaned` = **108** rows — matches `docs/data_pipeline.md:88`.
- Price Paid `quality_flag` = `non_standard` **19.86%** against the documented **~20%**
  (`docs/data_pipeline.md:47`), and the three flags are exhaustive:
  `ok` 698,336 (80.13%) · `non_standard` 173,040 (19.86%) · `price_suspect` 138 (0.02%).
  The bounds are fixed round numbers, not percentiles, so this is an exact reproduction — not
  a coincidence of similar data.

🔬 `calendar_cleaned` came out at exactly **365.0 rows per listing**, matching the Bronze ratio.

⚠️ **Observation to resolve in Gold, not a Silver failure:** `calendar_cleaned` holds **102,769**
distinct `listing_id`s but `listings_cleaned` holds **102,591** — **178 listing_ids appear in the
calendar with no matching listing**. Harmless in Silver (no join here), but it will silently
shrink any INNER join in Gold. Decide the join direction deliberately.

⚠️ `CLEAN_AUDIT` is still **empty** — Phase A ran the `.sql` files directly via `run_sql.py`. The
audit rows are written by `cleaning_layer.py`, which is Phase C.

### 🔴 The double-quote trap — would have emptied four tables silently
The Snowflake originals quote bronze columns as `"id"`, `"date"`, `"neighbourhood"` because
PARSE_HEADER made them case-sensitive. **In Databricks, `"id"` is the string literal `'id'`, not
the column.** Verified: `SELECT` \`id\`, `"id" FROM bronze.raw_listings` → `11551 | id`.

Ported verbatim, `TRY_CAST("id" AS DECIMAL(38,0))` casts the text `'id'` → NULL for every row →
`WHERE listing_id IS NOT NULL` drops all 102,591 → an **empty table and no error**. Affects files
02 (74 occurrences), 03 (7), 04 (8), 05 (4), 06 (1). All rewritten with backticks.

### Type translations applied
`NUMBER(p,s)` → `DECIMAL(p,s)`. `FLOAT` → **`DOUBLE`** — not cosmetic: Snowflake `FLOAT` is 8-byte
double, Databricks `FLOAT` is 4-byte REAL (~7 significant digits). Latitude/longitude at 4-byte
precision lose sub-metre accuracy and feed the point-in-polygon joins.

✅ `TRANSLATE(x,'{}','')` ports unchanged — verified `translate('{ABC-123}','{}','')` → `ABC-123`.
Both engines delete characters when the "to" string is shorter. Checked rather than assumed
because this expression defines the `transaction_uid` grain.

---

## Silver — Phase B ✅ PASSED (2026-07-28): 06, 08, 11

| Table | Rows | Grain unique? | Key check |
|---|---|---|---|
| `neighbourhoods_geo_cleaned` | **108** | ✅ `neighbourhood` | 📄 invariant #2 below — **PASSED** |
| `poi_cleaned` | 134,713 | ✅ `poi_id` | **0 unassigned** to a borough |
| `listing_amenities` | 2,992,739 | ✅ `listing_id × raw_amenity` | `Other` only **0.2%** |

🌍 **The `ST_AREA` fix validated against the real world.** The 108 borough areas sum to
**2,961 km²**. True: Greater London 1,572 + Greater Manchester 1,276 + Bristol 110 ≈ **2,958 km²**
— a 0.1% match. A naive `st_area` port would have summed to ~0.38 (square degrees). Range
1.0–188.19 km² is also plausible for the borough/district mix.

🔬 **All 134,713 POIs were assigned a borough, zero unassigned.** This is the strongest available
evidence that the SRIDs line up: `st_geomfromgeojson` (polygons, 4326) against Bronze's stored
`GEOMETRY` (points, 4326). An SRID mismatch would have produced mass NULLs through the LEFT JOIN
rather than an error.

🔬 **`Other` at 0.2% proves the VARIANT→STRING cast is clean.** Had `f.value::string` returned
`"Wifi"` with JSON quotes, every `LIKE` in the ordered CASE would have failed and ~100% of
2,992,739 rows would have classified as `Other` — a table that looks perfectly healthy.
Distribution is sane: Kitchen & Dining 28.4%, Bedroom & Comfort 14.7%, Bathroom 12.0%.
29.2 amenities per listing across 102,378 listings.

### 🔴 `SPLIT_PART(_FILENAME,'/',3)` NO LONGER YIELDS THE CITY
Snowflake stored a **stage-relative** path, so the city sat at position 3. Databricks
`_metadata.file_path` is a **full s3:// URL**, so position 3 is the *bucket name*:

```
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/london/...
 1     3                                              4    5             6
```

Ported verbatim, the `CASE SPLIT_PART(...)` in file 12 (and Gold's `DIM_NEIGHBOURHOOD`, which
`docs/data_pipeline.md:111` says uses "the same rule") matches nothing and sets **CITY = NULL on
every row**. Silent. City is at position **6**, but prefer a depth-independent extract so a bucket
or prefix change cannot break it again. Applies to files 12 and 14 — both still to port.

### ✅ Verified to port verbatim (checked, not assumed)
- `try_parse_json` exists and returns NULL on bad JSON — load-bearing, it is why a malformed
  amenities blob yields no rows instead of failing the run.
- `f.value::string` strips JSON quotes (`'Wifi'`, length 4).
- `SPLIT_PART` is 1-indexed and handles the **en dash** `' – '` (U+2013), not just ASCII hyphen.
- `LATERAL variant_explode(x)` + `:path::type` accessors — identical to `LATERAL FLATTEN`.
- Overture STRUCT accessors: `NAMES.primary`, `CATEGORIES.primary` (no backticks needed).
- `p.GEOMETRY` needs no conversion — Bronze already stores native `GEOMETRY` at SRID 4326.
- `ST_WITHIN` is topological, so **no unit trap** — unlike `st_area` and `st_dwithin`.

⚠️ **File 12 moved from Phase B to Phase C.** It reads `CODE_POINT_CLEANED`, which file 09 builds,
so it cannot run until the ONSPD rewrite lands.

---

## Silver — Phase C ✅ (2026-07-28): 09, 10, 12, 13, 14 + driver

| Table | Rows | Grain unique? | Check |
|---|---|---|---|
| `code_point_cleaned` | 2,700,777 | ✅ `postcode_key` | 901,381 terminated · 24,012 ungeocoded · 2,676,765 with GEOM |
| `property_group_map` | **51** | ✅ `property_type` | matches the driver's documented "~51" |
| `postcode_neighbourhood_map` | 461,861 | ✅ `postcode_key` | **0 CITY nulls** |
| `ons_private_rent_cleaned` | 54,252 | ✅ | = 137 months × 44 areas × 9 categories, **exactly** |
| `neighbourhood_ons_area_map` | 108 | ✅ `neighbourhood` | 📄 **32/32 London exact** |

### 📄 THE 99.95% COVERAGE INVARIANT — measured, and fully attributed

```
157,725 'ok' Price Paid postcodes · 157,383 mapped · 342 unmapped · 99.783%
```

🔴 **The denominator is EXACTLY 157,725 — identical to the Snowflake-era figure** in
`docs/data_pipeline.md:87`. Since `PRICE_PAID_CLEANED` was rebuilt from scratch on a different
platform, matching the old denominator to the row is the **closest thing to a genuine Snowflake
parity check that still exists anywhere in this migration.** It independently corroborates Phase A.

The numerator is 255 lower than Snowflake's 157,638. Attributed, not guessed:

| Cause | Postcodes | Verdict |
|---|---|---|
| **Absent from ONSPD entirely** | **298** | stale edition — 292 of them (98%) have sales **on/after Feb 2024**, the exact edition boundary |
| Geocoded but outside every polygon | 42 | genuine geographic miss |
| Present but ungeocoded (sentinel) | 2 | genuine |

**Both predicted effects are visible and quantified:**
- ⬇️ 298 missing because the ONSPD edition is nine releases old.
- ⬆️ Genuine misses fell from Snowflake's **87** to **44** (42 + 2) — the terminated postcodes are
  doing exactly what they were kept for, resolving historic sales Code-Point Open could not.

**Prediction for ONSPD May 2026:** the 298 should largely vanish, leaving ~44 unmapped →
coverage ≈ **99.97%**, i.e. *better* than the documented 99.95%. Until that file lands this gate
stays **measured but not signed off**.

### 📄 32/32 London — PASSED, including its documented exception
`neighbourhood_ons_area_map` resolves **33 London neighbourhoods, 32 with an ONS area code**. The
unresolved one is **City of London** — precisely the documented behaviour
(`etl/cleaning_layer/cleaning_layer.py:179`: "City of London resolves to a NULL ONS code but is
still emitted, so it is not dropped"). Bristol 34 broadcast, GM 32 broadcast + 9 exact. Total 108.

### 🔴 ONSPD ships a "no grid reference" sentinel — Code-Point Open did not
**24,012 rows carry `lat = 99.999999`** (ONS's marker for an ungeocoded postcode). The original
transform had nothing to guard against, because Code-Point only ever shipped geocoded postcodes.

Building a point from those places 24,012 postcodes at an **impossible latitude**, where
`st_within` simply never matches — so they would masquerade as ordinary "outside every polygon"
misses rather than missing data. `GEOM` is NULL for them and `IS_GEOCODED` records the
distinction, which is what let the 342 unmapped postcodes above be split three ways.

### 🔴 Column DEFAULTs are INHERITED through CTAS
File 13 failed with `WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED` despite declaring no
default. `BRONZE.RAW_ONS_PRIVATE_RENT._LOAD_TS` was created with `DEFAULT current_timestamp()`,
and a CTAS **inherits the column-default metadata from its source column**. Fixed with
`TBLPROPERTIES ('delta.feature.allowColumnDefaults'='supported')` on the CTAS. Only this one
Silver table is affected — it is the only one whose Bronze source carries a default.

### 🔴 The driver's `rows_in_sql` overrides were Snowflake SQL
Easiest thing in the layer to miss: `count_rows_in()` catches every exception and returns 0, so an
unported override does **not** fail the run — it records `ROWS_IN = 0`, making `ROWS_DROPPED`
negative and the audit meaningless. Three of four needed real edits. The helpers now **warn**.

⚠️ Snowflake's GeoJSON override was `SELECT ARRAY_SIZE(RAW:features)` read at row `[0][0]` — that
counted **one city's** features and ignored the other two. Replaced with an explode-and-count,
which is correct and independent of the city count.

### Decisions recorded
- **Terminated postcodes KEPT + `IS_TERMINATED` flag** (Sunil, 2026-07-28). Justified by the
  numbers above: genuine misses fell 87 → 44 because of them.
- **`GEOGRAPHY` column renamed to `GEOM`** — in Databricks `GEOGRAPHY` is a distinct, narrower
  type, so the old name would be actively misleading. Gold must use `GEOM`.
- **Table name `CODE_POINT_CLEANED` kept** despite the source change, so file 12 and Gold keep
  their references and the files stay diffable. ⚠️ `docs/data_pipeline.md:84` still calls it
  Code-Point and needs updating.

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

### Phase A ✅ (2026-07-28): 7 dimensions, built in 42.7 s

| Object | Rows | Grain unique? | Check |
|---|---|---|---|
| `DIM_LISTING` | 102,591 | ✅ `LISTING_ID` | ties to `LISTINGS_CLEANED` exactly |
| `DIM_HOST` | 57,081 | ✅ `HOST_ID` | — |
| `DIM_NEIGHBOURHOOD` | 108 | ✅ | **108/108 CITY populated** |
| `DIM_PROPERTY_GROUP` | 7 | ✅ | matches the 7 CASE branches |
| `DIM_POI` | 122,560 | — | equals the `confidence >= 0.5` count exactly |
| `DIM_CITY_ASSUMPTIONS` | 3 | ✅ | — |
| `DIM_DATE` | 438 | ✅ | 2026-05-20 → 2027-07-31 |

🔬 **SRID alignment asserted:** `DIM_LISTING.GEO_POINT` and `DIM_POI.LOCATION` are both **4326**,
one distinct SRID across 102,591 rows. `ST_MAKEPOINT` → `st_setsrid(st_point(...), 4326)`; without
the explicit `st_setsrid` the point would carry SRID 0 and `FCT_LISTING_POI`'s join would be
semantically undefined while still appearing to work.

### 🔴 `IS_WEEKEND` would have been WRONG ON EVERY ROW
Snowflake `DAYOFWEEK` returns **0=Sunday … 6=Saturday**; Databricks returns **1=Sunday … 7=Saturday**.
Verified: `2026-08-02` (Sun) → 1, `2026-08-01` (Sat) → 7, `2026-08-03` (Mon) → 2.

The original tests `DAYOFWEEK(d) IN (0,6)`. Ported verbatim on Databricks, **0 never occurs and 6
is Friday** — so `IS_WEEKEND` would be TRUE for Fridays and FALSE for actual weekends, with no
error, in a column the seasonal marts consume. Corrected to `IN (1,7)` and verified:

```
Sunday 1 true · Monday 2 false · … · Friday 6 false · Saturday 7 true
```

### Other Phase A translations (verified, not assumed)
- ✅ `ILIKE ANY (...)` ports verbatim.
- `GENERATOR(ROWCOUNT => 1000)` + `SEQ4` → `explode(sequence(start, end, INTERVAL 1 DAY))`. This
  also removes the magic 1000 and the trailing `WHERE d <= end_d` guard — `sequence()` is bounded
  by the dates, so the range cannot silently truncate if the calendar grows past 1000 days.
- `MONTHNAME` / `DAYNAME` do not exist → `date_format(d,'MMMM')` / `date_format(d,'EEEE')`.
  `QUARTER` / `WEEKOFYEAR` / `YEAR` / `MONTH` / `DAY` port verbatim.
- ⚠️ Snowflake auto-names `VALUES` columns `column1..N`; Databricks does not, so `column1 AS CITY`
  fails. Explicit `AS t(...)` aliases used.
- `SPLIT_PART(_FILENAME,'/',3)` → `regexp_extract` — the same city bug as Silver 12/14.

### Phase B ✅ (2026-07-28): 5 facts, built in 36.9 s

| Object | Rows | Check |
|---|---|---|
| `FCT_CALENDAR_DAILY` | 37,510,686 | ties to `CALENDAR_CLEANED` exactly |
| `FCT_LISTING_SNAPSHOT` | 102,591 | ties to `DIM_LISTING` exactly |
| `FCT_LISTING_POI` | **102,591** | 🔬 LEFT JOIN preserved **every** listing |
| `FCT_AREA_SALE_PRICE` | 324 | = 108 neighbourhoods × 3 classes, exactly |
| `FCT_AREA_RENT` | 749 | = 107 neighbourhoods × 7 categories, exactly |

🌍 **`FCT_LISTING_POI` reproduced the spike exactly, through a different code path** (via the
dimensions rather than straight off Silver): avg **188.5**, max **2,044**, **44** zeros, all
102,591 listings retained. An independent reproduction, not a re-run.

🔬 **Internal consistency of `FCT_AREA_SALE_PRICE`:** Flat 290,568 + House 403,273 = **693,841** =
the `All` total exactly. This also confirms the documented claim that the `Other` bucket is always
empty (100% of code-O sales are PPD category B, removed by `quality_flag='ok'`).

🔬 **Cross-layer reconciliation — the Gold gate — PASSES exactly:**

```
Silver 'ok' sales                 698,336
Gold FCT_AREA_SALE_PRICE (All)    693,841
difference                          4,495
sales on unmapped postcodes         4,495   ← exact match
```

Every sale that did not reach Gold is accounted for by the postcode-coverage gap already
attributed above. Nothing is unexplained.

🔬 `FCT_AREA_RENT` covers **107** neighbourhoods, not 108 — City of London has a NULL
`ONS_AREA_CODE` by design and is excluded by `WHERE x.ONS_AREA_CODE IS NOT NULL`. Documented
Snowflake behaviour, not a port regression.

✅ Verified verbatim in Phase B: `MEDIAN`, `ANY_VALUE`, `COUNT(CASE WHEN …)`, `UNION ALL`,
`COMMENT ON COLUMN`.

⚠️ **The `st_transform` calls sit in CTEs, not inline in the `ON` clause**, so they are evaluated
once per row rather than per candidate pair. That is the shape that was performance-tested — do
not "simplify" it back into the join condition.

### 🔴 Why Gold is plain tables, not materialized views
MVs work on Free Edition — verified: create, **MV-on-MV**, query, `COMMENT ON COLUMN`, drop. They
were rejected on **cost**, not capability:

| Operation (3-row object) | Time |
|---|---|
| `CREATE MATERIALIZED VIEW` | **5 m 39 s** |
| `CREATE TABLE AS SELECT` | **4.6 s** |

74×, entirely fixed overhead — each MV provisions its own backing Lakeflow pipeline, so a trivial
object costs the same as a real one. Twenty objects ≈ **110 minutes per build**, paid again on
every `CREATE OR REPLACE` during development. Phase A's seven objects took **42.7 s** as tables.

What is given up is auto-refresh, which is acceptable: this pipeline is Lambda-fed **quarterly**
and Bronze/Silver are already batch driver-run. The dependency DAG is carried by the driver's
`STEPS` ordering, as it always was. Reversible — `TABLE` ↔ `MATERIALIZED VIEW` is a
find-and-replace.

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

### 🌍 The geospatial unit trap — SPIKED 2026-07-28, both risks retired

`FCT_LISTING_POI` counts POIs within **500m** of each listing. Snowflake's `ST_DWITHIN` takes
GEOGRAPHY and measures **metres**; Databricks' measures in **SRID units — degrees at 4326**.

**Measured on one Westminster listing:**

| Version | POIs "within 500m" |
|---|---|
| `st_dwithin(st_transform(...,27700), 500)` — correct, metres | **831** |
| `st_dwithin(pt_4326, loc_4326, 500)` — naive port | **122,560** |
| Total POIs with `confidence >= 0.5` | **122,560** |

🔴 **The naive figure equals the total POI count exactly.** 500 degrees exceeds the Earth's
circumference (360°), so *every* POI matches *every* listing. This is not a subtly wrong number —
it is a **12.6 billion-row cross product** (102,591 × 122,560) before the `GROUP BY`. The trap is
simultaneously a correctness bug and a cost/runtime disaster, which is the only reason it would
likely be noticed at all.

**Full-scale run, correct version — the performance question is answered:**

| Metric | Value |
|---|---|
| Listings covered | 102,591 (all) |
| Listing–POI pairs | 19,337,214 |
| Avg POIs within 500m | 188.5 |
| Max | 2,044 |
| Listings with zero | 44 |
| **Wall clock** | **~14 s** on Free Edition serverless |

19.3M pairs versus 12.6 billion — a **650× difference**. The join is cheap when the projection is
right. `st_dwithin` can use a spatial index in a projected CRS; in degrees it degenerates to a
cross join.

✅ **Both Gold geospatial risks are now retired**: the unit semantics (Session 2, re-proven here)
and the scale/performance question (here). `ST_CONTAINS` in `MART_AREA_POI` is topological and
carries no unit risk. Gold's design does **not** need to change.

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

Both effects were subsequently measured (see the coverage section below) — the net is **−255
mapped postcodes**, fully attributed.

### ✅ ONSPD IS LOADED AND WORKING — the upgrade is an improvement, not a fix
Do not read the above as a blocker. `ONSPD_FEB_2024_UK.csv` is live through Bronze → Silver → Gold
and every number in the app is sound. Measured cost of the stale edition (2026-07-28):

| | Sales | % | Median price | Flats |
|---|---|---|---|---|
| Reaching Gold | 693,841 | 99.37% | £425,000 | 41.9% |
| Missing | **4,400** | **0.63%** | £442,830 | **85.0%** |

The missing sales are 4% pricier and overwhelmingly **flats** — the new-build apartment profile
predicted by the stale-edition hypothesis, since new developments get new postcodes. Worst-hit
districts are exactly the regeneration zones: Tower Hamlets **3.11%**, Salford 2.81%, Newham
2.38%, Barnet 1.90%, Manchester 1.83%.

🔬 **Materiality: negligible.** A median is robust to displacing 0.6–3% of observations, so no
neighbourhood `MEDIAN_SALE_PRICE` moves meaningfully. The gap is coherent and explainable rather
than random, which is itself corroboration.

**What the upgrade buys:** coverage ~99.783% → ~99.97% (better than the Snowflake original's
99.95%), and the documented gate becomes *signable* rather than merely *measured and attributed*.
That is a process distinction, not a data-correctness one.

**Recommendation: not urgent.** The August 2026 release is due shortly — wait for it rather than
doing the 1.45 GB upload twice. Upgrading is a pure file drop into the same folder:
`newest_csv()` selects by `modification_time`, the write is `CREATE OR REPLACE`, and only files 09
and 12 need re-running. No code change.

### Silver decision required: keep or drop terminated postcodes
Code-Point Open carried live postcodes only; ONSPD carries both. Keeping the terminated ones is
probably *right* here (Price Paid is historic, so retired postcodes are exactly what old sales
reference) — but it is a **behaviour change from Snowflake** and must be a stated decision in
`09_silver_code_point.sql`, not an accident of the source swap.

⚠️ **Foursquare "OS" is *Open Source*, not *Ordnance Survey*.** It has no GB postcode units and
cannot substitute for this. Already checked — do not re-litigate.
