# Data Pipeline — Joins & Filters (and why)

This document explains **how the data is joined together** and **what is filtered out at each
step, and why**. It is the "reasoning" companion to [architecture.md](architecture.md) (the
folder/flow map) and [data_sources.md](data_sources.md) (where the raw data comes from).

The pipeline is a medallion flow — **Bronze → Silver → Gold** — with a Streamlit app reading the
**GOLD marts only**. Bronze is a faithful, all-TEXT copy of the source files; almost all of the
cleaning logic and every join lives in **Silver** and **Gold**.

---

## Guiding principles (applied everywhere)

These four rules are applied in *every* Silver transform, so the per-table notes below only call
out the exceptions:

1. **`TRY_CAST` everything → a bad value becomes a countable `NULL`, never a lost row or a failed
   load.** Text like `"$1,250.00"`, `"95%"`, `"t"/"f"` is parsed explicitly; anything unparseable
   lands as `NULL` and can be counted, rather than silently killing the row.
2. **Deduplicate to the table's grain with `QUALIFY ROW_NUMBER() ... ORDER BY _LOAD_TS DESC` —
   latest load wins.** Guarantees exactly one row per key even if a file is re-ingested.
3. **Validate, don't guess.** Rows with no usable key (or physically impossible values) are
   dropped; questionable-but-usable rows are *kept and flagged* (see Price Paid `quality_flag`)
   so the choice to include them is the consumer's, not the pipeline's.
4. **Lineage is carried through** (`_FILENAME`, `_FILE_ROW_NUMBER`, `_LOAD_TS`) so any Silver/Gold
   row can be traced back to its Bronze source file.

---

## Silver — cleaning filters (per source)

| Silver table | Grain | What is filtered / dropped | Why |
|---|---|---|---|
| `LISTINGS_CLEANED` | one row per `listing_id` | drop rows with `listing_id IS NULL` or `latitude`/`longitude` outside `[-90,90]`/`[-180,180]`; dedupe latest scrape | a listing with no id can't be joined; impossible coordinates break the spatial joins downstream |
| `CALENDAR_CLEANED` | `listing_id × date` | drop rows with no `listing_id` or no `date`; dedupe | those two columns *are* the grain — a row missing either is unusable. (No price column exists in this scrape — nightly rate comes from `LISTINGS_CLEANED.PRICE`.) |
| `REVIEWS_CLEANED` | one row per `review_id` | drop rows with no `review_id` or no `listing_id`; dedupe | a review must have an id and must tie back to a listing |
| `PRICE_PAID_CLEANED` | one row per transaction | **county filter** to `GREATER LONDON` / `GREATER MANCHESTER` / `CITY OF BRISTOL`; drop rows with no transaction id, `price <= 0`, or unparseable date; dedupe | restrict ~5.25M national rows to the three investment cities *before* validation/dedup so we only process target rows; the rest are data errors |
| `POI_CLEANED` | one row per POI id | keep **only** categories on a curated amenity allow-list; must have a name and geometry; dedupe | the allow-list *is* the "is this investment-relevant?" filter (see below) |

### Price Paid — kept-but-flagged, not dropped (`quality_flag`)

HM Land Registry rows are **never dropped for being "non-market"** — they are labelled so each
consumer chooses. The flag is deterministic (fixed bounds, not percentiles) so it is reproducible
on every reload:

- `non_standard` — PPD category **B** (repossessions, company/portfolio transfers, multi-property
  sales). ~20% of rows. Not arm's-length market sales.
- `price_suspect` — a standard sale whose price is outside fixed sanity bounds (`< £10,000` or
  `> £20,000,000`) — almost certainly a data-entry error.
- `ok` — arm's-length market sale within bounds.

**Every sale-price benchmark in Gold filters `WHERE quality_flag = 'ok'`**, so medians reflect
true market sales; the flagged rows remain available for repossession/investor views.

### POI — curated allow-list, exact tokens not fuzzy `LIKE`

`POI_CLEANED` keeps only categories that plausibly affect property value (Transport, Attractions
& Culture, Parks & Green, Dining & Nightlife, Groceries & Essentials, Fitness, Education, Health).
Matching is on **exact category tokens** (`IN`-lists), not wildcards, because naive `LIKE` pulls in
noise: `%park%` → *parking*, `%school%` → *driving/dance schools*, `%bar%` → *barber*,
`%bus%` → *business services*. Only two safe wildcards are used (`%restaurant%`, `%grocery%`). Any
POI matching **no** group is dropped — the allow-list is the relevance filter.

### Amenities — ordered first-match classification

`LISTINGS_CLEANED.amenities` (a JSON blob) is exploded to one row per listing × amenity and
classified into ~13 curated groups via an **ordered `CASE` (first match wins)**. Ordering matters
to avoid substring collisions (e.g. more specific tokens must be tested before generic ones). This
feeds the amenity-coverage marts.

---

## The two spatial / crosswalk bridges (why they exist)

The sources are located on **different geographies** and cannot be joined directly. Two Silver
bridge tables reconcile them onto the shared **neighbourhood** grain.

### 1. Postcode → neighbourhood (`POSTCODE_NEIGHBOURHOOD_MAP`)

- **Problem:** Land Registry sales are located by **postcode only** (no lat/long, no
  neighbourhood); Airbnb listings are located by **neighbourhood**.
- **Join:** point-in-polygon —
  `ST_WITHIN(CODE_POINT_CLEANED.GEOGRAPHY /*postcode centroid*/, NEIGHBOURHOODS_GEO_CLEANED.BOUNDARY)`.
- **Grain:** one row per `POSTCODE_KEY` (space-stripped, upper-cased). A defensive
  `QUALIFY ROW_NUMBER()` guarantees uniqueness (0 polygon overlaps actually observed).
- **Coverage:** 157,638 / 157,725 = **99.95%** of `ok` postcodes map to a neighbourhood; 108/108
  neighbourhood names match Airbnb exactly.
- **Consumer:** `GOLD.FCT_AREA_SALE_PRICE`.

### 2. Neighbourhood → ONS area (`NEIGHBOURHOOD_ONS_AREA_MAP`)

- **Problem:** ONS Price Index of Private Rents is published at **local-authority** grain; the
  facts aggregate at **neighbourhood** grain.
- **Join:** a name crosswalk with a `rent_grain` flag recording resolution quality:
  - **`exact`** — London boroughs map 1:1 to their ONS area (32/32); Greater Manchester
    `"<X> District"` neighbourhoods map to ONS district *X*.
  - **`broadcast`** — many neighbourhoods share one ONS area (Manchester wards → *Manchester*;
    Bristol wards → *Bristol, City of*). Rent is identical across those neighbourhoods, so any
    yield spread there comes only from sale-price / Airbnb-revenue variation.
- The London regional roll-up (`E12000007`) is excluded so only district-level areas match.
- **Consumer:** `GOLD.FCT_AREA_RENT`.

---

## Gold — the star joins (dimensions & facts)

| Object | Join(s) | Type | Why |
|---|---|---|---|
| `DIM_LISTING` | `LISTINGS_CLEANED` ⟕ `PROPERTY_GROUP_MAP` on `LOWER(TRIM(property_type))` | LEFT | attaches `STRUCTURE_CLASS` (Flat/House) and `PROPERTY_GROUP` from the **single source of truth**, so the Airbnb (ST) side and the sale-price (LT) side can never disagree. LEFT so unmatched types survive as `Other/Unknown`. Also derives `GEO_POINT = ST_MAKEPOINT(lon,lat)`. |
| `DIM_NEIGHBOURHOOD` | — (from `NEIGHBOURHOODS_GEO_CLEANED`) | — | carries `CITY` (derived from the source file path) and the `BOUNDARY` geography used for point-in-polygon attribution. |
| `DIM_POI` | — (from `POI_CLEANED`) | — | filters `WHERE CONFIDENCE >= 0.5` (keep reasonably confident POIs); centralises `IS_TRANSPORT` / `IS_DINING` classification so the three POI consumers don't re-derive keyword lists. |
| `DIM_HOST` | — (from `LISTINGS_CLEANED`) | — | dedupes to one row per `HOST_ID` (latest scrape wins). |
| `FCT_LISTING_SNAPSHOT` | from `DIM_LISTING` | — | per-listing investment metrics; sets the **conformed `IS_ACTIVE` flag** (`OCCUPANCY_NIGHTS >= 30`) that every mart reuses rather than re-deriving. |
| `FCT_LISTING_POI` | `DIM_LISTING` ⟕ `DIM_POI` on `ST_DWITHIN(GEO_POINT, LOCATION, 500)` | LEFT | counts POIs within **500m** of each listing. Deliberately **separated** from the snapshot so the expensive spatial join doesn't slow snapshot refresh. |
| `FCT_AREA_SALE_PRICE` | `PRICE_PAID_CLEANED` ⋈ `POSTCODE_NEIGHBOURHOOD_MAP` on `POSTCODE_KEY`, `WHERE quality_flag='ok'` | INNER | the **single** area-level sale-price benchmark. Grain `NEIGHBOURHOOD × STRUCTURE_CLASS` (Flat/House/Other/All); `All` pools residential F,D,S,T. Replaces fragile per-mart district-name matching. |
| `FCT_AREA_RENT` | `ONS_PRIVATE_RENT_CLEANED` (latest month) ⋈ `NEIGHBOURHOOD_ONS_AREA_MAP` on `ONS_AREA_CODE` | INNER | observed long-term rent. Grain `NEIGHBOURHOOD × RENT_CATEGORY` (overall / structure / bedroom). `House` = mean of Detached/Semi/Terraced (so it lines up with `STRUCTURE_CLASS`). ONS does **not** cross bedroom × structure, so bedroom rent is structure-independent. |

---

## Gold — the mart join & filter conventions

The consumer marts share **one like-for-like universe** so their numbers reconcile with each
other. Unless a mart says otherwise, its per-listing base applies:

```sql
WHERE STRUCTURE_CLASS IN ('Flat','House')   -- purchasable dwellings only (hotels/boats/etc. excluded)
  AND ROOM_TYPE = 'Entire home/apt'          -- whole property, like-for-like
  AND IS_ACTIVE                              -- actively let: estimated 30+ booked nights, trailing 12m
```

- **Why `STRUCTURE_CLASS IN ('Flat','House')`** — only these have a Land Registry sale comparator,
  so a buy-vs-rent yield can be computed honestly. `NULL`-class types (hotels, guest accommodation,
  unique stays, outdoor) are kept in the data but excluded from the yield comparison.
- **Why `IS_ACTIVE`** — a booked night is only *proxied* as `AVAILABLE = FALSE` in the calendar.
  Dormant/host-blocked listings would make blocked nights masquerade as bookings and inflate
  occupancy, so seasonal and yield marts drop them.
- **Why `BEDROOMS >= 1`** in bedroom-grain marts — drops Studio (0) and Unknown (NULL); buckets are
  `1 / 2 / 3 / 4+` (`4+` folds 4 and 5+, matching ONS's "Four or more bedrooms").

### Mart-specific joins & rules

- **`MART_LISTING_CANDIDATES`** — the app's per-listing source. `FCT_LISTING_SNAPSHOT` ⋈
  `DIM_LISTING`, then LEFT joins to `DIM_HOST`, `FCT_LISTING_POI`, and `FCT_AREA_SALE_PRICE`
  (matched on `NEIGHBOURHOOD` **and** `STRUCTURE_CLASS`) for the area buy-price benchmark. LEFT so a
  listing never disappears just because a host/POI/sale-price row is missing.
- **`MART_AREA_OVERVIEW` / `MART_AREA_POI`** — POIs attributed to an area by
  `ST_CONTAINS(BOUNDARY, LOCATION)` (point-in-polygon); `MART_AREA_OVERVIEW` joins
  `FCT_AREA_SALE_PRICE` on `STRUCTURE_CLASS = 'All'` for the pooled area median.
- **`MART_ST_VS_LT`** — the headline buy-vs-Airbnb comparison at
  `CITY × NEIGHBOURHOOD × STRUCTURE_CLASS × BEDROOM_BUCKET`. ST income is **pure capped**:
  `median(ADR × LEAST(booked nights, city legal cap))`, where the cap comes from
  `DIM_CITY_ASSUMPTIONS` (**London = 90 nights**, Manchester/Bristol = 365/uncapped) — so London's
  short-let cap is self-documenting in the uplift columns.
- **LT rent fallback chain** — `COALESCE(bedroom ONS rent, structure ONS rent, modelled)`, where
  *modelled* = `sale price × per-city assumed gross yield`. `LT_RENT_SOURCE`
  (`observed_bedroom` / `observed_structure` / `assumed`) records which was used, so the app can
  show when a figure is real vs modelled.
- **Sale price is shared across bedroom buckets** — Land Registry has property type but **no
  bedroom count**, so a bedroom-specific buy price (and bedroom yield) cannot be derived honestly.
  Buy price therefore lives at structure grain (`MART_PROPERTY_TYPE`), not on `MART_BEDROOMS`.
- **Thin-cell guards** — finer grains produce sparse cells, so marts expose
  `SUFFICIENT_SAMPLE` (`LISTING_COUNT >= 5`) and, where relevant, `ROBUST_SAMPLE`
  (`>= 10`) and `CITY_*` fallback benchmarks — flagging thin cells rather than hiding them.
- **Amenity gap (`MART_AREA_AMENITY_GAP`)** — segments an area's active listings into top revenue
  quartile vs the rest (`NTILE(4)`), then compares amenity-group coverage. Explicitly labelled
  **associational, not causal**, with `SUFFICIENT_SAMPLE` (`TOP_N >= 5 AND REST_N >= 15`).

---

## One-line summary

Bronze copies the files verbatim; **Silver types, validates (drop only the unusable, flag the
questionable), and builds the two spatial bridges** that put every source on the neighbourhood
grain; **Gold joins them into a star and applies the like-for-like investment filters**
(purchasable dwellings, entire-home, actively let) so the app's benchmarks are honest and mutually
consistent.
