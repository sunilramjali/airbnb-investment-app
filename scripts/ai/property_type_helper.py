"""
property_type_helper.py
-----------------------
Helper module for the Property Type Streamlit page.
Import and call get_or_generate_recommendation() — all other
functions are internal.

Runs inside Snowflake Streamlit (Snowpark session).
Does NOT use snowflake.connector, streamlit, or a main block.
"""

import json
import time
import pandas as pd
from google import genai

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE       = 'AIRBNB_INVESTMENT_DB'
GOLD_SCHEMA    = 'GOLD'
OUTPUT_TABLE   = 'AI_OUTPUTS'
OUTPUT_TYPE    = 'RECOMMENDATION'
MODEL          = 'gemini-3.1-flash-lite'
PROMPT_VERSION = 'v1'

PERSONAS = {
    'YIELD_MAXIMISER': {
        'label':     'Yield Maximiser',
        'focus':     'maximising annual revenue, high nightly '
                     'price, strong booking demand',
        'score_col': 'avg_score_yield_maximiser',
    },
    'OCCUPANCY_OPTIMISER': {
        'label':     'Occupancy Optimiser',
        'focus':     'consistent high occupancy, minimal vacancy, '
                     'steady booking flow',
        'score_col': 'avg_score_occupancy_optimiser',
    },
    'QUALITY_HOST': {
        'label':     'Quality Host',
        'focus':     'exceptional guest experience, high ratings, '
                     'superhost status, premium positioning',
        'score_col': 'avg_score_quality_host',
    },
}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def check_cache(session, city, neighbourhood, persona):
    try:
        result = session.sql(f"""
            SELECT AI_NARRATIVE
            FROM {DATABASE}.{GOLD_SCHEMA}.{OUTPUT_TABLE}
            WHERE CITY = '{city}'
            AND NEIGHBOURHOOD_CLEANSED = '{neighbourhood}'
            AND PERSONA = '{persona}'
            AND OUTPUT_TYPE = '{OUTPUT_TYPE}'
            AND PROMPT_VERSION = '{PROMPT_VERSION}'
            LIMIT 1
        """).to_pandas()
        if len(result) > 0:
            val = result.iloc[0]['AI_NARRATIVE']
            if val and str(val).strip():
                return str(val)
        return None
    except Exception:
        return None


def write_to_cache(session, city, neighbourhood, persona,
                   narrative, investment_score, metrics_json, confidence):
    df = pd.DataFrame([{
        'city':                   city,
        'neighbourhood_cleansed': neighbourhood,
        'persona':                persona,
        'output_type':            OUTPUT_TYPE,
        'investment_score':       investment_score,
        'ai_narrative':           narrative,
        'confidence':             confidence,
        'metrics_json':           metrics_json,
        'prompt_version':         PROMPT_VERSION,
        'model_used':             MODEL,
        'computed_at':            pd.Timestamp.now(),
    }])
    try:
        session.write_pandas(
            df,
            OUTPUT_TABLE,
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

def load_borough_row(session, city, neighbourhood):
    df_borough = session.sql(f"""
        SELECT *
        FROM {DATABASE}.{GOLD_SCHEMA}.BOROUGH_SUMMARY
        WHERE CITY = '{city}'
        AND NEIGHBOURHOOD_CLEANSED = '{neighbourhood}'
        LIMIT 1
    """).to_pandas()
    df_borough.columns = df_borough.columns.str.lower()

    if len(df_borough) == 0:
        return None

    row = df_borough.iloc[0].to_dict()

    try:
        df_themes = session.sql(f"""
            SELECT NEIGHBOURHOOD_CLEANSED, TOP_THEME,
                   PCT_MENTIONS_PRICE, PCT_MENTIONS_LOCATION,
                   AVG_SENTIMENT_SCORE
            FROM {DATABASE}.{GOLD_SCHEMA}.REVIEW_THEMES
            WHERE CITY = '{city}'
            AND NEIGHBOURHOOD_CLEANSED = '{neighbourhood}'
            LIMIT 1
        """).to_pandas()
        df_themes.columns = df_themes.columns.str.lower()

        theme_cols = ['top_theme', 'pct_mentions_price',
                      'pct_mentions_location', 'avg_sentiment_score']
        if len(df_themes) > 0:
            for col in theme_cols:
                row[col] = df_themes.iloc[0].get(col)
        else:
            for col in theme_cols:
                row[col] = None
    except Exception:
        for col in ['top_theme', 'pct_mentions_price',
                    'pct_mentions_location', 'avg_sentiment_score']:
            row[col] = None

    return row


def load_property_bedroom_data(session, city, neighbourhood):
    df = session.sql(f"""
        SELECT
            p.NEIGHBOURHOOD,
            p.STRUCTURE_CLASS,
            p.LISTING_COUNT,
            ROUND(p.AVG_ADR, 2) AS avg_price,
            ROUND(p.AVG_OCCUPANCY_RATE * 100, 1) AS avg_occupancy,
            ROUND(p.AVG_ANNUAL_REVENUE, 2) AS avg_revenue,
            ROUND(p.AVG_RATING, 2) AS avg_rating,
            p.SUFFICIENT_SAMPLE AS sufficient_sample,
            p.BEDROOM_BUCKET AS bedroom_bucket,
            ROUND(j1.INVESTMENT_SCORE_YIELD, 2)
                AS avg_score_yield_maximiser,
            ROUND(j1.INVESTMENT_SCORE_OCCUPANCY, 2)
                AS avg_score_occupancy_optimiser,
            ROUND(j1.INVESTMENT_SCORE_QUALITY, 2)
                AS avg_score_quality_host
        FROM (
            SELECT
                CASE
                    WHEN a.BEDROOMS >= 4 THEN '4+'
                    WHEN a.BEDROOMS IN (1,2,3)
                        THEN CAST(a.BEDROOMS AS VARCHAR)
                END AS BEDROOM_BUCKET,
                a.NEIGHBOURHOOD,
                a.STRUCTURE_CLASS,
                b.CITY,
                AVG(b.SCORE_YIELD_MAXIMISER)
                    AS INVESTMENT_SCORE_YIELD,
                AVG(b.SCORE_OCCUPANCY_OPTIMISER)
                    AS INVESTMENT_SCORE_OCCUPANCY,
                AVG(b.SCORE_QUALITY_HOST)
                    AS INVESTMENT_SCORE_QUALITY
            FROM {DATABASE}.{GOLD_SCHEMA}.MART_LISTING_CANDIDATES a
            LEFT JOIN {DATABASE}.{GOLD_SCHEMA}.INVESTMENT_SCORES b
                ON a.LISTING_ID = b.LISTING_ID
            WHERE a.NEIGHBOURHOOD IS NOT NULL
            AND a.STRUCTURE_CLASS IS NOT NULL
            AND b.CITY IS NOT NULL
            GROUP BY
                b.CITY, a.NEIGHBOURHOOD, a.STRUCTURE_CLASS,
                CASE
                    WHEN a.BEDROOMS >= 4 THEN '4+'
                    WHEN a.BEDROOMS IN (1,2,3)
                        THEN CAST(a.BEDROOMS AS VARCHAR)
                END
        ) j1
        JOIN {DATABASE}.{GOLD_SCHEMA}.MART_BEDROOMS p
            ON p.NEIGHBOURHOOD = j1.NEIGHBOURHOOD
            AND p.STRUCTURE_CLASS = j1.STRUCTURE_CLASS
            AND p.CITY = j1.CITY
            AND p.BEDROOM_BUCKET = j1.BEDROOM_BUCKET
        WHERE p.NEIGHBOURHOOD IS NOT NULL
        AND p.STRUCTURE_CLASS IS NOT NULL
        AND LOWER(TRIM(p.STRUCTURE_CLASS)) != 'other / unknown'
        AND j1.CITY = '{city}'
        AND p.NEIGHBOURHOOD = '{neighbourhood}'
        ORDER BY p.STRUCTURE_CLASS, p.BEDROOM_BUCKET
    """).to_pandas()

    df.columns = df.columns.str.lower()
    df = df.rename(columns={'neighbourhood': 'neighbourhood_cleansed'})
    return df


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def build_recommendation_prompt(neighbourhood, persona_key,
                                 top_n, borough_row):
    persona   = PERSONAS[persona_key]
    score_col = persona['score_col']
    n         = len(top_n)

    top_n_text = ''
    for i, (_, row) in enumerate(top_n.iterrows()):
        disclaimer = ''
        count = int(row['listing_count'])
        if count < 3:
            disclaimer = ' WARNING: only 1-2 listings — treat with caution'
        elif count < 10:
            disclaimer = ' (limited sample — interpret carefully)'

        top_n_text += (
            f"{i+1}. {row['structure_class']}, "
            f"{row['bedroom_bucket']} bedroom(s) — "
            f"avg investment score "
            f"{round(float(row[score_col]), 1)}/100 "
            f"(based on {count} listings{disclaimer}), "
            f"avg nightly price £{row['avg_price']}, "
            f"avg occupancy {row['avg_occupancy']}%, "
            f"avg annual revenue £{row['avg_revenue']:,.0f}, "
            f"avg guest rating {row['avg_rating']}/5\n"
        )

    options_phrase = (
        f"the {n} available option{'s' if n != 1 else ''}"
    )

    if persona['label'] == 'Yield Maximiser':
        persona_rules = ('Focus ONLY on revenue, nightly '
                         'price, annual income and gross yield. '
                         'Do NOT use occupancy rate as a '
                         'primary metric.')
    elif persona['label'] == 'Occupancy Optimiser':
        persona_rules = ('Focus ONLY on occupancy rate, '
                         'booking consistency, vacancy risk '
                         'and booking flow. Do NOT mention '
                         'gross yield percentage.')
    else:
        persona_rules = ('Focus ONLY on guest ratings, review '
                         'scores, Superhost potential and guest '
                         'experience. Do NOT mention gross yield '
                         'percentage or revenue as primary metrics.')

    system_prompt = f"""You are an expert Airbnb investment analyst \
advising a {persona['label']} who prioritises {persona['focus']}.

The property options in the user message are already ranked \
from highest to lowest investment score for this persona, \
comparing {options_phrase}. \
You MUST set top_pick to the FIRST combination listed \
and second_pick to the SECOND combination listed. \
Never reorder this ranking.

Your role is to EXPLAIN why the pre-computed ranking makes \
sense for this persona. Do not create your own ranking.

PERSONA RULES: {persona_rules}

Property options are limited to Flat and House, each considered \
separately by bedroom count (1, 2, 3, 4+). Rank on the combination \
of structure type AND bedroom count together — a 2-bedroom Flat and \
a 3-bedroom Flat are different options, not the same one. The \
investment scores shown are averages across all listings of that \
structure type and bedroom count in this neighbourhood — not a \
single listing score. Be specific, reference actual numbers, and \
tailor your advice entirely to this persona's priorities. \
Do not mention other personas.

Respond with ONLY a valid JSON object, no other text:
{{
  "recommendation_summary": "2-3 sentence summary of which structure \
type and bedroom count combinations perform best in this neighbourhood \
for this persona and why, referencing actual scores and revenue figures",
  "top_pick": "MUST be the first structure type + bedroom count \
combination listed, e.g. 'House, 3 bedrooms' — copy it exactly, \
do not change",
  "top_pick_reason": "one specific sentence on why this combination \
ranks first, referencing avg score, revenue and number of listings \
it is based on",
  "second_pick": "the second structure type + bedroom count \
combination, exactly as listed, e.g. 'Flat, 2 bedrooms' — \
or null if only one combination is available",
  "second_pick_reason": "one sentence on second pick referencing \
actual numbers, otherwise null",
  "what_to_avoid": "combination to avoid and specific reason why \
based on the data",
}}"""

    user_prompt = f"""
Neighbourhood: {neighbourhood}
Persona: {persona['label']}
Overall neighbourhood investment score: {round(float(
    borough_row[f'score_{persona_key.lower()}']), 2)}/100

Property type + bedroom combinations ranked by average investment \
score ({n} available, each score is the mean across all listings \
of that combination in this neighbourhood):
{top_n_text}
Neighbourhood context:
Total listings: {int(borough_row['listing_count'])}
Avg nightly price: £{round(float(borough_row['avg_price']), 2)}
Avg occupancy: {round(float(borough_row['avg_occupancy']) / 365 * 100, 1)}%
Avg annual revenue: £{round(float(borough_row['avg_revenue']), 2):,.0f}
Avg review rating: {round(float(borough_row['avg_review_rating']), 2)}/5
Superhost percentage: {round(float(borough_row['pct_superhost']), 1)}%
Top review theme: {borough_row.get('top_theme') or 'N/A'}
Price mentions in reviews: {round(float(borough_row['pct_mentions_price']), 1) if pd.notna(borough_row.get('pct_mentions_price')) else 'N/A'}%
Location mentions in reviews: {round(float(borough_row['pct_mentions_location']), 1) if pd.notna(borough_row.get('pct_mentions_location')) else 'N/A'}%
Avg sentiment score: {round(float(borough_row['avg_sentiment_score']), 4) if pd.notna(borough_row.get('avg_sentiment_score')) else 'N/A'}
"""
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def call_gemini(api_key, system_prompt, user_prompt):
    client      = genai.Client(api_key=api_key)
    combined    = system_prompt + '\n\n' + user_prompt
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=combined
            )
            return response.text
        except Exception as e:
            if '429' in str(e) and attempt < max_retries - 1:
                time.sleep(15 * (attempt + 1))
            elif attempt < max_retries - 1:
                time.sleep(5)
            else:
                return None
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
        parsed     = json.loads(clean)
        confidence = parsed.get('confidence', 'medium')
        return clean, confidence
    except Exception:
        return ai_response, 'low' if ai_response else 'error'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_generate_recommendation(session, api_key,
                                    city, neighbourhood, persona):
    """
    Return a cached JSON narrative for the given city / neighbourhood /
    persona combination, generating and caching one on-demand if absent.
    PROMPT_VERSION is included in the cache key — bump it whenever prompt
    logic changes so stale cached narratives are never served silently.

    Returns a JSON string, or None if no property data exists for this
    neighbourhood or the Gemini call fails.

    Parameters
    ----------
    session        : Snowpark session (already open)
    api_key        : Google API key, e.g. from st.secrets
    city           : e.g. 'Bristol'
    neighbourhood  : e.g. 'Clifton'
    persona        : 'YIELD_MAXIMISER' | 'OCCUPANCY_OPTIMISER' |
                     'QUALITY_HOST'
    """
    # Step 1: Check cache (filters on PROMPT_VERSION)
    cached = check_cache(session, city, neighbourhood, persona)
    if cached:
        return cached

    # Step 2: Load borough context
    borough_row = load_borough_row(session, city, neighbourhood)
    if borough_row is None:
        return None

    # Step 3: Load property/bedroom combinations for this neighbourhood
    df_props = load_property_bedroom_data(session, city, neighbourhood)
    if len(df_props) == 0:
        return None

    # Step 4: Select up to 3 top combinations by persona score
    score_col = PERSONAS[persona]['score_col']
    top_n = df_props.nlargest(3, score_col).reset_index(drop=True)

    if len(top_n) == 0:
        return None

    # Step 5: Build prompt and call Gemini (works for 1, 2, or 3 combos)
    system_prompt, user_prompt = build_recommendation_prompt(
        neighbourhood, persona, top_n, borough_row
    )

    ai_response = call_gemini(api_key, system_prompt, user_prompt)
    if not ai_response:
        return None

    narrative, confidence = parse_response(ai_response)

    # Step 6: Store in cache
    investment_score = (
        round(float(borough_row[f'score_{persona.lower()}']), 2)
        if pd.notna(borough_row.get(f'score_{persona.lower()}'))
        else None
    )
    metrics_json = json.dumps({
        'top_property_group': top_n.iloc[0]['structure_class'],
        'top_bedroom_bucket': top_n.iloc[0]['bedroom_bucket'],
        'top_avg_score':      float(top_n.iloc[0][score_col]),
        'listing_count':      int(top_n.iloc[0]['listing_count']),
        'top_avg_revenue':    float(top_n.iloc[0]['avg_revenue']),
    })

    write_to_cache(
        session, city, neighbourhood, persona,
        narrative, investment_score, metrics_json, confidence
    )

    return narrative
