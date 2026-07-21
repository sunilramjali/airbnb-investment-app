# Helper for the Listing Candidates page: caches and generates persona-based top-vs-bottom listing comparisons via the live Gemini API.
# Co-authored with CoCo
"""
listing_comparison_helper.py
----------------------------
Helper module for the Listing Candidates Streamlit page.
Import and call get_or_generate_comparison() — all other
functions are internal.

Runs inside Snowflake Streamlit (Snowpark session).
Does NOT use snowflake.connector, streamlit, or a main block.
"""

import json
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE       = 'AIRBNB_INVESTMENT_DB'
GOLD_SCHEMA    = 'GOLD'
CACHE_TABLE    = 'LISTING_COMPARISON_CACHE'
MODEL          = 'gemini-3.1-flash-lite'
PROMPT_VERSION = 'v1'

PERSONAS = {
    'YIELD_MAXIMISER': {
        'label':         'Yield Maximiser',
        'focus':         'maximising annual revenue and nightly price',
        'score_col':     'score_yield_maximiser',
        'key_metrics':   ['annual_revenue', 'price_per_night', 'revpar'],
        'metric_labels': {
            'annual_revenue':  'Annual Revenue',
            'price_per_night': 'Nightly Price (ADR)',
            'revpar':          'RevPAR',
        },
    },
    'OCCUPANCY_OPTIMISER': {
        'label':         'Occupancy Optimiser',
        'focus':         'consistent high occupancy and booking flow',
        'score_col':     'score_occupancy_optimiser',
        'key_metrics':   ['occupancy_rate', 'number_of_reviews',
                          'annual_revenue'],
        'metric_labels': {
            'occupancy_rate':    'Occupancy Rate',
            'number_of_reviews': 'Review Count (booking proxy)',
            'annual_revenue':    'Annual Revenue',
        },
    },
    'QUALITY_HOST': {
        'label':         'Quality Host',
        'focus':         'exceptional guest ratings and Superhost status',
        'score_col':     'score_quality_host',
        'key_metrics':   ['review_scores_rating', 'number_of_reviews',
                          'host_is_superhost'],
        'metric_labels': {
            'review_scores_rating': 'Guest Rating',
            'number_of_reviews':    'Review Count',
            'host_is_superhost':    'Superhost Status',
        },
    },
}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def check_cache(session, city, neighbourhood, persona, property_group):
    try:
        result = session.sql(f"""
            SELECT AI_NARRATIVE
            FROM {DATABASE}.{GOLD_SCHEMA}.{CACHE_TABLE}
            WHERE CITY = '{city}'
            AND NEIGHBOURHOOD_CLEANSED = '{neighbourhood}'
            AND PERSONA = '{persona}'
            AND PROPERTY_GROUP = '{property_group}'
            LIMIT 1
        """).to_pandas()

        if len(result) > 0:
            val = result.iloc[0]['AI_NARRATIVE']
            if val and str(val).strip():
                return str(val)
        return None
    except Exception:
        return None


def write_to_cache(session, city, neighbourhood, persona, property_group,
                   narrative, top_listing_name, listing_count):
    df = pd.DataFrame([{
        'city':                   city,
        'neighbourhood_cleansed': neighbourhood,
        'persona':                persona,
        'property_group':         property_group,
        'top_listing_name':       top_listing_name,
        'listing_count':          listing_count,
        'ai_narrative':           narrative,
        'model_used':             MODEL,
        'prompt_version':         PROMPT_VERSION,
        'computed_at':            pd.Timestamp.now(),
    }])

    try:
        session.write_pandas(
            df,
            CACHE_TABLE,
            database=DATABASE,
            schema=GOLD_SCHEMA,
            overwrite=False,
            auto_create_table=True
        )
    except Exception as e:
        print(f'Cache write failed: {e}')


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_top_listings(session, city, neighbourhood, persona, property_group):
    score_col = PERSONAS[persona]['score_col']
    # score columns in INVESTMENT_SCORES are lowercase due to write_pandas

    df = session.sql(f"""
        SELECT
            lc.LISTING_ID,
            lc.NAME,
            lc.PROPERTY_GROUP,
            lc.ROOM_TYPE,
            lc.BEDROOMS,
            lc.BATHROOMS,
            lc.ADR              AS price_per_night,
            lc.OCCUPANCY_RATE,
            lc.ANNUAL_REVENUE,
            lc.REVPAR,
            lc.REVIEW_SCORES_RATING,
            lc.NUMBER_OF_REVIEWS,
            lc.POI_COUNT_500M,
            lc.TRANSPORT_COUNT_500M,
            lc.DINING_COUNT_500M,
            lc.HOST_IS_SUPERHOST,
            lc.LISTING_URL,
            i."{score_col}"     AS persona_score
        FROM {DATABASE}.{GOLD_SCHEMA}.INVESTMENT_SCORES i
        JOIN {DATABASE}.{GOLD_SCHEMA}.MART_LISTING_CANDIDATES lc
            ON i."listing_id" = lc.LISTING_ID
        WHERE i."city" = '{city}'
        AND i."neighbourhood_cleansed" = '{neighbourhood}'
        AND lc.PROPERTY_GROUP = '{property_group}'
        AND lc.ANNUAL_REVENUE > 0
        AND lc.OCCUPANCY_RATE > 0
        ORDER BY i."{score_col}" DESC
        LIMIT 10
    """).to_pandas()

    df.columns = df.columns.str.lower()
    return df


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def format_listing(row, rank, persona):
    superhost = 'Yes' if row.get('host_is_superhost') else 'No'

    if persona == 'YIELD_MAXIMISER':
        key_stats = (
            f"  Annual revenue: "
            f"£{float(row['annual_revenue']):,.0f}\n"
            f"  Nightly price (ADR): "
            f"£{float(row['price_per_night']):.0f}\n"
            f"  RevPAR: £{float(row['revpar']):.0f}\n"
            f"  Occupancy: "
            f"{float(row['occupancy_rate'])*100:.1f}%"
        )
    elif persona == 'OCCUPANCY_OPTIMISER':
        key_stats = (
            f"  Occupancy rate: "
            f"{float(row['occupancy_rate'])*100:.1f}%\n"
            f"  Review count: "
            f"{int(row.get('number_of_reviews', 0))} reviews\n"
            f"  Annual revenue: "
            f"£{float(row['annual_revenue']):,.0f}\n"
            f"  Nightly price: "
            f"£{float(row['price_per_night']):.0f}"
        )
    else:  # QUALITY_HOST
        key_stats = (
            f"  Guest rating: "
            f"{row.get('review_scores_rating', 'N/A')}/5\n"
            f"  Review count: "
            f"{int(row.get('number_of_reviews', 0))} reviews\n"
            f"  Superhost: {superhost}\n"
            f"  Occupancy: "
            f"{float(row['occupancy_rate'])*100:.1f}%"
        )

    return (
        f"Position {rank}: {row['name']}\n"
        f"  Investment score: "
        f"{float(row['persona_score']):.1f}/100\n"
        f"{key_stats}\n"
        f"  Room type: {row['room_type']}, "
        f"Bedrooms: {row.get('bedrooms', 'N/A')}, "
        f"Bathrooms: {row.get('bathrooms', 'N/A')}\n"
        f"  Transport links 500m: "
        f"{int(row.get('transport_count_500m', 0))}\n"
        f"  Dining options 500m: "
        f"{int(row.get('dining_count_500m', 0))}\n"
        f"  Total POIs 500m: "
        f"{int(row.get('poi_count_500m', 0))}"
    )


def build_prompt(city, neighbourhood, persona, property_group,
                 top_3, bottom_3):
    persona_info = PERSONAS[persona]

    top_text = '\n\n'.join([
        format_listing(row, i + 1, persona)
        for i, (_, row) in enumerate(top_3.iterrows())
    ])

    bottom_text = '\n\n'.join([
        format_listing(row, 8 + i, persona)
        for i, (_, row) in enumerate(bottom_3.iterrows())
    ])

    avg_top_score    = top_3['persona_score'].mean()
    avg_bottom_score = bottom_3['persona_score'].mean()
    score_gap        = avg_top_score - avg_bottom_score

    system_prompt = f"""You are an expert Airbnb investment \
analyst advising a {persona_info['label']} who prioritises \
{persona_info['focus']}.

You are comparing the top 3 vs bottom 3 listings from the \
top 10 {property_group} properties in {neighbourhood}, {city},
ranked by investment score for a {persona_info['label']}.

The average score gap between top and bottom is \
{score_gap:.1f} points. Explain what drives this gap \
specifically for a {persona_info['label']}.

CRITICAL PERSONA RULES:
- YIELD_MAXIMISER: lead with annual revenue, nightly price \
and RevPAR. Occupancy is secondary context only.
- OCCUPANCY_OPTIMISER: lead with occupancy rate and review \
count as booking proxy. Revenue is secondary context only.
- QUALITY_HOST: lead with guest rating, review count and \
Superhost status. Revenue and occupancy are secondary.

Use POI data (transport and dining within 500m) to explain \
location quality differences between top and bottom listings.

Respond with ONLY a valid JSON object, no other text:
{{
  "comparison_summary": "2-3 sentences explaining what \
separates the top 3 from the bottom 3 specifically \
for a {persona_info['label']}. Lead with the persona's \
primary metric. Reference actual scores and numbers.",
  "top_performer": "name of the rank 1 listing",
  "top_performer_reason": "one sentence on exactly why \
this listing ranks first — focus on the primary metric \
for this persona with specific numbers",
  "key_differentiator": "the single most important factor \
that separates top performers from bottom performers \
in this neighbourhood x property group combination. \
Must be specific to this persona's priorities.",
  "location_insight": "one sentence comparing the POI \
context of top vs bottom listings — transport and \
dining counts within 500m. State which group has \
better location access and why it matters for \
this persona.",
  "what_to_look_for": [
    "first specific criterion to prioritise when \
selecting a {property_group} here for this persona",
    "second specific criterion with actual benchmark \
numbers from the top 3 data"
  ],
  "what_to_avoid": "one specific red flag visible in the \
bottom 3 listings — something a {persona_info['label']} \
should actively screen out when evaluating listings"
}}"""

    user_prompt = f"""
City: {city}
Neighbourhood: {neighbourhood}
Property group: {property_group}
Persona: {persona_info['label']}
Avg investment score gap (top vs bottom): {score_gap:.1f} points

TOP 3 LISTINGS (positions 1-3 of top 10 by investment score):
{top_text}

BOTTOM 3 LISTINGS (positions 8-10 of top 10 by investment score):
{bottom_text}
"""
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def call_gemini(api_key, system_prompt, user_prompt):
    # Delegate to the app's single Gemini gateway (owns SDK, model, retries).
    from gemini import generate as gemini_generate

    combined = system_prompt + '\n\n' + user_prompt
    try:
        return gemini_generate(combined, api_key=api_key)
    except Exception:
        return None


def parse_response(ai_response):
    try:
        clean = ai_response.strip() if ai_response else None
        if clean and clean.startswith('```'):
            parts = clean.split('```')
            clean = parts[1]
            if clean.startswith('json'):
                clean = clean[4:]
            clean = clean.strip()
        json.loads(clean)  # validate it is real JSON
        return clean
    except Exception:
        return ai_response  # return raw if parse fails


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_generate_comparison(session, api_key, city, neighbourhood,
                                persona, property_group):
    """
    Check cache for an existing comparison narrative; generate and cache
    one if absent. Returns a JSON string or None if data is insufficient.

    Parameters
    ----------
    session        : Snowpark session (already open)
    api_key        : Google API key, e.g. from st.secrets
    city           : e.g. 'London'
    neighbourhood  : e.g. 'Westminster'
    persona        : 'YIELD_MAXIMISER' | 'OCCUPANCY_OPTIMISER' |
                     'QUALITY_HOST'
    property_group : e.g. 'Apartment / Flat'
    """
    # Step 1: Check cache
    cached = check_cache(session, city, neighbourhood, persona, property_group)
    if cached:
        return cached

    # Step 2: Load top 10 listings
    df_listings = load_top_listings(
        session, city, neighbourhood, persona, property_group
    )

    # Need at least 6 listings for a meaningful top 3 vs bottom 3 comparison
    if len(df_listings) < 6:
        return None

    top_3    = df_listings.head(3).reset_index(drop=True)
    bottom_3 = df_listings.tail(3).reset_index(drop=True)

    # Step 3: Build prompt and call Gemini
    system_prompt, user_prompt = build_prompt(
        city, neighbourhood, persona, property_group, top_3, bottom_3
    )

    ai_response = call_gemini(api_key, system_prompt, user_prompt)

    if not ai_response:
        return None

    narrative = parse_response(ai_response)

    # Step 4: Store in cache
    top_listing_name = top_3.iloc[0]['name'] if len(top_3) > 0 else 'Unknown'

    write_to_cache(
        session, city, neighbourhood, persona, property_group,
        narrative, top_listing_name, len(df_listings)
    )

    # Step 5: Return narrative
    return narrative
