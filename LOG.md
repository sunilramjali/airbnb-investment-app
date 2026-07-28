# Migration Log — Snowflake → Databricks

Session notes for the airbnb-investment-app migration. Newest entries at the top.
Read this before starting any migration work.

---

## 2026-07-28 — Session 8: ETL filtering post-mortem + ONSPD materiality

**Agent:** Snowflake to Databricks Migrator (planned and executed in Opus 5)

### Status: review complete, 3 findings, 1 fixed as code, 2 clarified, 2 docs corrected.

### 🔴 Finding 1 (FIXED) — the marts did NOT share one universe
`docs/data_pipeline.md:123` claimed *"the consumer marts share one like-for-like universe so their
numbers reconcile"*. **`MART_AREA_OVERVIEW` applied none of the three base filters**, so its
operating metrics ran over hotels, private rooms and dormant listings.

| | Listings |
|---|---|
| `MART_AREA_OVERVIEW` | 102,591 |
| property / strategy marts | 25,731 |

A **4× universe difference presented as one number**. User-visible impact:

| Neighbourhood | Overview avg rev | Like-for-like | Overview occ | LFL occ |
|---|---|---|---|---|
| Westminster | £26,980 | **£56,385** | 0.177 | **0.376** |
| Tower Hamlets | £12,924 | £31,536 | 0.130 | 0.340 |
| Camden | £19,307 | £41,337 | 0.174 | 0.363 |

**~2× different revenue and occupancy for the same area depending on the screen.** This is in the
Snowflake original too — the migration surfaced it, it did not cause it.

**Fix** (`03_app_marts_core.sql`), schema-compatible so Streamlit keeps working:
`LISTING_COUNT` stays market size · `LISTING_COUNT_INVESTABLE` added · operating metrics
recomputed on the investable base · `SUFFICIENT_SAMPLE` added (≥5, matching the codebase
convention). Driven from the all-listings CTE so an area with no investable listings would still
appear with NULL metrics rather than vanishing off the map.
✅ Verified: **all 108 areas reconcile on count, revenue AND occupancy**; 102 of 108 pass ≥5.

### 🟡 Findings 2 & 3 (clarified, not restructured)
- **POI relevance is filtered one layer apart** — Silver allow-list 634,958→134,713, Gold
  `CONFIDENCE >= 0.5` 134,713→122,560. Kept split (different questions: *relevant?* vs
  *trustworthy?*), but both ends now state the other's existence and counts. Silver also records
  honestly that its "consumers choose their own threshold" rationale is theoretical — there is
  exactly one consumer and it hard-codes 0.5.
- **`AREA_ACTIVE_LISTINGS` → `AREA_RANKED_LISTINGS`.** "Active" = `OCCUPANCY_NIGHTS >= 30`
  everywhere else (37,046); this mart uses `ANNUAL_REVENUE > 0` (47,838), a 29% difference. Both
  defensible; sharing the word was not. Safe — no app file reads that mart.

### ✅ ONSPD IS LOADED — the "May 2026" item was BADLY WORDED, not outstanding work
Earlier sessions listed "land ONSPD May 2026" beside genuine blockers, which read as if nothing
had been loaded. **Wrong.** `ONSPD_FEB_2024_UK.csv` is live end-to-end. The item is an *edition
upgrade*. Measured cost of the stale edition:

| | Sales | % | Median | Flats |
|---|---|---|---|---|
| Reaching Gold | 693,841 | 99.37% | £425,000 | 41.9% |
| Missing | **4,400** | **0.63%** | £442,830 | **85.0%** |

Missing sales are 4% pricier and **85% flats** — the new-build apartment profile predicted.
Worst districts are the regeneration zones: Tower Hamlets 3.11%, Salford 2.81%, Newham 2.38%.
🔬 **Materiality negligible** — a median is robust to 0.6–3% displacement; no neighbourhood
`MEDIAN_SALE_PRICE` moves meaningfully. **Not urgent.** Wait for the August 2026 release rather
than uploading 1.45 GB twice.

### Docs corrected
- `docs/data_pipeline.md` — records that the one-universe claim was aspirational, the measured 4×
  impact, that it is fixed in the Databricks port but **NOT in the Snowflake original**, and the
  one deliberate exception (`LISTING_COUNT` stays market size).
- `docs/data_sources.md` — Overture was scoped against `SILVER.NEIGHBOURHOODS_GEO_CLEANED`, a
  **Bronze→Silver dependency inverting the medallion order** (Silver's `POI_CLEANED` reads
  `BRONZE.RAW_OVERTURE_POI`, closing the loop). The Databricks loader uses
  `BRONZE.RAW_NEIGHBOURHOODS_GEO`. Same polygons, clean layering.

### ⚠️ Surfaced, not acted on: three Gold marts are unconsumed by the app
`MART_PROPERTY_TYPE`, `MART_AREA_AMENITIES`, `MART_AREA_AMENITY_GAP` — no Streamlit file reads
them. `MART_PROPERTY_TYPE` is notable: it is the only mart carrying buy price at structure grain,
the basis of the yield comparison. Either work-in-progress or dead weight — **decide before the
Streamlit port**, since porting pages that read nothing is wasted effort either way.

### Next
1. **Streamlit → Databricks Apps** — the last layer.
2. Optional: ONSPD August 2026 when released, to sign off the coverage gate.

---

## 2026-07-28 — Session 7: **GOLD IS COMPLETE (20 of 20) — MIGRATION PIPELINE DONE**

**Agent:** Snowflake to Databricks Migrator (planned and executed in Opus 5)

### Status: all 20 Gold objects built, run and verified. Driver run `586169914666593` SUCCESS.
Bronze (9) + Silver (14) + Gold (20) all complete. Only the Streamlit app remains.

| Phase | Objects | Build time |
|---|---|---|
| A — dimensions | 7 | 42.7 s |
| B — facts | 5 | 36.9 s |
| C — marts | 8 | ~4 min |

### 🔴 DYNAMIC TABLES → PLAIN TABLES, NOT MATERIALIZED VIEWS
MVs work on Free Edition — verified: create, **MV-on-MV**, query, `COMMENT ON COLUMN`, drop.
Rejected on **cost**, not capability:

| Operation (3-row object) | Time |
|---|---|
| `CREATE MATERIALIZED VIEW` | **5 m 39 s** |
| `CREATE TABLE AS SELECT` | **4.6 s** |

74×, entirely fixed overhead — each MV provisions its own backing Lakeflow pipeline. Twenty
objects ≈ **110 min per build**, paid again on every `CREATE OR REPLACE` during development.
Phase A's seven objects took 42.7 s as tables. Auto-refresh is what we give up; acceptable because
the pipeline is Lambda-fed **quarterly** and Bronze/Silver are already batch driver-run. The DAG is
carried by the driver's `STEPS` ordering. Reversible via find-and-replace.

### 🔴 Two more silent bugs caught
1. **`IS_WEEKEND` would have been wrong on EVERY row.** Snowflake `DAYOFWEEK` = 0(Sun)…6(Sat);
   Databricks = 1(Sun)…7(Sat). The original tests `IN (0,6)` — on Databricks 0 never occurs and
   **6 is Friday**, so `IS_WEEKEND` would be TRUE for Fridays and FALSE for weekends, silently, in
   a column the seasonal marts consume. Corrected to `IN (1,7)` and verified.
2. **`ST_DWITHIN` unit trap, measured.** One Westminster listing: correct (EPSG:27700) = **831**
   POIs; naive (degrees at 4326) = **122,560** — *exactly* the total POI count, because 500 degrees
   exceeds the Earth's circumference. Not a subtly wrong number: a **12.6 billion-row cross
   product** vs 19.3M pairs. Full scale with the fix: 102,591 listings, 19,337,214 pairs, avg 188.5,
   max 2,044, **~14 s**.

### Verification — structural and semantic (no Snowflake numbers survive for Gold)
- 🔬 **Cross-layer reconciliation exact:** Silver 'ok' sales 698,336 − Gold `FCT_AREA_SALE_PRICE`
  693,841 = **4,495** = sales on unmapped postcodes, to the row.
- 🔬 **LEFT-join preservation:** `MART_LISTING_CANDIDATES` = 102,591, grain unique, no fan-out.
- 🔬 **Exact grain products:** `FCT_AREA_SALE_PRICE` 324 = 108×3 (Flat 290,568 + House 403,273 =
  All 693,841, confirming the documented "Other is always empty"); `FCT_AREA_RENT` 749 = 107×7;
  `MART_AREA_SEASONAL` 1,296 = 108×12.
- 🌍 **`ST_AREA` fix validated:** 108 borough areas sum to **2,961 km²** vs a real ~2,958.
- 🌍 **SEMANTIC check — London's 90-night cap self-documents**, exactly as the mart header claims:

| City | Cap | Avg ST−LT uplift | ST wins |
|---|---|---|---|
| London | **90** | **−£8,039** | 12 / 252 |
| Greater Manchester | 365 | +£3,616 | 139 / 224 |
| Bristol | 365 | +£241 | 75 / 184 |

### Other Databricks behaviours verified (not assumed)
- ✅ `st_contains` **raises `ST_DIFFERENT_SRID_VALUES`** on a mismatch rather than returning a
  quietly meaningless answer — the SRID discipline is enforced, not merely advisable.
- ✅ Verbatim: `MEDIAN` (matches Snowflake's interpolation), `ANY_VALUE`, `ILIKE ANY`, `NTILE`,
  `EXISTS`, `ST_CONTAINS`/`ST_X`/`ST_Y`, `COMMENT ON COLUMN` (on tables **and** MVs), `::STRING`.
- `GENERATOR(ROWCOUNT=>1000)+SEQ4` → `explode(sequence(...))`, which also removes the magic 1000
  and the `WHERE d <= end_d` guard — the range can no longer silently truncate.
- `MONTHNAME`/`DAYNAME` do not exist → `date_format(d,'MMMM'/'EEEE')`.
- Snowflake auto-names `VALUES` columns `column1..N`; Databricks does not → explicit `AS t(...)`.

### ⚠️ Gold is REVIEWED, NOT PROVEN
No surviving Snowflake numbers exist for any of the 20 objects. Everything above is structural or
semantic. Do not describe Gold as parity-verified.

### Created this session
```
databricks/aggregation_layer/01_dimensions.sql        02_facts.sql
databricks/aggregation_layer/03_app_marts_core.sql    04_app_marts_property.sql
databricks/aggregation_layer/05_app_marts_strategy.sql 06_app_marts_amenities.sql
databricks/aggregation_layer/aggregation_layer.py     databricks/run_gold.py
```

### Next
1. **ETL pipeline post-mortem** — filtering consistency review (see Session 8).
2. **Streamlit → Databricks Apps** — the last layer.
3. Land **ONSPD May 2026** to sign off the coverage gate.

---

## 2026-07-28 — Session 6: **SILVER IS COMPLETE (14 of 14) + driver**

**Agent:** Snowflake to Databricks Migrator (planned and executed in Opus 5)

### Status: all 14 Silver files ported, run and verified. Every drop attributable.

Silver was split into three phases: **A** = DDL + the row-preserving transforms
(01, 02, 03, 04, 05, 07) · **B** = VARIANT + geospatial (06, 08, 11, 12) ·
**C** = ONSPD rewrite + crosswalks (09, 10, 13, 14) + the driver.

| Table | Bronze in | Silver out | Dropped | Grain unique? |
|---|---|---|---|---|
| `listings_cleaned` | 102,591 | 102,591 | 0 | ✅ |
| `calendar_cleaned` | 37,510,686 | 37,510,686 | 0 | ✅ (365.0/listing) |
| `reviews_cleaned` | 2,676,100 | 2,676,100 | 0 | ✅ |
| `neighbourhoods_cleaned` | 108 | 108 | 0 | ✅ |
| `price_paid_cleaned` | 5,249,688 | 871,514 | 4,378,174 | ✅ |

**The Price Paid drop is fully attributable** — bronze rows in the three target counties =
871,514, silver = 871,514, so **zero rows lost to validation**; the whole gap is the documented
county filter. That is the row-accounting gate passing its first real test.

📄 **Two documented Snowflake-era invariants reproduced exactly:** `neighbourhoods_cleaned` = 108
rows, and Price Paid `quality_flag = non_standard` at **19.86%** against the documented ~20%
(bounds are fixed round numbers, not percentiles, so this is a real reproduction).

### 🔴 THE DOUBLE-QUOTE TRAP — WOULD HAVE SILENTLY EMPTIED FOUR TABLES
The Snowflake originals quote every bronze column as `"id"`, `"date"`, `"neighbourhood"` because
PARSE_HEADER made them case-sensitive lowercase identifiers.

**In Databricks, `"id"` is the STRING LITERAL `'id'`, not the column.** Verified live:
```
SELECT `id`, "id" FROM airbnb_investment.bronze.raw_listings  ->  11551 | id
```
Ported verbatim, `TRY_CAST("id" AS DECIMAL(38,0))` casts the text `'id'`, returns NULL for every
row, and `WHERE listing_id IS NOT NULL` then drops all 102,591 — leaving an **empty table with no
error**. Occurrences: 02 (74), 03 (7), 04 (8), 05 (4), 06 (1). All now backticked.

### 🔴 ST_AREA HAS THE SAME UNIT TRAP AS ST_DWITHIN — a NEW instance
`06_silver_neighbourhoods_geo.sql:42` computes `ST_AREA(TO_GEOGRAPHY(...)) / 1e6`. Snowflake's
`ST_AREA` on GEOGRAPHY returns **square metres**; Databricks' returns **square degrees** at SRID
4326. Measured, against real borough areas:

| Borough | naive `st_area` | `st_area(st_transform(b,27700))/1e6` | true |
|---|---|---|---|
| Kingston upon Thames | 0.00481 | **37.26** | 37.25 km² |
| Croydon | 0.01116 | **86.49** | 86.52 km² |
| Bromley | 0.01938 | **150.13** | 150.15 km² |

A naive port is wrong by ~8 orders of magnitude and nothing fails. The log previously flagged only
`ST_DWITHIN`; **the trap applies to every metric ST_ function, not just distance.** Fix lands in
Phase B.

### Other findings verified this session (not assumed)
- ✅ `TRANSLATE(x,'{}','')` ports unchanged — `translate('{ABC-123}','{}','')` → `ABC-123`. Both
  engines delete when "to" is shorter. Checked because it defines the `transaction_uid` grain.
- ✅ `raw_overture_poi.GEOMETRY` is already native `GEOMETRY` at **SRID 4326** for all 634,958 rows,
  so `p.GEOMETRY AS location` in file 08 ports **unchanged**. `NAMES`/`CATEGORIES` are STRUCT →
  accessor change needed.
- ✅ `st_geomfromgeojson` returns SRID 4326, but takes a **STRING** — `f.value:geometry` is VARIANT,
  so it needs `to_json(...)` wrapped around it. `TO_GEOGRAPHY` accepted the VARIANT directly.
- ✅ `LATERAL variant_explode(raw:features)` works; VARIANT path accessors port verbatim.
- `NUMBER(p,s)` → `DECIMAL(p,s)`; `FLOAT` → **`DOUBLE`** (Snowflake FLOAT is 8-byte double,
  Databricks FLOAT is 4-byte REAL — lat/long would lose sub-metre precision).

### ⚠️ Two things to resolve later
1. **178 orphan listing_ids.** `calendar_cleaned` has 102,769 distinct `listing_id` but
   `listings_cleaned` has 102,591. Harmless in Silver (no join), but it will silently shrink any
   INNER join in Gold. Decide the join direction deliberately.
2. **`CLEAN_AUDIT` is empty** — Phase A ran the `.sql` files directly through `run_sql.py`. The
   audit rows come from `cleaning_layer.py`, which is Phase C.

### Phase B also done — 06, 08, 11 ported, run and verified

| Table | Rows | Grain unique? | Key check |
|---|---|---|---|
| `neighbourhoods_geo_cleaned` | **108** | ✅ | 📄 documented invariant PASSED |
| `poi_cleaned` | 134,713 | ✅ | **0** POIs unassigned to a borough |
| `listing_amenities` | 2,992,739 | ✅ | `Other` only **0.2%** of 13 groups |

🌍 **The ST_AREA fix validated against reality.** The 108 borough areas sum to **2,961 km²**;
true is London 1,572 + Greater Manchester 1,276 + Bristol 110 ≈ **2,958 km²** — a 0.1% match.
The naive port would have summed to ~0.38 (square degrees).

🔬 **All 134,713 POIs got a borough, zero unassigned** — the strongest available evidence the
SRIDs line up (polygons from `st_geomfromgeojson` at 4326 vs Bronze `GEOMETRY` at 4326). A
mismatch would have produced mass NULLs through the LEFT JOIN, not an error.

🔬 **`Other` at 0.2% proves the VARIANT→STRING cast is clean.** Had `f.value::string` kept the JSON
quotes, every LIKE in the ordered CASE would have failed and ~100% of 2,992,739 rows would have
landed in `Other` — in a table that still looks perfectly healthy. 29.2 amenities per listing
across 102,378 listings; Kitchen & Dining 28.4% is the top group.

### 🔴 SPLIT_PART(_FILENAME,'/',3) NO LONGER YIELDS THE CITY
Snowflake stored a **stage-relative** path so the city sat at position 3. Databricks
`_metadata.file_path` is a **full s3:// URL**, so position 3 is the *bucket name*:
```
s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/london/...
 1     3(bucket)                                      4    5             6(city)
```
Ported verbatim, the `CASE SPLIT_PART(...)` in file 12 — and in Gold's `DIM_NEIGHBOURHOOD`, which
`docs/data_pipeline.md:111` says uses "the same rule" — matches nothing and sets **CITY = NULL on
every row**. Silent. Affects files 12 and 14, both still to port. Use a depth-independent extract
rather than just changing 3 to 6, so a bucket or prefix change cannot break it again.

### Verified to port verbatim (checked, not assumed)
`try_parse_json` (returns NULL on bad JSON — load-bearing) · `f.value::string` strips JSON quotes ·
`SPLIT_PART` is 1-indexed and handles the **en dash** `' – '` · `LATERAL variant_explode` +
`:path::type` accessors · Overture `NAMES.primary` / `CATEGORIES.primary` STRUCT accessors ·
`p.GEOMETRY` needs no conversion · `ST_WITHIN` is topological so **no unit trap**.

### Created this session
```
databricks/cleaning_layer/01_silver_ddl.sql          02_silver_listings.sql
databricks/cleaning_layer/03_silver_calendar.sql     04_silver_reviews.sql
databricks/cleaning_layer/05_silver_neighbourhoods.sql  07_silver_price_paid.sql
databricks/cleaning_layer/06_silver_neighbourhoods_geo.sql  08_silver_poi.sql
databricks/cleaning_layer/11_silver_amenities.sql
```

### Phase C done — **SILVER IS COMPLETE (14 of 14) + driver**

Full driver run `run_id 508237821978575` → SUCCESS. `SILVER.CLEAN_AUDIT` populated, 13 rows:

| Table | rows_in | rows_out | dropped | attributable to |
|---|---|---|---|---|
| `listings_cleaned` | 102,591 | 102,591 | 0 | — |
| `calendar_cleaned` | 37,510,686 | 37,510,686 | 0 | — |
| `reviews_cleaned` | 2,676,100 | 2,676,100 | 0 | — |
| `neighbourhoods_cleaned` | 108 | 108 | 0 | — |
| `neighbourhoods_geo_cleaned` | 108 | 108 | 0 | — |
| `price_paid_cleaned` | 5,249,688 | 871,514 | 4,378,174 | county filter (verified: 0 lost to validation) |
| `poi_cleaned` | 634,958 | 134,713 | 500,245 | curated amenity allow-list — *is* the relevance filter |
| `code_point_cleaned` | 2,700,777 | 2,700,777 | 0 | — |
| `property_group_map` | 51 | 51 | 0 | — |
| `listing_amenities` | 2,992,739 | 2,992,739 | 0 | — |
| `postcode_neighbourhood_map` | 2,700,777 | 461,861 | 2,238,916 | UK-wide ONSPD → 3 cities' polygons |
| `ons_private_rent_cleaned` | 54,252 | 54,252 | 0 | — |
| `neighbourhood_ons_area_map` | 108 | 108 | 0 | — |

**Every drop is attributable to a documented rule. No unexplained loss anywhere in Silver.**

### 📄 THE 99.95% COVERAGE INVARIANT — measured and fully attributed
```
157,725 'ok' Price Paid postcodes · 157,383 mapped · 342 unmapped · 99.783%
```
🔴 **The denominator is EXACTLY 157,725 — identical to the Snowflake-era figure**
(`docs/data_pipeline.md:87`). `PRICE_PAID_CLEANED` was rebuilt from scratch on a different platform
and reproduced the old count to the row. **This is the closest thing to a genuine Snowflake parity
check that exists anywhere in this migration** — and it was not designed for, it fell out.

| Cause of the 342 | n | verdict |
|---|---|---|
| Absent from ONSPD entirely | **298** | stale edition — **292 (98%) have sales on/after Feb 2024**, the exact edition boundary |
| Geocoded, outside every polygon | 42 | genuine |
| Present but ungeocoded (sentinel) | 2 | genuine |

Both predicted effects are now **measured, not speculated**: ⬇️ 298 lost to the nine-release-old
edition, ⬆️ genuine misses fell from Snowflake's **87 → 44** because the terminated postcodes
resolve historic sales Code-Point Open never carried. **With ONSPD May 2026 the coverage should
reach ~99.97% — better than the documented 99.95%.** Gate stays measured-but-not-signed-off.

### 📄 32/32 London PASSED, including its documented exception
33 London neighbourhoods, 32 with an ONS area code; the unresolved one is **City of London** —
exactly what `etl/cleaning_layer/cleaning_layer.py:179` documents. Bristol 34 broadcast,
GM 32 broadcast + 9 exact, total 108.

### 🔴 Three more traps found in Phase C
1. **ONSPD ships a `lat = 99.999999` "no grid reference" sentinel — 24,012 rows.** Code-Point Open
   only ever shipped geocoded postcodes, so the original had nothing to guard. Unguarded, those
   postcodes get an **impossible latitude** where `st_within` silently never matches — they would
   masquerade as ordinary outside-the-polygon misses rather than missing data. `GEOM` is NULL for
   them and `IS_GEOCODED` records it, which is what let the 342 above be split three ways.
2. **Column DEFAULTs are INHERITED through CTAS.** File 13 failed with
   `WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED` despite declaring no default —
   `BRONZE.RAW_ONS_PRIVATE_RENT._LOAD_TS` carries one and the CTAS inherited the metadata. Fixed
   with `TBLPROPERTIES` on the CTAS. Only Silver table affected.
3. **A latent bug in the ORIGINAL driver.** Snowflake's GeoJSON `rows_in_sql` was
   `SELECT ARRAY_SIZE(RAW:features)` read at row `[0][0]` — it counted **one city's** features and
   ignored the other two. Replaced with an explode-and-count (correct and city-count independent).
   Also: `count_rows_in()` swallows every exception and returns 0, so an unported override would
   record `ROWS_IN = 0` and make `ROWS_DROPPED` negative without failing the run. Both helpers now
   **warn** instead of failing silently.

### Decisions recorded
- **Terminated postcodes KEPT + `IS_TERMINATED` flag** (Sunil, 2026-07-28) — justified by the
  numbers: genuine misses fell 87 → 44 because of them.
- **`GEOGRAPHY` column renamed `GEOM`** — in Databricks GEOGRAPHY is a distinct, narrower type, so
  the old name would actively mislead. **Gold must use `GEOM`.**
- **Table name `CODE_POINT_CLEANED` kept** despite the source change, so file 12 and Gold keep
  their references and files stay diffable. ⚠️ `docs/data_pipeline.md:84` still calls it Code-Point
  and needs updating.

### Created in Phase C
```
databricks/cleaning_layer/09_silver_code_point.sql   10_silver_property_group_map.sql
databricks/cleaning_layer/12_silver_postcode_neighbourhood_map.sql
databricks/cleaning_layer/13_silver_ons_private_rent.sql
databricks/cleaning_layer/14_silver_neighbourhood_ons_area_map.sql
databricks/cleaning_layer/cleaning_layer.py          databricks/run_silver.py
```

### ▶ RESUME HERE
**Nothing from Session 6 is committed.** All 16 new files are untracked on
`role/migration-databricks` (pushed and up to date through Session 5, commit `e907afb`).

⚠️ File 12 was moved from Phase B to Phase C — it reads `CODE_POINT_CLEANED`, which file 09 builds.
Stated rather than silently reordered.

### Next
1. **Commit Silver** to `role/migration-databricks`.
2. **Gold** — 20 Dynamic Tables → a Lakeflow pipeline. Do the **geospatial spike first**:
   `FCT_LISTING_POI` uses `ST_DWITHIN(...,500)`, and `st_dwithin` measures in SRID units
   (degrees at 4326), not metres. Use `st_transform(...,27700)`. `MART_AREA_POI` uses
   `ST_CONTAINS`, which is topological and safe.
   ⚠️ Gold must also use `GEOM` (not `GEOGRAPHY`) and the `regexp_extract` city rule.
   ⚠️ **178 orphan listing_ids** (calendar has 102,769 distinct, listings 102,591) will silently
   shrink any INNER join — decide the join direction deliberately.
3. Land **ONSPD May 2026** and re-run 09/12 to sign off the coverage gate.

---

## 2026-07-28 — Session 5: ONSPD landed and loaded — **BRONZE IS COMPLETE (9 of 9)**

**Agent:** Snowflake to Databricks Migrator (planned and executed in Opus 5)

### Status: `raw_onspd` loaded. The last Bronze blocker is cleared.

Sunil uploaded the ONSPD file to S3 himself this session, at
`raw/ons/postcode_directory/ONSPD_FEB_2024_UK.csv` (1.45 GB) — **not** the `raw/ons/postcodes/`
path the loader assumed. His folder name is the better one; the loader was changed to match rather
than moving a 1.45 GB object.

| Check | Result |
|---|---|
| Rows loaded | **2,700,777** |
| `count(*) == count(distinct pcds)` | ✅ **holds** — 2,700,777 == 2,700,777 |
| Terminated (`doterm` set) / live | 901,381 / 1,799,396 |
| `_RESCUED` non-null | **0** — not one malformed record |
| `LOAD_AUDIT` | `LOADED`, 2,700,777 parsed == loaded, 0 errors |
| Source files | 1 |

Job `run_id 55117842538502` → `SUCCESS`. Table verified by independent query afterwards, not by
trusting the job status.

### ✅ ALL ONSPD COLUMN MAPPINGS NOW CONFIRMED — no guesses remain
Read the real 53-column header. Every "UNCONFIRMED" row from Session 3 is resolved. Evidence is
row 1, `AB1 0AA` (a terminated Aberdeen postcode):

| Code-Point Open (old) | ONSPD | Evidence |
|---|---|---|
| `POSTCODE` | `pcds` | `AB1 0AA` |
| `ADMIN_DISTRICT_CODE` | `oslaua` | `S12000033` |
| `ADMIN_WARD_CODE` | `osward` | `S13002843` |
| `COUNTRY_CODE` | **`ctry`** | `S92000003` = Scotland — correct for an AB postcode |
| `ADMIN_COUNTY_CODE` | **`oscty`** | `S99999999` = "not applicable" pseudo-code |
| `POSITIONAL_QUALITY_INDICATOR` | **`osgrdind`** | `1` |
| `NHS_HA_CODE` | **`oshlthau`** | `S08000020` |
| `NHS_REGIONAL_HA_CODE` | **`nhser`** | `S99999999` |
| `GEOMETRY`/`GEOGRAPHY` | none — construct in Silver from `lat`/`long` | `57.101474`, `-2.242851` |

`09_silver_code_point.sql` can now be ported without a single unknown.

### 🔴 THE EDITION IS FEBRUARY 2024 — CURRENT RELEASE IS MAY 2026
ONSPD ships quarterly (Feb/May/Aug/Nov), so the landed file is ~9 releases behind. **This does not
affect Bronze** — the load is faithful to the file it has. **It does block judging the Silver
coverage gate**, because two effects act on the documented 99.95% invariant in opposite directions:

| Effect | Direction |
|---|---|
| Postcodes created after Feb 2024 absent → 2024-26 new-build sales in Price Paid can't resolve | coverage **down** |
| 901,381 terminated postcodes present that Code-Point Open never had → historic 2021-23 sales on retired postcodes now resolve | coverage **up** |

The net is not just unpredictable, it is **unattributable** — and rule #5 requires explanation, not
just a number. **Land the May 2026 edition before running the Silver coverage gate.**

Upgrading is a pure file drop: `newest_csv()` selects by `modification_time` and the write is
`CREATE OR REPLACE`. No code change for a new edition. Dropping the newer CSV alongside the old one
is enough.

### ⚠️ New Silver decision surfaced (was not on the radar)
Code-Point Open carried **live postcodes only**; ONSPD carries live + terminated. Keeping the
terminated ones is probably correct here — Price Paid is historic, so retired postcodes are exactly
what old sales reference — but it is a **behaviour change from Snowflake** and must be an explicit,
commented decision in `09_silver_code_point.sql`, not an accident of the source swap.

### Loader corrections (`06_onspd_load.py`)
| Fix | Why |
|---|---|
| `PREFIX` → `postcode_directory/` | matches the real upload path |
| `multiLine` → **`false`** | it is load-bearing for Airbnb CSVs (newlines in descriptions) but ONSPD has none, and `true` makes a 1.45 GB file **non-splittable** — single-threaded parse for zero benefit |
| Sanity band → ~2.7M UK | ⚠️ the old "~1.7–1.8M" was the Code-Point Open (GB, **live-only**) figure, which coincidentally equals ONSPD's *live* subset — a wrong expectation that would have passed for entirely the wrong reason. Commented so nobody "corrects" it back |
| Grain check now **raises**, not prints | `count(*) != count(distinct pcds)` is a parse failure, not dirty data |
| Header block | all nine mappings + their evidence values |

### Created this session
```
databricks/run_onspd.py    notebook runner, own file (not folded into run_bronze.py) so an
                           ONSPD reload never forces a rerun of the 37.5M-row calendar load
```

### Environment note (cost time this session)
Neither `aws` nor `databricks` is on the **PowerShell** PATH. The Databricks CLI is bundled with
the VS Code extension at
`C:\Users\Sunil\.vscode\extensions\databricks.databricks-2.12.3-win32-x64\bin\databricks.exe`.
`run_sql.py` calls bare `databricks`, so prepend that dir to `PATH` first. Combined with Session 4's
finding that `git` is not on the PowerShell PATH either: **use the Bash tool with an explicit
`export PATH=...` for all CLI work on this machine.** AWS CLI is not installed at all.

### ▶ RESUME HERE
**Still nothing committed.** `LOG.md`, `databricks/`, `setup/databricks/`,
`config/databricks_context.py`, `.gitignore` all outstanding; the two `etl/` deletions still staged.

### Next session
1. **Start Silver** — Bronze is done. 14 files. `09_silver_code_point.sql` is now fully specified.
2. Land ONSPD **May 2026** before running the Silver coverage gate (see above).
3. Decide and comment the terminated-postcode question in `09_silver_code_point.sql`.

---

## 2026-07-28 — Session 4: Snowflake is gone — verification model replaced

**Agent:** Snowflake to Databricks Migrator (planned and executed in Opus 5 — see process note)

### Status: no code migrated this session. The migration's *verification model* was rewritten.

### 🔴 SNOWFLAKE IS PERMANENTLY INACCESSIBLE — STOP PLANNING AROUND IT
Sunil confirmed the free trial has ended and he cannot log in. Session 3 already noted "no verified
Snowflake baselines"; this session makes it structural rather than a caveat.

**A new trial does not help.** It provisions an empty account, not the old tables. Recovering real
baselines would mean rebuilding the entire Snowflake pipeline just to run `COUNT(*)` against it —
strictly more work than the migration itself. The one cheap path that existed (converting the
*original* account to pay-as-you-go, which may have restored query access to the existing tables)
was checked with Sunil and is not available.

**Consequence:** every "row counts match Snowflake" gate in the plan was unpassable, and the agent
file still instructed future sessions to wait for them. Fixed below.

### What replaced it: invariant-based verification
New file **`databricks/verification_invariants.md`** — the per-table checklist a cold session reads
instead of querying Snowflake. Mined from `docs/` and the SQL headers, which is where the only
surviving observations of the working system live. Entries are tagged by provenance:
📄 documented · 🔬 structural · 🌍 ground truth · 🧪 measured-this-migration (**low trust — a record,
not a gate**).

The four documented Silver invariants that survived:

| Invariant | Value | Source |
|---|---|---|
| Postcode → neighbourhood coverage | 157,638 / 157,725 = **99.95%** | `docs/data_pipeline.md:87` |
| Neighbourhood names matching Airbnb | **108/108** | `docs/data_pipeline.md:88` |
| London boroughs → ONS area, `exact` | **32/32** | `docs/data_pipeline.md:96` |
| Polygon overlaps in the postcode bridge | **0** | `12_silver_postcode_neighbourhood_map.sql:17` |

✅ **The 99.95% figure transfers to ONSPD** — checked, not assumed. Its denominator is *Price Paid
`ok` postcodes* (`12_silver_postcode_neighbourhood_map.sql:23`), derived from `PRICE_PAID_CLEANED`,
**not** from the postcode table. Swapping Code-Point Open for ONSPD therefore does not move it.
⚠️ Expect the number to *rise* anyway: ONSPD carries terminated postcodes (`doterm`), so historic
sales on retired postcodes may now resolve. That is acceptable **only** if attributable to
`doterm IS NOT NULL` rows. An unexplained move either way is a blocker.

### Honest assessment of the trade
Snowflake parity would only ever have proven *"we reproduced Snowflake, bugs included."* Invariants
test against reality — session 3's British Museum coordinate check caught an SRID bug that a row
count sailed straight past. So this is a **stronger** gate for Bronze and a **genuinely weaker** one
for Gold, where nothing survives for any of the 20 marts and verification is now structural only
(cross-layer reconciliation, grain uniqueness, LEFT-join row preservation, no unexpected all-NULL
columns). **Gold must be reported as "reviewed, not proven."** Do not dress this up.

### 🔴 `LOG.md` and `.claude/` had been gitignored — LOG.md un-ignored
The uncommitted `.gitignore` change added both under "Ignore Claude Prompt". `git log -- LOG.md`
returned nothing: three sessions of migration knowledge existed only on one machine, untracked.
With Snowflake gone this file *is* the project's only memory of the old system's behaviour, so it
is now tracked, with a comment in `.gitignore` explaining why. `.claude/` left ignored — Sunil's
deliberate choice, not reversed.

### Agent file corrections (`.claude/agents/snowflake-to-databricks-migrator.md`)
Eight edits, all removing statements that would mislead a cold session:

| What | Was | Now |
|---|---|---|
| Rule #5 | "row counts and aggregate checksums match Snowflake" | invariant-based; records that Snowflake ended 2026-07-28 and why a new trial doesn't help |
| §Migration sequencing | all 5 gates = "match Snowflake" | invariant gates; setup/Bronze marked ✅ passed; Gold flagged as the weakest |
| §Parity verification | "mirror `count_rows()` against both platforms" | renamed §Verification (post-Snowflake); "a number with no expectation attached is not verification" |
| §Comms style | example "87,412 Snowflake vs 87,412 Databricks" | invariant-shaped example + "never imply a Snowflake comparison" |
| Workspace §, S3 | one external location; "verified by reading London listings (141,206 rows)" | all three locations + the one-location-per-prefix rule; retracted count removed |
| `METADATA$FILE_ROW_NUMBER` | "High risk — decide deliberately" | Resolved — records session 3's decision and the `RAW_ONS_PRIVATE_RENT` exception |
| §Known traps | — | added the `multiLine`+`escape` trap, `read_files` type inference, Delta column DEFAULTs, `NULL_IF` |
| Workspace gotchas | — | added `run_sql.py`, per-statement sessions, workspace-upload requirement, Connect unverified |

### Verified this session
- `git status` — `databricks/`, `setup/databricks/`, `config/databricks_context.py` untracked; the
  two `etl/` deletions still staged. Session 3's "nothing is committed" **confirmed accurate**.
- Notebooks hold **zero committed outputs** (`grep "output_type"` → 0 matches across all 9), so
  there were no salvageable Snowflake numbers hiding there. `docs/` was the only source.
- ⚠️ `git` is **not on PATH in PowerShell** on this machine — use the Bash tool for git.

### ▶ RESUME HERE
**Still uncommitted.** Nothing was committed this session (not asked for). `LOG.md`,
`databricks/verification_invariants.md`, and the `.gitignore` change join the untracked set.

**Unchanged blockers:** file 06 / ONSPD still needs Sunil to land the CSV at
`s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/ons/postcodes/`.

### Next session
1. **Read `databricks/verification_invariants.md` first.** It is now the gate definition — there is
   nothing else to check against.
2. Unblock 06 (ONSPD), confirm ~1.7–1.8M rows, fill in the three unconfirmed column mappings.
3. **Start Silver** (14 files) — three-level naming, `09_silver_code_point.sql` rewritten for ONSPD,
   Overture STRUCT accessors instead of VARIANT, EPSG:27700 for the geospatial work.

### Process note
`CLAUDE.md` rule #5 asks for planning in Fable or Opus 4.8 and execution in Opus 5. This session
planned and executed in Opus 5, as in sessions 1–3. Flagged rather than silently ignored.

---

## 2026-07-27 — Session 3: Bronze ported and loaded (7 of 8 files)

**Agent:** Snowflake to Databricks Migrator (planning in Fable, execution in Opus 5)

### Status: Bronze is live on Databricks. 5 of 6 Bronze tables loaded and verified.

| Table | Rows | Verified by |
|---|---|---|
| `raw_listings` | 102,591 | rows == distinct id per city; calendar ratio (below) |
| `raw_calendar` | 37,510,686 | 365 rows per listing per city — see ratio check |
| `raw_reviews` | 2,676,100 | loaded, no baseline |
| `raw_neighbourhoods` | 108 | matches borough count used by Overture |
| `raw_neighbourhoods_geo` | 3 | one VARIANT FeatureCollection per city |
| `raw_price_paid` | 5,249,688 | rows == distinct TRANSACTION_UID in all 6 years |
| `raw_overture_poi` | 634,958 | landmark coordinates verified against reality |
| `raw_ons_private_rent` | 48,910 | header at row 3, data from row 4 (Silver contract) |
| `raw_onspd` | — | **BLOCKED**, see below |

### 🔴 THE "141,206 BASELINE" IN SESSION 2 WAS WRONG — DO NOT USE IT
Session 2 recorded *"London listings @ snapshot 2026-06-19 = 141,206 rows"* as the Bronze
parity gate. **It is not a Snowflake number.** Re-read `LOG.md` Session 2: it came from a
Databricks `read_files()` probe run with DEFAULT options — no `multiLine`. Inside Airbnb
listings contain newlines inside quoted description fields, so every such newline became a
spurious row.

Measured on the same file, three ways:

| Read options | Rows | Distinct ids |
|---|---|---|
| `read_files` defaults (the Session 2 probe) | 141,206 | — |
| `+ multiLine=>true` | 93,672 | 92,966 |
| `+ multiLine=>true, escape=>'"'` | **92,638** | **92,638** |

Only the third is correct: rows == distinct ids exactly. `escape` matters as much as
`multiLine` — Spark's default escape is `\`, not RFC4180's doubled quote, and leaving it
wrong produced 706 phantom duplicate-id rows that a row count alone would never reveal.

Independent corroboration — calendar rows per listing:
`london 33,871,636/92,638 = 365.6` · `manchester 2,535,655/6,930 = 365.9` · `bristol 1,103,395/3,023 = 365.0`.
One row per listing per day, all three cities. **92,638 is right; 141,206 was an artifact.**

**Lesson for the rest of the migration:** a count from a probe is not a baseline. The
Snowflake trial is expired (confirmed with Sunil this session), so there are **no verified
Snowflake baselines for any Bronze table**. Every number above is internally consistent, not
cross-checked against Snowflake. Do not describe Bronze as "parity-verified".

### 🔴 One external location per prefix — a shared `raw/` location DOES NOT WORK
Session 2's plan assumed widening `airbnb_raw` to `raw/` would be free because the IAM policy
already grants `raw/*`. **It fails:**
```
databricks external-locations update airbnb_raw --url 's3://.../raw/' --force
  -> AWS IAM role does not have READ permissions on url s3://.../raw. PERMISSION_DENIED
```
The very same credential validates fine at CHILD prefixes. So Unity Catalog needs one
external location per prefix, unlike Snowflake's one-integration-many-stages model:

| External location | URL | Serves |
|---|---|---|
| `airbnb_raw` | `raw/inside_airbnb` | Airbnb snapshots (file 02) |
| `airbnb_raw_lr` | `raw/hm_land_registry` | Land Registry (files 03/04) |
| `airbnb_raw_ons` | `raw/ons` | private rents (07/08) + ONSPD (06) |

All three share the one storage credential `airbnb_s3_cred`. No AWS change was needed.

### Marketplace shares were ALREADY attached
Both listings Sunil named are live in the workspace as `DELTASHARING_CATALOG`:
- `carto_overture_maps_places.carto.place` — 75,642,289 global POIs
- `foursquare_os_places.fsq_os.{places,categories}`

⚠️ **Foursquare "OS" is *Open Source*, not *Ordnance Survey*.** It is a POI dataset with no GB
postcode units and **cannot** replace Code-Point Open. This was checked, not assumed.

### Overture port — three findings that would each have been a silent bug
1. **`geom` is WKB `binary`, not GEOGRAPHY** → `st_geomfromwkb(geom)`.
2. **SRID mismatch.** `st_geomfromwkb(...)` returns **SRID 0**; `st_geomfromgeojson(...)` on the
   borough polygons returns **SRID 4326**. Both are lon/lat degrees, so `st_within` across them
   looks like it works while being semantically undefined. Fixed with
   `st_setsrid(st_geomfromwkb(geom), 4326)`.
3. **The share ships a native `bbox` struct** `<xmin,xmax,ymin,ymax>` per row. Using it for the
   cheap prefilter beats Snowflake's per-row `ST_X`/`ST_Y`: 75,642,289 → 1,788,763 candidates
   (97.6% cut) before any geometry work. Exact point-in-polygon then gave 634,958.

Verified by coordinate, not just count — British Museum `-0.12703, 51.51954` (true 51.5194°N,
0.1270°W), Tate Modern `-0.09935, 51.5076` (true 51.5076°N, 0.0994°W), plus Manchester and
Bristol landmarks. Count parity alone would not have caught an SRID bug.

### Things that ported UNCHANGED (better than expected)
- **VARIANT path syntax is identical.** `f.value:properties:neighbourhood::STRING` works
  verbatim in Databricks. `LATERAL FLATTEN(input => x)` → `LATERAL variant_explode(x)`; the
  accessor and `::` cast need no edit at all.
- **`QUALIFY`** is supported and ports verbatim.
- **`latest_snapshot()`** logic unchanged — only `LIST` returning a `path` column instead of `name`.
- **GeoJSON as one VARIANT row** — `parse_json()` on a whole-text read reproduces Snowflake's
  `STRIP_OUTER_ARRAY = FALSE` shape exactly.

### Traps found while porting
- **`read_files()` INFERS CSV types by default.** Land Registry `_c1` came back INT and `_c2`
  TIMESTAMP, breaking the all-TEXT rule. `schemaHints` forcing all 16 to string is load-bearing.
  Casting back afterwards is NOT equivalent: an inferred TIMESTAMP re-renders as
  `2026-04-30T00:00:00.000Z` where the raw file holds `2026-04-30 00:00`.
  (The DataFrame API path avoids this differently — `inferSchema=false`.)
- **Delta rejects column DEFAULTs** until `TBLPROPERTIES ('delta.feature.allowColumnDefaults'='supported')`
  is set. Hit on `LOAD_AUDIT.LOAD_TS` and again on `RAW_ONS_PRIVATE_RENT._LOAD_TS`.
- **`NULL_IF` has no single-option equivalent.** Spark's `nullValue` takes ONE marker; Snowflake
  normalised four (`''`,`'NULL'`,`'null'`,`'N/A'`). Applied explicitly in code. Skipping this
  would leave `'N/A'` as a literal string where Snowflake stored NULL.
- **Statement Execution API: each call is its own session.** `USE CATALOG` does not persist
  between statements — pass `catalog`/`schema` in the request body instead.
- **Git Bash mangles workspace paths.** `databricks workspace ... /Workspace/...` becomes
  `E:/Git/Workspace/...`. Set `MSYS_NO_PATHCONV=1`.
- **`databricks catalogs create` still fails on Free Edition** (Session 2's finding holds).

### `_FILE_ROW_NUMBER` — decision made
Kept as a **synthetic `row_number()` per file** (Sunil's call), so the Bronze schema stays
identical to Snowflake and the five Silver SELECT lists port untouched. Evidence: it appears
in Silver only in SELECT lists, never in a WHERE/join, for every COPY-sourced table.
⚠️ Commented in every file as read-order, **not** a physical file line number.

**Exception:** `RAW_ONS_PRIVATE_RENT._FILE_ROW_NUMBER` is the REAL sheet row from `enumerate()`,
unchanged from Snowflake, and it IS load-bearing — Silver filters `>= 4`
(`13_silver_ons_private_rent.sql:56`). Verified live: row 3 is the header
`["Time period","Area code","Area name",...]`, data starts at row 4. Contract intact.

### File 06 — Code-Point Open replaced by ONSPD. **BLOCKED on Sunil.**
Loader is **written and ready**: `databricks/ingestion_layer/06_onspd_load.py`. It derives its
columns from the real ONSPD header at runtime, so it needs no edit when the file lands.

**Sunil's action:** download the current ONSPD release and land the CSV at
`s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/ons/postcodes/`. The external
location `airbnb_raw_ons` already covers it — no new UC object, no IAM change. Record the
ONSPD edition here the way `snapshot_date=` folders are tracked.

⚠️ **Silver will need rewriting for this table** — ONSPD column names differ from Code-Point:

| Code-Point Open (old) | ONSPD (new) | Confidence |
|---|---|---|
| `POSTCODE` | `pcds` | confirmed |
| `ADMIN_DISTRICT_CODE` | `oslaua` | confirmed |
| `ADMIN_WARD_CODE` | `osward` | confirmed |
| `GEOMETRY` / `GEOGRAPHY` | none — build in Silver from `lat`/`long`: `st_setsrid(st_point(long, lat), 4326)` | confirmed |
| `COUNTRY_CODE` | likely `ctry` | **unconfirmed** |
| `ADMIN_COUNTY_CODE` | possibly `oscty` | **unconfirmed** |
| `NHS_REGIONAL_HA_CODE`, `NHS_HA_CODE`, `POSITIONAL_QUALITY_INDICATOR` | no known equivalent | **unconfirmed** |

Verify the unconfirmed rows against the real header before porting `09_silver_code_point.sql`.

### Also needed for Silver (shape changes, not name changes)
Overture `NAMES`/`CATEGORIES`/`ADDRESSES`/`BRAND` arrive as native **STRUCT / ARRAY\<STRUCT\>**,
not VARIANT. Silver accessors change: `NAMES:primary::STRING` → `NAMES.primary`.

### Created this session
```
config/databricks_context.py                      session helper (get_session/use_schema/table)
databricks/ingestion_layer/01_bronze_ddl.sql      LOAD_AUDIT only; formats+stage+integration obsolete
databricks/ingestion_layer/02_bronze_load.py      Airbnb CSV + GeoJSON
databricks/ingestion_layer/03_land_registry_ddl.sql   creates nothing; documents the replacements
databricks/ingestion_layer/04_land_registry_load.sql  positional CSV + per-file audit
databricks/ingestion_layer/05_overture_poi_load.sql   Delta Sharing + WKB + SRID + bbox prefilter
databricks/ingestion_layer/06_onspd_load.py       ready, BLOCKED on the download
databricks/ingestion_layer/07_ons_private_rent_parse.py  openpyxl parse (was a stored proc)
databricks/ingestion_layer/08_ons_private_rent_load.py   orchestration (was CALL)
databricks/run_bronze.py                          notebook runner
databricks/run_ons_private_rent.py                notebook runner (%pip install openpyxl)
databricks/run_sql.py                             local .sql runner (CLI only, no deps)
```
Layout choice: a parallel top-level `databricks/` tree, so `etl/` stays runnable and cutover is
one directory swap. `config/ingestion_manifest.py` is **shared, not copied** — it is
platform-agnostic and duplicating it would invite drift.

### How the code runs (Databricks Connect NOT verified)
`databricks-connect` and `pyspark` are not installed locally, and Connect against Free Edition
serverless was never proven. Everything ran instead via:
- **SQL** → Statement Execution API against warehouse `bdef2ebe62faebea`
- **Python** → `databricks workspace import-dir` to
  `/Workspace/Users/ramjs016.310@gmail.com/airbnb-investment-app/`, then `databricks jobs submit`
  with a `notebook_task`. Headerless `.py` files import as workspace FILES, so they work as
  real Python modules.

The `get_session()` Connect fallback is written but **untested** — if it fails, use the notebook
path, which is proven.

### ▶ RESUME HERE — how to pick this up cold

**Nothing is committed.** `git status` will show `databricks/`, `config/databricks_context.py`
and the LOG/README edits as untracked or modified, plus the two Session 1 deletions still staged.

**Check Bronze is still there** (no setup needed — the CLI profile `airbnb` is all it takes):
```bash
python databricks/run_sql.py --sql "SELECT count(*) FROM airbnb_investment.bronze.raw_listings"
# expect 102,591
```

**Re-run any SQL loader:**
```bash
python databricks/run_sql.py databricks/ingestion_layer/04_land_registry_load.sql
python databricks/run_sql.py databricks/ingestion_layer/05_overture_poi_load.sql
```
`databricks/run_sql.py` drives the Statement Execution API through the CLI — no
`databricks-connect`, no `pyspark`, no pip install required.

**Re-run the Python loaders** (these must run in the workspace; there is no local Spark):
```bash
export MSYS_NO_PATHCONV=1   # Git Bash mangles /Workspace paths without this
WS=/Workspace/Users/ramjs016.310@gmail.com/airbnb-investment-app
databricks workspace import-dir ./config      "$WS/config"      --overwrite --profile airbnb
databricks workspace import-dir ./databricks  "$WS/databricks"  --overwrite --profile airbnb
databricks workspace import "$WS/databricks/run_bronze"            --file ./databricks/run_bronze.py            --format SOURCE --language PYTHON --overwrite --profile airbnb
databricks workspace import "$WS/databricks/run_ons_private_rent"  --file ./databricks/run_ons_private_rent.py  --format SOURCE --language PYTHON --overwrite --profile airbnb

# then submit, e.g.
databricks jobs submit --profile airbnb --no-wait --json '{
  "run_name":"bronze-load",
  "tasks":[{"task_key":"t","notebook_task":{"notebook_path":"'"$WS"'/databricks/run_bronze"}}]}'
databricks jobs get-run <run_id> --profile airbnb -o json
```
⚠️ **Re-upload after ANY local edit** — the workspace copy is a snapshot, not a live link.
Headerless `.py` files import as workspace FILES (so they work as real Python modules); the two
`run_*.py` runners carry a `# Databricks notebook source` header and must be imported as
NOTEBOOK, hence the separate commands.

Key identifiers: warehouse `bdef2ebe62faebea` · catalog `airbnb_investment` · profile `airbnb` ·
host `https://dbc-2c4f994e-b3df.cloud.databricks.com`.

### Next session
1. **Unblock 06** — land the ONSPD CSV, run the loader, confirm ~1.7–1.8M rows, then fill in
   the unconfirmed column mappings above.
2. **Start Silver** (`etl/cleaning_layer/`, 14 files). Known changes going in:
   - three-level naming throughout
   - `09_silver_code_point.sql` rewritten for ONSPD columns + constructed point geometry
   - Overture STRUCT accessors instead of VARIANT
   - `TO_GEOGRAPHY`/`ST_DWITHIN` → the EPSG:27700 approach from Session 2 (still the top project
     risk; `FCT_LISTING_POI` and `MART_AREA_POI` are in the aggregation layer, not Silver, but
     `06_silver_neighbourhoods_geo.sql` and `08_silver_poi.sql` set up their inputs)
3. **Nothing is committed.** All new files are untracked; `etl/01_bronze_ddl.sql` and
   `etl/02_bronze_load.py` remain staged for deletion from Session 1.

---

## 2026-07-27 — Session 2: Databricks bootstrap + capability probes

**Agent:** Claude Code (Opus 5)

### Workspace
- Host: `https://dbc-2c4f994e-b3df.cloud.databricks.com` · workspace_id `7474654279175711`
- Metastore: `2013dd5c-9b50-4e38-b3bf-65790d6fe43e` · default catalog `workspace`
- CLI v1.7.0 (bundled with the VS Code Databricks extension), profile **`airbnb`**
- **The workspace was not new** — it already held a `crime_data` catalog and a pipeline created
  2026-05-20. Session 1's "workspace does not exist yet" was wrong.

### Capability probes — ALL FIVE CLEARED ✅
| Capability | Result |
|---|---|
| Serverless SQL warehouse | ✅ `Serverless Starter Warehouse` (2X-Small), id `bdef2ebe62faebea` |
| Lakeflow Declarative Pipelines | ✅ Pipelines API live; one pre-existing pipeline |
| Databricks Apps | ✅ API responds (no apps deployed) |
| Git folders | ✅ GitHub OAuth already linked as `sunilramjali` |
| Storage credentials / external locations | ✅ Creation permitted (verified by probe, since deleted) |
| **Geospatial `ST_*`** | ✅ **97 functions, incl. `st_within` + `st_dwithin`** |

### 🔴 Geospatial: works, but NOT a like-for-like port
Databricks `ST_*` functions operate on **GEOMETRY**. `GEOGRAPHY` is a separate, narrower type —
passing it to `st_dwithin` or `st_distancesphere` fails with `DATATYPE_MISMATCH`. Snowflake's
`ST_DWITHIN` takes GEOGRAPHY and measures in **metres**; Databricks `st_dwithin` measures in
**the SRID's units**, which for 4326 is degrees. A naive port silently computes the wrong radius.

Two verified-working replacements (London test points, true distance ≈ 730 m):
```sql
-- Option A: spherical distance in metres, filter explicitly
st_distancesphere(geom_4326_a, geom_4326_b) <= 1000        -- returned 729.1 m

-- Option B: reproject to British National Grid (EPSG:27700), then st_dwithin in metres
st_dwithin(st_transform(a,27700), st_transform(b,27700), 1000)   -- returned true
st_distance(st_transform(a,27700), st_transform(b,27700))        -- returned 730.9 m
```
**Recommend Option B for UK data** — EPSG:27700 is the correct projected CRS for Great Britain,
distances come out in metres natively, and `st_dwithin` can use a spatial index. The 1.8 m
divergence from the spherical answer is immaterial for POI proximity.
Build geometries as `st_setsrid(st_geomfromtext(wkt), 4326)`; `TO_GEOGRAPHY` → `st_geomfromtext`.
Affects `FCT_LISTING_POI`, `MART_AREA_POI`, and the `06_silver_neighbourhoods_geo.sql` polygons.

### Other semantics confirmed
- `try_cast('$1,250.00' AS DECIMAL(10,2))` → `NULL` — **matches Snowflake `TRY_CAST`**, so the
  all-TEXT Bronze → typed Silver design ports unchanged.
- `typeof(parse_json('{"a":1}'))` → `variant` — native VARIANT type available.
- `st_within(point, polygon)` → `true`. Point-in-polygon works for neighbourhood assignment.

### Created
- Catalog **`airbnb_investment`** (MANAGED) + schemas **`bronze`**, **`silver`**, **`gold`**.
- ⚠️ `databricks catalogs create` **fails** on Free Edition ("Metastore storage root URL does not
  exist. Default Storage is enabled"). Use SQL `CREATE CATALOG` via the Statement Execution API
  instead — that path works. Schema creation via CLI is fine.

### ✅ S3 EXTERNAL LOCATION WORKING — Bronze is unblocked
IAM role `databricks-airbnb-s3-read` created in AWS (trust policy applied after a false start,
see gotcha below). Databricks objects created:
- Storage credential **`airbnb_s3_cred`** → `arn:aws:iam::988261629236:role/databricks-airbnb-s3-read`
- External location **`airbnb_raw`** (read_only) →
  `s3://airbnb-investment-app-988261629236-eu-west-2-an/raw/inside_airbnb/`

Verified end-to-end through the serverless warehouse:
```sql
LIST '.../raw/inside_airbnb/'          -- bristol/, greater_manchester/, london/   (matches CITIES exactly)
LIST '.../inside_airbnb/london/'       -- snapshot_date=2025-09-14/, snapshot_date=2026-06-19/
SELECT count(*) FROM read_files('.../london/snapshot_date=2026-06-19/listings/listings.csv.gz',
       format => 'csv', header => true)          -- 141,206 rows
```
**`latest_snapshot()` logic ports unchanged** — the constant prefix + ISO date still sort lexically,
so `snapshot_date=2026-06-19` wins. Cross-region (us-east-2 → eu-west-2) read works fine.

⚠️ **`databricks external-locations validate` does not exist in CLI v1.7.0.** Use a `LIST` or
`read_files()` query through the SQL warehouse as the real validation instead.

⚠️ **IAM trust policy is two-phase.** The UC trust policy names the role *itself* as a second
principal, and AWS validates principal ARNs at creation time — so a role cannot be created with
the final policy. Create with `setup/databricks/iam_trust_policy_step1.json` (UC principal only),
then edit the trust relationship to `iam_trust_policy.json` once the role exists.

### S3 handshake values (for the IAM trust policy)
Creating a storage credential returns the Databricks side of the handshake — the direct analogue
of Snowflake's `DESC INTEGRATION` (documented at `etl/ingestion_layer/01_bronze_ddl.sql:71-86`):
- `unity_catalog_iam_arn`: `arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL`
- `external_id`: `d781b099-9a6d-4198-b415-98183d94803d`

The existing IAM role `snowflake-airbnb-s3-read` trusts **Snowflake**, not Databricks — a **new
IAM role** (or an added trust statement) is required before Bronze can read the bucket.

### 🔴 Region mismatch — CONFIRMED
Metastore is `metastore_aws_us_east_2`, region **us-east-2** (Ohio). The raw bucket is in
**eu-west-2** (London). **Region is not selectable on Free Edition**, so this cannot be fixed
from the Databricks side.

Impact is modest: inter-region egress ~$0.02/GB billed to AWS account `988261629236` (not
Databricks), plus transatlantic latency. At Inside Airbnb volumes (a few hundred MB per
city-snapshot) a full Bronze rebuild costs pennies. It only matters if something re-scans
the bucket repeatedly. Treat as a latency/tidiness issue, not a budget one.

**Alternative on the table:** upload raw files to a UC Volume (`/Volumes/airbnb_investment/bronze/raw/`)
and skip S3 + IAM + egress entirely. Cost: loses the quarterly Lambda's automatic delivery.
Decision still open.

### Created this session (files)
`setup/databricks/` — `iam_trust_policy.json`, `iam_permission_policy.json`, `README.md`
(full handshake runbook, incl. the UC self-reference requirement in the trust policy).

### Next session — port Bronze
Infrastructure is done. All blockers cleared. Start writing code.

1. Port `etl/ingestion_layer/01_bronze_ddl.sql` → the storage integration + stage + file format
   sections are **obsolete** (replaced by `airbnb_raw`). Keep only `LOAD_AUDIT`, converting
   `AUTOINCREMENT` → `GENERATED ALWAYS AS IDENTITY`.
2. Port `etl/ingestion_layer/02_bronze_load.py`:
   - `get_session()` → `spark`; `session.sql(...)` → `spark.sql(...)`
   - `LIST @BRONZE.RAW_STAGE/<city>/` → `LIST 's3://.../inside_airbnb/<city>/'` — `latest_snapshot()`
     otherwise unchanged
   - `INFER_SCHEMA` + `USING TEMPLATE` (all-TEXT) → `read_files(..., schemaHints)` or read-as-string;
     **preserve the all-TEXT Bronze discipline** (`02_bronze_load.py:98-107`)
   - `METADATA$FILENAME` → `_metadata.file_path`; `METADATA$START_SCAN_TIME` → `current_timestamp()`
   - ⚠️ `METADATA$FILE_ROW_NUMBER` — still no equivalent. **Decide**: `row_number()` window per
     file, or drop. Do not drop silently.
   - `ON_ERROR = CONTINUE` → `_rescued_data` / `badRecordsPath`, still writing to `LOAD_AUDIT`
3. Parity gate: row counts per `RAW_*` table vs Snowflake. ~~Known baseline —
   **London listings @ snapshot 2026-06-19 = 141,206 rows.**~~
   🔴 **CORRECTED IN SESSION 3 — 141,206 IS WRONG.** It came from the `read_files()` probe
   above, run without `multiLine`, so newlines inside quoted description fields were counted
   as extra rows. The true figure is **92,638**. It was never a Snowflake number. See Session 3.

---

## 2026-07-27 — Session 1: Agent setup (no migration work yet)

**Agent:** Claude Code (Opus 5)

### Done
- Surveyed the repo's full Snowflake surface (setup, config, etl, notebooks, Streamlit).
- Created project-scoped agent `.claude/agents/snowflake-to-databricks-migrator.md`
  with the repo inventory, a Snowflake→Databricks translation reference, Free Edition
  bootstrap playbook, migration sequencing with parity gates, and known traps.
- Left the global `~/.claude/agents/engineering-data-engineer.md` untouched (stays generic).

### Key findings from the survey
- **20 `CREATE OR REPLACE DYNAMIC TABLE`** across `etl/aggregation_layer/` (5 dims, 5 facts,
  10 marts). `DIM_CITY_ASSUMPTIONS` and `DIM_DATE` are plain tables, not dynamic.
- **Geospatial is the top project risk** — `ST_WITHIN` / `ST_DWITHIN` / `TO_GEOGRAPHY` drive
  POI proximity in `FCT_LISTING_POI` and `MART_AREA_POI`. Must be spiked early.
- **`METADATA$FILE_ROW_NUMBER` has no Databricks equivalent** — real lineage in `BRONZE.RAW_*`.
  Needs a deliberate decision (window function per file, or accept the loss).
- ~~`etl/01_bronze_ddl.sql` and `etl/02_bronze_load.py` are divergent older copies~~ —
  **resolved, see cleanup below.**
- Two-level (`SCHEMA.TABLE`) → three-level (`catalog.schema.table`) naming is a repo-wide
  change touching ~28 SQL files and 4 Python modules.
- Streamlit's Gemini access gets *simpler* on Databricks: `NETWORK RULE` + `SECRET` +
  `EXTERNAL ACCESS INTEGRATION` collapses to a secret scope + app env vars.

### Cleanup: removed stale pre-S3 bronze duplicates
`git rm`'d `etl/01_bronze_ddl.sql` and `etl/02_bronze_load.py` (staged, not committed).
Evidence they were dead code:
- **Git history diverges at `c839b99` ("Brushed up").** Commits `5204f14` (S3 bucket ingestion)
  and `e58faea` (bronze DDL Replace→Alter) landed on the `etl/ingestion_layer/` copies only.
  The root copies received nothing after `c839b99`.
- **Nothing references them.** `config/ingestion_manifest.py`, `etl/cleaning_layer/cleaning_layer.py`,
  `README.md`, and `docs/` all point at `etl/ingestion_layer/`. The root copies referenced
  only each other.
- **They would fail at runtime.** The root loader reads `ds["name"]/["format"]/["file"]` and
  builds `@RAW_STAGE/<city>/<file>`. The current manifest also carries a `dir` key, and the
  real S3 layout is `<city>/snapshot_date=<date>/<dataset>/<file>` — the root copy has no
  `latest_snapshot()` resolution and would build wrong paths against an internal (not S3) stage.

Migrate only `etl/ingestion_layer/` for Bronze. Recover with `git checkout HEAD -- <path>` if needed.

### Not done / outstanding
- **Databricks workspace does not exist yet.** Nothing has been migrated.
- Next session starts with the Free Edition bootstrap: sign up, create catalog
  `airbnb_investment` + `bronze`/`silver`/`gold` schemas, then **verify** availability of:
  external locations to third-party S3, Lakeflow Declarative Pipelines, serverless SQL
  warehouses, Databricks Apps, and `ST_*` geospatial functions. Record findings here —
  every later design decision branches off them.

### Process note
`CLAUDE.md` rule #5 asks for planning in Fable or Opus 4.8 and execution in Opus 5.
This session both planned and executed in Opus 5 (model was set to Opus 5 before the
request). Flagged rather than silently ignored.
