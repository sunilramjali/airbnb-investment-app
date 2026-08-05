# Synthetic Snowpark-session stand-in for local dev while the real Snowflake
# account is suspended. Dispatches session.sql(query, params=...) on
# distinctive substrings in the query text (table/alias names) to canned
# pandas DataFrames with the right shape for the app's pages/helpers.
# Co-authored with CoCo
"""mock_session.py

MockSession duck-types the handful of snowflake.snowpark.Session methods the
app actually calls: .sql(query, params=None) -> object with .to_pandas() and
.collect(). It never talks to Snowflake.

Every "table" queried by the app is backed by a small synthetic universe of
neighbourhoods (real UK city/neighbourhood names), listings, and derived
aggregates, generated deterministically (seeded on city/neighbourhood/etc.)
so repeated queries return stable data within a run.

Cache-check queries (PROPERTY_TYPE_CACHE, LISTING_COMPARISON_CACHE,
ST_VS_LT_COMPARISON_CACHE, PROPERTY_COMPARISON_CACHE) always report a miss
(empty result), so the app's existing cache-miss -> generate fallback runs —
which now hits gemini.py's dev-disabled stub, so it stays fast and free.
"""
import hashlib
import json
import random

import pandas as pd

CITY_NEIGHBOURHOODS = {
    "London": [
        "Camden", "Hackney", "Islington", "Lambeth",
        "Southwark", "Wandsworth", "Westminster", "Greenwich",
    ],
    "Bristol": [
        "Clifton", "Redland", "Bedminster", "Southville", "Easton", "Bishopston",
    ],
    "Greater Manchester": [
        "Ancoats", "Chorlton", "Didsbury", "Salford Quays", "Northern Quarter", "Fallowfield",
    ],
}

CITY_BOUNDS = {
    # (lat_min, lat_max, lon_min, lon_max)
    "London": (51.45, 51.55, -0.25, 0.05),
    "Bristol": (51.42, 51.48, -2.65, -2.53),
    "Greater Manchester": (53.44, 53.52, -2.30, -2.15),
}

STRUCTURE_CLASSES = ["Flat", "House"]
BEDROOM_BUCKETS = ["1", "2", "3", "4+"]
BEDROOM_SORT = {"1": 1, "2": 2, "3": 3, "4+": 4}
PERSONAS = ["YIELD_MAXIMISER", "OCCUPANCY_OPTIMISER", "QUALITY_HOST"]
AMENITY_GROUPS = [
    "Dining & Nightlife", "Attractions & Culture", "Parks & Green",
    "Education", "Fitness", "Groceries & Essentials", "Health",
    "Transport", "Other",
]


def _rng(*parts):
    key = "|".join(str(p) for p in parts)
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2 ** 32)
    return random.Random(seed)


def _all_neighbourhoods():
    for city, hoods in CITY_NEIGHBOURHOODS.items():
        for hood in hoods:
            yield city, hood


def _centre(city, neighbourhood):
    lat_min, lat_max, lon_min, lon_max = CITY_BOUNDS[city]
    rng = _rng(city, neighbourhood, "centre")
    return rng.uniform(lat_min, lat_max), rng.uniform(lon_min, lon_max)


def _boundary_geojson(lat, lon, size=0.008):
    coords = [
        [lon - size, lat - size],
        [lon + size, lat - size],
        [lon + size, lat + size],
        [lon - size, lat + size],
        [lon - size, lat - size],
    ]
    return json.dumps({"type": "Polygon", "coordinates": [coords]})


def _extract(query, column, default=None):
    import re
    m = re.search(rf"{column}\s*=\s*'([^']*)'", query, re.IGNORECASE)
    return m.group(1) if m else default


# ---------------------------------------------------------------------------
# Core synthetic universes (built once, cached at module scope)
# ---------------------------------------------------------------------------

def _neighbourhood_stats_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        rng = _rng(city, hood, "stats")
        lat, lon = _centre(city, hood)
        listing_count = rng.randint(80, 900)
        avg_adr = rng.uniform(70, 320)
        median_adr = avg_adr * rng.uniform(0.85, 1.0)
        avg_occ = rng.uniform(45, 85)
        avg_rev = avg_adr * 365 * (avg_occ / 100)
        median_rev = avg_rev * rng.uniform(0.8, 1.0)
        rows.append({
            "CITY": city,
            "NEIGHBOURHOOD": hood,
            "LAT": lat,
            "LON": lon,
            "LISTING_COUNT": listing_count,
            "AVG_ADR": avg_adr,
            "MEDIAN_ADR": median_adr,
            "AVG_OCCUPANCY_RATE": avg_occ,
            "AVG_ANNUAL_REVENUE": avg_rev,
            "MEDIAN_ANNUAL_REVENUE": median_rev,
            "MEDIAN_SALE_PRICE": rng.uniform(220000, 950000),
            "AVG_BEDROOMS": rng.uniform(1.2, 3.2),
            "AVG_RATING": rng.uniform(4.0, 4.9),
            "AVG_REVIEW_RATING": rng.uniform(4.0, 4.9),
            "POI_COUNT": rng.randint(50, 600),
            "POI_DENSITY_SQKM": rng.uniform(20, 300),
            "TRANSPORT_COUNT": rng.randint(5, 120),
            "DINING_COUNT": rng.randint(10, 250),
            "AREA_SQKM": rng.uniform(1.5, 12.0),
            "PCT_SUPERHOST": rng.uniform(10, 55),
            "SCORE_YIELD_MAXIMISER": rng.uniform(35, 95),
            "SCORE_OCCUPANCY_OPTIMISER": rng.uniform(35, 95),
            "SCORE_QUALITY_HOST": rng.uniform(35, 95),
        })
    return rows


def _neighbourhood_stats_df():
    return pd.DataFrame(_neighbourhood_stats_rows())


def _listings_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        centre_lat, centre_lon = _centre(city, hood)
        for structure in STRUCTURE_CLASSES:
            for bedroom in BEDROOM_BUCKETS:
                rng = _rng(city, hood, structure, bedroom, "listings")
                bedrooms_num = {"1": 1, "2": 2, "3": 3}.get(bedroom, 4 + rng.randint(0, 2))
                for i in range(8):
                    adr = rng.uniform(55, 380)
                    occ_pct = rng.uniform(40, 88)
                    annual_revenue = adr * 365 * (occ_pct / 100)
                    revpar = adr * (occ_pct / 100)
                    lat = centre_lat + rng.uniform(-0.008, 0.008)
                    lon = centre_lon + rng.uniform(-0.008, 0.008)
                    listing_id = f"{city[:2].upper()}-{hood[:3].upper()}-{structure[0]}{bedroom}-{i}"
                    rows.append({
                        "LISTING_ID": listing_id,
                        "GEO_POINT": f"POINT({lon:.5f} {lat:.5f})",
                        "INSTANT_BOOKABLE": rng.random() < 0.4,
                        "LISTING_URL": f"https://example.com/listings/{listing_id}",
                        "NAME": f"{structure} near {hood}",
                        "NEIGHBOURHOOD": hood,
                        "PICTURE_URL": None,
                        "PROPERTY_GROUP": structure,
                        "PROPERTY_TYPE": "Entire home/apt",
                        "ROOM_TYPE": "Entire home/apt",
                        "STRUCTURE_CLASS": structure,
                        "ACCOMMODATES": bedrooms_num * 2,
                        "ADR": adr,
                        "ANNUAL_REVENUE": annual_revenue,
                        "AREA_MEDIAN_SALE_PRICE": rng.uniform(220000, 950000),
                        "BATHROOMS": max(1, bedrooms_num - 1),
                        "BEDROOMS": bedrooms_num,
                        "BEDS": bedrooms_num,
                        "DINING_COUNT_500M": rng.randint(0, 40),
                        "HOST_ID": f"host-{rng.randint(1000, 9999)}",
                        "LATITUDE": lat,
                        "LONGITUDE": lon,
                        "NUMBER_OF_REVIEWS": rng.randint(5, 300),
                        "OCCUPANCY_RATE": occ_pct,
                        "POI_COUNT_500M": rng.randint(5, 120),
                        "REVIEW_SCORES_RATING": rng.uniform(3.8, 5.0),
                        "REVPAR": revpar,
                        "TRANSPORT_COUNT_500M": rng.randint(0, 25),
                        "CITY": city,
                        "SCORE_YIELD_MAXIMISER": rng.uniform(30, 95),
                        "SCORE_OCCUPANCY_OPTIMISER": rng.uniform(30, 95),
                        "SCORE_QUALITY_HOST": rng.uniform(30, 95),
                        "HOST_IS_SUPERHOST": rng.random() < 0.3,
                        "BEDROOM_GROUP": bedroom,
                        "BEDROOM_BUCKET": bedroom,
                        "BEDROOM_SORT": BEDROOM_SORT[bedroom],
                    })
    return rows


def _listings_df():
    return pd.DataFrame(_listings_rows())


def _bedroom_agg_df():
    df = _listings_df()
    grouped = df.groupby(
        ["CITY", "NEIGHBOURHOOD", "STRUCTURE_CLASS", "BEDROOM_BUCKET", "BEDROOM_SORT"],
        as_index=False,
    ).agg(
        LISTING_COUNT=("LISTING_ID", "count"),
        AVG_ADR=("ADR", "mean"),
        MEDIAN_ADR=("ADR", "median"),
        AVG_ANNUAL_REVENUE=("ANNUAL_REVENUE", "mean"),
        MEDIAN_ANNUAL_REVENUE=("ANNUAL_REVENUE", "median"),
        AVG_OCCUPANCY_RATE=("OCCUPANCY_RATE", "mean"),
        AVG_RATING=("REVIEW_SCORES_RATING", "mean"),
        SCORE_YIELD=("SCORE_YIELD_MAXIMISER", "mean"),
        SCORE_OCC=("SCORE_OCCUPANCY_OPTIMISER", "mean"),
        SCORE_QUAL=("SCORE_QUALITY_HOST", "mean"),
    )
    return grouped


def _st_lt_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        for structure in STRUCTURE_CLASSES:
            for bedroom in BEDROOM_BUCKETS:
                rng = _rng(city, hood, structure, bedroom, "st_lt")
                listing_count = rng.randint(3, 60)
                st_annual = rng.uniform(12000, 55000)
                lt_annual = rng.uniform(9000, 30000)
                sale_price = rng.uniform(220000, 950000)
                st_yield = st_annual / sale_price * 100
                lt_yield = lt_annual / sale_price * 100
                rows.append({
                    "CITY": city,
                    "NEIGHBOURHOOD": hood,
                    "STRUCTURE_CLASS": structure,
                    "BEDROOM_BUCKET": bedroom,
                    "BEDROOM_SORT": BEDROOM_SORT[bedroom],
                    "LISTING_COUNT": listing_count,
                    "OCCUPANCY_CAP_NIGHTS": rng.randint(90, 365),
                    "MEDIAN_SALE_PRICE": sale_price,
                    "ST_ANNUAL_INCOME": st_annual,
                    "ST_GROSS_YIELD_PCT": st_yield,
                    "ASSUMED_LT_GROSS_YIELD_PCT": lt_yield * rng.uniform(0.95, 1.05),
                    "LT_ANNUAL_INCOME": lt_annual,
                    "LT_GROSS_YIELD_PCT": lt_yield,
                    "LT_RENT_SOURCE": "synthetic",
                    "ST_VS_LT_INCOME_UPLIFT": st_annual - lt_annual,
                    "ST_VS_LT_YIELD_UPLIFT_PPT": st_yield - lt_yield,
                    "ST_TO_LT_INCOME_RATIO": st_annual / lt_annual if lt_annual else None,
                    "ST_WINS": st_annual > lt_annual,
                    "SUFFICIENT_SAMPLE": listing_count >= 5,
                })
    return rows


def _st_lt_granular_df():
    return pd.DataFrame(_st_lt_rows())


def _st_lt_area_df():
    # Listing-count-weighted average per (CITY, NEIGHBOURHOOD), vectorized
    # (avoids groupby.apply/include_groups version differences across pandas).
    df = _st_lt_granular_df().copy()
    df["_ST_W"] = df["ST_ANNUAL_INCOME"] * df["LISTING_COUNT"]
    df["_LT_W"] = df["LT_ANNUAL_INCOME"] * df["LISTING_COUNT"]
    df["_ST_Y_W"] = df["ST_GROSS_YIELD_PCT"] * df["LISTING_COUNT"]
    df["_LT_Y_W"] = df["LT_GROSS_YIELD_PCT"] * df["LISTING_COUNT"]

    grouped = df.groupby(["CITY", "NEIGHBOURHOOD"], as_index=False).agg(
        LISTING_COUNT=("LISTING_COUNT", "sum"),
        _ST_W=("_ST_W", "sum"),
        _LT_W=("_LT_W", "sum"),
        _ST_Y_W=("_ST_Y_W", "sum"),
        _LT_Y_W=("_LT_Y_W", "sum"),
        ST_VS_LT_INCOME_UPLIFT=("ST_VS_LT_INCOME_UPLIFT", "sum"),
        ST_VS_LT_YIELD_UPLIFT_PPT=("ST_VS_LT_YIELD_UPLIFT_PPT", "sum"),
        ST_TO_LT_INCOME_RATIO=("ST_TO_LT_INCOME_RATIO", "sum"),
    )
    grouped["ST_ANNUAL_REVENUE"] = grouped["_ST_W"] / grouped["LISTING_COUNT"]
    grouped["LT_ANNUAL_RENT"] = grouped["_LT_W"] / grouped["LISTING_COUNT"]
    grouped["ST_GROSS_YIELD_PCT"] = grouped["_ST_Y_W"] / grouped["LISTING_COUNT"]
    grouped["LT_GROSS_YIELD_PCT"] = grouped["_LT_Y_W"] / grouped["LISTING_COUNT"]
    grouped = grouped.drop(columns=["_ST_W", "_LT_W", "_ST_Y_W", "_LT_Y_W"])
    return grouped


def _area_seasonal_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        rng = _rng(city, hood, "seasonal")
        for month in range(1, 13):
            total_nights = rng.randint(200, 900)
            occ = rng.uniform(0.35, 0.9)
            booked = int(total_nights * occ)
            rows.append({
                "CITY": city,
                "NEIGHBOURHOOD": hood,
                "MONTH": month,
                "LISTING_COUNT": rng.randint(20, 300),
                "TOTAL_NIGHTS": total_nights,
                "BOOKED_NIGHTS": booked,
                "OCCUPANCY_RATE": booked / total_nights if total_nights else 0.0,
            })
    return rows


def _area_seasonal_df():
    return pd.DataFrame(_area_seasonal_rows())


def _property_seasonal_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        for structure in STRUCTURE_CLASSES:
            for bedroom in BEDROOM_BUCKETS:
                rng = _rng(city, hood, structure, bedroom, "prop_seasonal")
                for month in range(1, 13):
                    total_nights = rng.randint(60, 300)
                    occ = rng.uniform(0.3, 0.9)
                    booked = int(total_nights * occ)
                    rows.append({
                        "CITY": city,
                        "NEIGHBOURHOOD": hood,
                        "STRUCTURE_CLASS": structure,
                        "BEDROOM_BUCKET": bedroom,
                        "BEDROOM_SORT": BEDROOM_SORT[bedroom],
                        "MONTH": month,
                        "LISTING_COUNT": rng.randint(3, 40),
                        "TOTAL_NIGHTS": total_nights,
                        "BOOKED_NIGHTS": booked,
                        "OCCUPANCY_RATE": booked / total_nights if total_nights else 0.0,
                        "SUFFICIENT_SAMPLE": True,
                    })
    return rows


def _property_seasonal_df():
    return pd.DataFrame(_property_seasonal_rows())


def _area_poi_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        centre_lat, centre_lon = _centre(city, hood)
        rng = _rng(city, hood, "poi")
        for i in range(18):
            group = AMENITY_GROUPS[i % len(AMENITY_GROUPS)]
            rows.append({
                "CITY": city,
                "NEIGHBOURHOOD": hood,
                "POI_NAME": f"{group.split(' ')[0]} Spot {i + 1}",
                "CATEGORY": group.lower().replace(" & ", "_").replace(" ", "_"),
                "AMENITY_GROUP": group,
                "IS_TRANSPORT": group == "Transport",
                "IS_DINING": group == "Dining & Nightlife",
                "LATITUDE": centre_lat + rng.uniform(-0.006, 0.006),
                "LONGITUDE": centre_lon + rng.uniform(-0.006, 0.006),
            })
    return rows


def _area_poi_df():
    return pd.DataFrame(_area_poi_rows())


def _ai_outputs_rows():
    rows = []
    for city, hood in _all_neighbourhoods():
        for persona in PERSONAS:
            rng = _rng(city, hood, persona, "ai_output")
            narrative = {
                "investment_summary": (
                    f"{hood} in {city} shows solid fundamentals for a "
                    f"{persona.replace('_', ' ').title()} investor, with steady "
                    f"demand and competitive pricing relative to nearby areas."
                ),
                "key_strengths": [
                    "Strong transport connectivity and walkability.",
                    "Consistent booking demand across the year.",
                    "Healthy density of dining and leisure amenities.",
                ],
                "key_risks": [
                    "Seasonal dips in shoulder months.",
                    "Rising local competition from new listings.",
                ],
                "confidence": rng.choice(["high", "medium", "low"]),
                "recommended_action": (
                    f"Shortlist {hood} for further due diligence given its "
                    f"persona fit for {persona.replace('_', ' ').title()}."
                ),
            }
            rows.append({
                "persona": persona,
                "neighbourhood_cleansed": hood,
                "output_type": "area_overview",
                "ai_narrative": json.dumps(narrative),
            })
    return rows


def _ai_outputs_df():
    return pd.DataFrame(_ai_outputs_rows())


def _area_overview_join_df():
    stats = _neighbourhood_stats_df().copy()
    stats = stats.sort_values("SCORE_YIELD_MAXIMISER", ascending=False).reset_index(drop=True)

    out = pd.DataFrame({
        "CITY": stats["CITY"],
        "NEIGHBOURHOOD": stats["NEIGHBOURHOOD"],
        "LISTINGS_COUNT": stats["LISTING_COUNT"],
        "AVERAGE_ADR": stats["AVG_ADR"],
        "MEDIAN_ADR": stats["MEDIAN_ADR"],
        "AVERAGE_OCCUPANCY_RATE": stats["AVG_OCCUPANCY_RATE"],
        "AVERAGE_ANNUAL_REVENUE": stats["AVG_ANNUAL_REVENUE"],
        "MEDIAN_ANNUAL_REVENUE": stats["MEDIAN_ANNUAL_REVENUE"],
        "MEDIAN_SALE_PRICE": stats["MEDIAN_SALE_PRICE"],
        "AVERAGE_NO_BEDROOMS": stats["AVG_BEDROOMS"],
        "AVERAGE_RATING": stats["AVG_RATING"],
        "POI_COUNT": stats["POI_COUNT"],
        "POI_DENSITY": stats["POI_DENSITY_SQKM"],
        "TRANSPORT_COUNT": stats["TRANSPORT_COUNT"],
        "DINING_COUNT": stats["DINING_COUNT"],
        "AREA": stats["AREA_SQKM"],
        "INVESTMENT_SCORE": stats["SCORE_YIELD_MAXIMISER"],
    })
    out["BOUNDARY"] = [
        _boundary_geojson(lat, lon) for lat, lon in zip(stats["LAT"], stats["LON"])
    ]
    out["LAT"] = stats["LAT"]
    out["LON"] = stats["LON"]
    out["INVESTMENT_RANK"] = range(1, len(out) + 1)
    return out


def _borough_summary_row(city, neighbourhood):
    df = _neighbourhood_stats_df()
    match = df[
        (df["CITY"].str.lower() == str(city).lower())
        & (df["NEIGHBOURHOOD"].str.lower() == str(neighbourhood).lower())
    ]
    if match.empty:
        return pd.DataFrame()

    row = match.iloc[0]
    out = pd.DataFrame([{
        "CITY": row["CITY"],
        "NEIGHBOURHOOD_CLEANSED": row["NEIGHBOURHOOD"],
        "LISTING_COUNT": row["LISTING_COUNT"],
        "AVG_PRICE": row["AVG_ADR"],
        "AVG_OCCUPANCY": row["AVG_OCCUPANCY_RATE"] / 100 * 365,
        "AVG_REVENUE": row["AVG_ANNUAL_REVENUE"],
        "AVG_REVIEW_RATING": row["AVG_REVIEW_RATING"],
        "PCT_SUPERHOST": row["PCT_SUPERHOST"],
        "SCORE_YIELD_MAXIMISER": row["SCORE_YIELD_MAXIMISER"],
        "SCORE_OCCUPANCY_OPTIMISER": row["SCORE_OCCUPANCY_OPTIMISER"],
        "SCORE_QUALITY_HOST": row["SCORE_QUALITY_HOST"],
    }])
    return out


def _review_themes_row(city, neighbourhood):
    rng = _rng(city, neighbourhood, "review_themes")
    themes = ["Great location", "Value for money", "Cleanliness", "Host communication", "Noise levels"]
    return pd.DataFrame([{
        "NEIGHBOURHOOD_CLEANSED": neighbourhood,
        "TOP_THEME": rng.choice(themes),
        "PCT_MENTIONS_PRICE": rng.uniform(5, 40),
        "PCT_MENTIONS_LOCATION": rng.uniform(10, 60),
        "AVG_SENTIMENT_SCORE": rng.uniform(0.3, 0.9),
    }])


def _property_bedroom_helper_df(city, neighbourhood):
    agg = _bedroom_agg_df()
    match = agg[
        (agg["CITY"].str.lower() == str(city).lower())
        & (agg["NEIGHBOURHOOD"].str.lower() == str(neighbourhood).lower())
    ].copy()
    if match.empty:
        return match

    out = pd.DataFrame({
        "NEIGHBOURHOOD": match["NEIGHBOURHOOD"],
        "STRUCTURE_CLASS": match["STRUCTURE_CLASS"],
        "LISTING_COUNT": match["LISTING_COUNT"],
        "avg_price": match["AVG_ADR"],
        "avg_occupancy": match["AVG_OCCUPANCY_RATE"],
        "avg_revenue": match["AVG_ANNUAL_REVENUE"],
        "avg_rating": match["AVG_RATING"],
        "sufficient_sample": True,
        "bedroom_bucket": match["BEDROOM_BUCKET"],
        "avg_score_yield_maximiser": match["SCORE_YIELD"],
        "avg_score_occupancy_optimiser": match["SCORE_OCC"],
        "avg_score_quality_host": match["SCORE_QUAL"],
    })
    return out


def _mart_bedrooms_join_df():
    agg = _bedroom_agg_df()
    out = pd.DataFrame({
        "CITY": agg["CITY"],
        "NEIGHBOURHOOD": agg["NEIGHBOURHOOD"],
        "STRUCTURE_CLASS": agg["STRUCTURE_CLASS"],
        "LISTING_COUNT": agg["LISTING_COUNT"],
        "AVERAGE_ADR": agg["AVG_ADR"],
        "MEDIAN_ADR": agg["MEDIAN_ADR"],
        "AVERAGE_ANNUAL_REVENUE": agg["AVG_ANNUAL_REVENUE"],
        "MEDIAN_ANNUAL_REVENUE": agg["MEDIAN_ANNUAL_REVENUE"],
        "AVERAGE_OCCUPANCY_RATE": agg["AVG_OCCUPANCY_RATE"],
        "AVERAGE_RATING": agg["AVG_RATING"],
        "ROBUST_SAMPLE": True,
        "SUFFICIENT_SAMPLE": True,
        "BEDROOM_GROUP": agg["BEDROOM_BUCKET"],
        "BEDROOM_NUM": agg["BEDROOM_SORT"],
        "INVESTMENT_SCORE_YIELD": agg["SCORE_YIELD"],
        "INVESTMENT_SCORE_OCCUPANCY": agg["SCORE_OCC"],
        "INVESTMENT_SCORE_QUALITY": agg["SCORE_QUAL"],
    })
    return out


def _area_persona_scores_df():
    agg = _bedroom_agg_df().groupby(["CITY", "NEIGHBOURHOOD"], as_index=False).agg(
        SCORE_YIELD_MAXIMISER=("SCORE_YIELD", "mean"),
        SCORE_OCCUPANCY_OPTIMISER=("SCORE_OCC", "mean"),
        SCORE_QUALITY_HOST=("SCORE_QUAL", "mean"),
    )
    return agg


def _listing_candidates_full_df():
    df = _listings_df().copy()
    out = df.rename(columns={
        "SCORE_YIELD_MAXIMISER": "INVESTMENT_SCORE_YIELD",
        "SCORE_OCCUPANCY_OPTIMISER": "INVESTMENT_SCORE_OCCUPANCY",
        "SCORE_QUALITY_HOST": "INVESTMENT_SCORE_QUALITY",
    })
    return out


def _investment_scores_join_df(query):
    # listing_comparison_helper.load_top_listings: INVESTMENT_SCORES i JOIN
    # MART_LISTING_CANDIDATES lc, persona score column aliased persona_score
    # e.g. "i.SCORE_YIELD_MAXIMISER       AS persona_score".
    import re
    df = _listings_df().copy()
    df = df.rename(columns={"ADR": "price_per_night"})
    m = re.search(r"i\.(\w+)\s+AS\s+persona_score", query, re.IGNORECASE)
    score_col = (m.group(1) if m else "SCORE_YIELD_MAXIMISER").upper()
    df["persona_score"] = df.get(score_col, df["SCORE_YIELD_MAXIMISER"])
    df.columns = [c if c == "persona_score" else c.lower() for c in df.columns]
    return df


def _investment_scores_grouped_df():
    # property_types_comparison_helper.load_investment_scores
    agg = _bedroom_agg_df().rename(columns={"BEDROOM_BUCKET": "bedroom_bucket"})
    agg.columns = [c.lower() if c not in ("bedroom_bucket",) else c for c in agg.columns]
    out = pd.DataFrame({
        "neighbourhood": agg["neighbourhood"],
        "structure_class": agg["structure_class"],
        "bedroom_bucket": agg["bedroom_bucket"],
        "avg_score_yield_maximiser": agg["score_yield"],
        "avg_score_occupancy_optimiser": agg["score_occ"],
        "avg_score_quality_host": agg["score_qual"],
    })
    return out


_CACHE_TABLES = (
    "PROPERTY_TYPE_CACHE",
    "LISTING_COMPARISON_CACHE",
    "ST_VS_LT_COMPARISON_CACHE",
    "PROPERTY_COMPARISON_CACHE",
)


class _MockResult:
    def __init__(self, df=None):
        self._df = df if df is not None else pd.DataFrame()

    def to_pandas(self):
        return self._df.copy()

    def collect(self):
        return []

    def count(self):
        return len(self._df)


class MockSession:
    """Duck-types the subset of snowflake.snowpark.Session the app uses."""

    def sql(self, query, params=None):
        df = self._resolve(query, params)
        return _MockResult(df)

    # -- dispatch --------------------------------------------------------
    def _resolve(self, query, params):
        q = query.upper()

        # Cache tables: always a miss on SELECT, no-op on INSERT/CREATE TABLE.
        if any(table in q for table in _CACHE_TABLES):
            if "SELECT" in q:
                return pd.DataFrame(columns=["AI_NARRATIVE"])
            return None  # INSERT / CREATE TABLE -> .collect()

        if "BOROUGH_SUMMARY" in q:
            city = _extract(query, "CITY")
            neighbourhood = _extract(query, "NEIGHBOURHOOD_CLEANSED")
            return _borough_summary_row(city, neighbourhood)

        if "REVIEW_THEMES" in q:
            city = _extract(query, "CITY")
            neighbourhood = _extract(query, "NEIGHBOURHOOD_CLEANSED")
            return _review_themes_row(city, neighbourhood)

        if "MART_BEDROOMS" in q:
            # property_types.py load_property_types (selects ROBUST_SAMPLE) vs
            # property_type_helper.load_property_bedroom_data (filtered to one
            # city/neighbourhood, selects lowercase avg_price/avg_occupancy).
            if "ROBUST_SAMPLE" in q:
                return _mart_bedrooms_join_df()
            city = _extract(query, "j1.CITY") or _extract(query, "CITY")
            neighbourhood = _extract(query, "p.NEIGHBOURHOOD") or _extract(query, "NEIGHBOURHOOD")
            return _property_bedroom_helper_df(city, neighbourhood)

        if "MART_AREA_OVERVIEW" in q:
            return _area_overview_join_df()

        if "AI_OUTPUTS" in q:
            return _ai_outputs_df()

        if "MART_ST_VS_LT" in q:
            if "GROUP BY" in q:
                return _st_lt_area_df()
            return _st_lt_granular_df()

        if "MART_PROPERTY_SEASONAL" in q:
            return _property_seasonal_df()

        if "MART_AREA_SEASONAL" in q:
            return _area_seasonal_df()

        if "MART_AREA_POI" in q:
            return _area_poi_df()

        if "GEO_POINT" in q:
            # listing_candidates.py load_listings — full listing rows.
            return _listing_candidates_full_df()

        if "PERSONA_SCORE" in q or "persona_score" in query:
            # listing_comparison_helper.load_top_listings
            return _investment_scores_join_df(query)

        if "avg_score_yield_maximiser" in query:
            # property_types_comparison_helper.load_investment_scores
            return _investment_scores_grouped_df()

        if "SCORE_YIELD_MAXIMISER" in q and "MART_LISTING_CANDIDATES" in q:
            # pages/1.1 load_area_persona_scores
            return _area_persona_scores_df()

        # Fallback: unknown query — return an empty frame rather than raising,
        # so unexpected/no-op SQL (e.g. session pings) doesn't crash a page.
        return pd.DataFrame()
