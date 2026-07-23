# Helper for the Property Types Comparison page: caches and generates
# persona-based ST-vs-LT + seasonality comparisons across 3 starred
# (neighbourhood, structure_class, bedroom_bucket) picks.
"""
property_types_comparison_helper.py
------------------------------------
Runs inside Streamlit-in-Snowflake via a Snowpark session.
Import and call get_or_generate_comparison() — all other functions
are internal.

Grain: exactly 3 user-picked (neighbourhood, structure_class,
bedroom_bucket) combinations, possibly spanning different starred
neighbourhoods. Cache key is order-independent across the 3 picks.

Investment scores are derived using the same join logic as Andrew's
frontend KPI query (MART_LISTING_CANDIDATES + INVESTMENT_SCORES,
CASE-bucketed bedrooms, explicit CITY join) — this must stay in sync
with property_type_helper.py's load_property_bedroom_data(). If that
join logic changes there, mirror the change here too.
"""

import json
from gemini import generate as _gemini_generate, DEFAULT_MODEL

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE       = 'AIRBNB_INVESTMENT_DB'
GOLD_SCHEMA    = 'GOLD'
CACHE_TABLE    = 'PROPERTY_TYPE_COMPARISON_CACHE'
PROMPT_VERSION = 'v1'

MONTH_TO_SEASON = {
    12: 'Winter', 1: 'Winter', 2: 'Winter',
    3:  'Spring', 4: 'Spring', 5: 'Spring',
    6:  'Summer', 7: 'Summer', 8: 'Summer',
    9:  'Autumn', 10: 'Autumn', 11: 'Autumn',
}

PERSONAS = {
    'YIELD_MAXIMISER': {
        'label': 'Yield Maximiser',
        'focus': (
            'maximising annual revenue and gross yield — which of '
            'these 3 combinations earns the most, and whether short-'
            'term or long-term letting wins for each'
        ),
    },
    'OCCUPANCY_OPTIMISER': {
        'label': 'Occupancy Optimiser',
        'focus': (
            'consistent high occupancy and booking demand — which '
            'combination books up most reliably across the year'
        ),
    },
    'QUALITY_HOST': {
        'label': 'Quality Host',
        'focus': (
            'guest experience and manageable, sustainable hosting — '
            'which combination supports the strongest guest ratings'
        ),
    },
}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def ensure_cache_table(session):
    """Creates PROPERTY_TYPE_COMPARISON_CACHE if it doesn't already
    exist. Safe to call on every request — CREATE TABLE IF NOT EXISTS
    is a no-op once the table is there. Cheap enough not to bother
    caching this check across calls."""
    try:
        session.sql(f"""
            CREATE TABLE IF NOT EXISTS {DATABASE}.{GOLD_SCHEMA}.{CACHE_TABLE} (
                CITY                VARCHAR,
                PROPERTY_TYPE_GROUP VARCHAR,
                PERSONA             VARCHAR,
                COMBO_COUNT         NUMBER(2,0),
                AI_NARRATIVE        VARCHAR,
                MODEL_USED          VARCHAR,
                PROMPT_VERSION      VARCHAR,
                COMPUTED_AT         TIMESTAMP_NTZ
            )
        """).collect()
    except Exception as e:
        # Don't block the page over a table-creation race/permissions
        # issue — surface it, but let the caller decide what to do.
        raise RuntimeError(f'Could not ensure cache table exists: {e}') from e


def make_cache_key(selections):
    """Sorted, comma-joined 'NEIGHBOURHOOD|STRUCTURE_CLASS|BEDROOM_BUCKET'
    strings — order-independent."""
    tuples = [
        f"{s['neighbourhood']}|{s['structure_class']}|{s['bedroom_bucket']}"
        for s in selections
    ]
    return ','.join(sorted(tuples))


def check_cache(session, city, combo_key, persona):
    try:
        result = session.sql(f"""
            SELECT AI_NARRATIVE
            FROM {DATABASE}.{GOLD_SCHEMA}.{CACHE_TABLE}
            WHERE CITY = '{city}'
            AND PROPERTY_TYPE_GROUP = '{combo_key}'
            AND PERSONA = '{persona}'
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


def write_to_cache(session, city, combo_key, persona, narrative,
                   combo_count, model_used):
    insert_sql = f"""
        INSERT INTO {DATABASE}.{GOLD_SCHEMA}.{CACHE_TABLE}
            (CITY, PROPERTY_TYPE_GROUP, PERSONA, COMBO_COUNT,
             AI_NARRATIVE, MODEL_USED, PROMPT_VERSION, COMPUTED_AT)
        SELECT ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ
    """
    params = [
        city, combo_key, persona, int(combo_count),
        narrative, model_used, PROMPT_VERSION,
    ]
    try:
        session.sql(insert_sql, params=params).collect()
    except Exception as e:
        raise RuntimeError(f'Cache write failed: {e}') from e


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _tuple_filter(selections):
    return ', '.join(
        f"('{s['neighbourhood']}', '{s['structure_class']}', "
        f"'{s['bedroom_bucket']}')"
        for s in selections
    )


def load_st_vs_lt(session, city, selections):
    """Direct match — MART_ST_VS_LT is already at
    (neighbourhood, structure_class, bedroom_bucket) grain, no
    aggregation needed."""
    tuple_list = _tuple_filter(selections)

    df = session.sql(f"""
        SELECT
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_BUCKET,
            LISTING_COUNT,
            ST_ANNUAL_INCOME,
            LT_ANNUAL_INCOME,
            ST_GROSS_YIELD_PCT,
            LT_GROSS_YIELD_PCT,
            ST_WINS,
            SUFFICIENT_SAMPLE
        FROM {DATABASE}.{GOLD_SCHEMA}.MART_ST_VS_LT
        WHERE CITY = '{city}'
        AND (NEIGHBOURHOOD, STRUCTURE_CLASS, BEDROOM_BUCKET)
            IN ({tuple_list})
    """).to_pandas()

    df.columns = df.columns.str.lower()
    return df


def load_seasonal_trend(session, city, selections):
    """Monthly occupancy per (neighbourhood, structure_class,
    bedroom_bucket), from MART_PROPERTY_SEASONAL."""
    tuple_list = _tuple_filter(selections)

    df = session.sql(f"""
        SELECT
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_BUCKET,
            MONTH,
            BOOKED_NIGHTS,
            TOTAL_NIGHTS
        FROM {DATABASE}.{GOLD_SCHEMA}.MART_PROPERTY_SEASONAL
        WHERE CITY = '{city}'
        AND (NEIGHBOURHOOD, STRUCTURE_CLASS, BEDROOM_BUCKET)
            IN ({tuple_list})
    """).to_pandas()

    df.columns = df.columns.str.lower()
    return df


def summarise_seasonality(seasonal_df):
    """Nights-weighted season averages per (neighbourhood,
    structure_class, bedroom_bucket) combo, plus peak/trough season."""
    if seasonal_df.empty:
        return {}

    seasonal_df = seasonal_df.copy()
    seasonal_df['season'] = seasonal_df['month'].map(MONTH_TO_SEASON)
    seasonal_df['combo_key'] = (
        seasonal_df['neighbourhood'] + '|' +
        seasonal_df['structure_class'] + '|' +
        seasonal_df['bedroom_bucket']
    )

    summary = {}
    for combo_key, group in seasonal_df.groupby('combo_key'):
        season_totals = group.groupby('season')[
            ['booked_nights', 'total_nights']
        ].sum()
        season_avg = {
            season: (row['booked_nights'] / row['total_nights']
                     if row['total_nights'] else 0.0)
            for season, row in season_totals.iterrows()
        }
        if season_avg:
            peak   = max(season_avg, key=season_avg.get)
            trough = min(season_avg, key=season_avg.get)
        else:
            peak, trough = None, None
        summary[combo_key] = {
            'season_avg': season_avg,
            'peak_season': peak,
            'trough_season': trough,
        }
    return summary


def load_investment_scores(session, city, selections):
    """Derived persona scores — MUST match Andrew's frontend join
    logic exactly (property_type_helper.py's
    load_property_bedroom_data uses the same query shape). Studios
    (0-bedroom) are dropped, not folded into '1', matching his CASE."""
    neighbourhoods = ', '.join(
        f"'{s['neighbourhood']}'" for s in selections
    )

    df = session.sql(f"""
        SELECT
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_BUCKET,
            AVG(SCORE_YIELD_MAXIMISER) AS avg_score_yield_maximiser,
            AVG(SCORE_OCCUPANCY_OPTIMISER) AS avg_score_occupancy_optimiser,
            AVG(SCORE_QUALITY_HOST) AS avg_score_quality_host
        FROM (
            SELECT
                a.NEIGHBOURHOOD,
                a.STRUCTURE_CLASS,
                CASE
                    WHEN a.BEDROOMS >= 4 THEN '4+'
                    WHEN a.BEDROOMS IN (1,2,3) THEN CAST(a.BEDROOMS AS VARCHAR)
                END AS BEDROOM_BUCKET,
                b.SCORE_YIELD_MAXIMISER,
                b.SCORE_OCCUPANCY_OPTIMISER,
                b.SCORE_QUALITY_HOST
            FROM {DATABASE}.{GOLD_SCHEMA}.MART_LISTING_CANDIDATES a
            LEFT JOIN {DATABASE}.{GOLD_SCHEMA}.INVESTMENT_SCORES b
                ON a.LISTING_ID = b.LISTING_ID
            WHERE a.NEIGHBOURHOOD IN ({neighbourhoods})
            AND a.STRUCTURE_CLASS IS NOT NULL
            AND b.CITY = '{city}'
        )
        WHERE BEDROOM_BUCKET IS NOT NULL
        GROUP BY NEIGHBOURHOOD, STRUCTURE_CLASS, BEDROOM_BUCKET
    """).to_pandas()

    df.columns = df.columns.str.lower()
    return df


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def format_combo_block(row, rank, scores_row, seasonality):
    combo_key = f"{row['neighbourhood']}|{row['structure_class']}|{row['bedroom_bucket']}"
    season_info = seasonality.get(combo_key, {})
    season_avg = season_info.get('season_avg', {})
    season_text = ', '.join(
        f"{season}: {rate * 100:.0f}%" for season, rate in season_avg.items()
    ) if season_avg else 'no seasonal data available'

    scores_text = 'no investment score data available'
    if scores_row is not None:
        scores_text = (
            f"Yield Maximiser score {scores_row['avg_score_yield_maximiser']:.1f}, "
            f"Occupancy Optimiser score {scores_row['avg_score_occupancy_optimiser']:.1f}, "
            f"Quality Host score {scores_row['avg_score_quality_host']:.1f}"
        )

    sample_flag = '' if row.get('sufficient_sample', True) else \
        ' — WARNING: small sample, interpret with caution'

    return (
        f"Option {rank}: {row['neighbourhood']}, {row['structure_class']}, "
        f"{row['bedroom_bucket']} bedroom(s){sample_flag}\n"
        f"  Listings sampled: {int(row['listing_count'])}\n"
        f"  Short-term annual income: £{float(row['st_annual_income']):,.0f}\n"
        f"  Long-term annual income: £{float(row['lt_annual_income']):,.0f}\n"
        f"  Short-term gross yield: {float(row['st_gross_yield_pct']):.1f}%\n"
        f"  Long-term gross yield: {float(row['lt_gross_yield_pct']):.1f}%\n"
        f"  Short-term wins on income: {'Yes' if row.get('st_wins') else 'No'}\n"
        f"  Seasonal occupancy by season: {season_text}\n"
        f"  Peak season: {season_info.get('peak_season', 'N/A')}, "
        f"Trough season: {season_info.get('trough_season', 'N/A')}\n"
        f"  Investment scores: {scores_text}"
    )


def build_prompt(city, selections, persona, st_lt_df, scores_df, seasonality):
    persona_info = PERSONAS[persona]

    blocks = []
    for i, (_, row) in enumerate(st_lt_df.iterrows()):
        match = scores_df[
            (scores_df['neighbourhood'] == row['neighbourhood']) &
            (scores_df['structure_class'] == row['structure_class']) &
            (scores_df['bedroom_bucket'] == row['bedroom_bucket'])
        ]
        scores_row = match.iloc[0] if len(match) > 0 else None
        blocks.append(format_combo_block(row, i + 1, scores_row, seasonality))
    combo_blocks = '\n\n'.join(blocks)

    system_prompt = f"""You are an expert Airbnb investment analyst \
advising a {persona_info['label']} who prioritises \
{persona_info['focus']}.

You are comparing exactly {len(selections)} specific combinations of \
neighbourhood, property type (Flat or House) and bedroom count in \
{city}, each showing short-term (ST) vs long-term (LT) rental \
income and yield, seasonal occupancy, and this persona's investment \
score.

CRITICAL PERSONA RULES:
- YIELD_MAXIMISER: rank primarily by whichever of ST or LT income is \
higher for each option, and by gross yield. State clearly whether ST \
or LT wins for each combination.
- OCCUPANCY_OPTIMISER: rank primarily by seasonal occupancy \
consistency — a combination with a smaller gap between its peak and \
trough season is more reliable than one with a bigger swing, even if \
its average is similar.
- QUALITY_HOST: rank primarily by the persona's own investment \
score, which already weights guest rating heavily.

MANDATORY CROSS-REFERENCE RULE: never state a seasonal or ST-vs-LT \
fact in isolation — always connect it back to what actually matters \
for this persona, explicitly. If a combination has high ST income \
but ST does not actually win over LT, or if occupancy is high in \
one season but low elsewhere, say what that means for this persona's \
decision, not just what the numbers are.

The investment score is fixed and must not be contradicted — if a \
lower-scoring option looks appealing on one metric, name that as a \
trade-off rather than declaring it the overall best.

Respond with ONLY a valid JSON object, no other text:
{{
  "comparison_summary": "2-3 sentences comparing the options for a \
{persona_info['label']}, leading with their primary metric and \
referencing actual numbers.",
  "best_combination": "state the winner as 'neighbourhood, property \
type, bedroom count' exactly, e.g. 'Lambeth, Flat, 2 bedroom'",
  "best_combination_reason": "one sentence why, with specific \
numbers, matching this persona's investment score ranking",
  "st_vs_lt_insight": "one sentence stating which combinations \
favour short-term vs long-term letting and why, for this persona",
  "seasonality_verdict": "one sentence naming peak/trough seasons \
for the relevant combination(s), then judging whether that pattern \
actually helps or hurts this persona specifically",
  "what_to_avoid": "one specific risk among these options for this \
persona, e.g. a small sample size or a combination where ST loses \
to LT despite looking attractive on the surface"
}}"""

    selections_text = ', '.join(
        f"{s['neighbourhood']}/{s['structure_class']}/"
        f"{s['bedroom_bucket']}bed"
        for s in selections
    )

    user_prompt = f"""
City: {city}
Persona: {persona_info['label']}
Combinations compared: {selections_text}

COMBINATION DATA:
{combo_blocks}
"""
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def call_gemini(api_key, system_prompt, user_prompt):
    combined = system_prompt + '\n\n' + user_prompt
    try:
        return _gemini_generate(combined, api_key=api_key), DEFAULT_MODEL
    except Exception:
        return None, DEFAULT_MODEL


def parse_response(ai_response):
    try:
        clean = ai_response.strip() if ai_response else None
        if clean and clean.startswith('```'):
            parts = clean.split('```')
            clean = parts[1]
            if clean.startswith('json'):
                clean = clean[4:]
            clean = clean.strip()
        json.loads(clean)
        return clean
    except Exception:
        return ai_response


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_or_generate_comparison(session, api_key, city, selections, persona):
    """
    selections : list of exactly 3 dicts, each:
                 {'neighbourhood': 'Lambeth', 'structure_class': 'Flat',
                  'bedroom_bucket': '2'}
    persona    : 'YIELD_MAXIMISER' | 'OCCUPANCY_OPTIMISER' | 'QUALITY_HOST'
    """
    if not selections or len(selections) != 3:
        return None

    ensure_cache_table(session)

    combo_key = make_cache_key(selections)

    cached = check_cache(session, city, combo_key, persona)
    if cached:
        return cached

    st_lt_df = load_st_vs_lt(session, city, selections)
    if len(st_lt_df) < len(selections):
        return None

    scores_df   = load_investment_scores(session, city, selections)
    seasonal_df = load_seasonal_trend(session, city, selections)
    seasonality = summarise_seasonality(seasonal_df)

    system_prompt, user_prompt = build_prompt(
        city, selections, persona, st_lt_df, scores_df, seasonality
    )

    ai_response, model_used = call_gemini(api_key, system_prompt, user_prompt)
    if not ai_response:
        return None

    narrative = parse_response(ai_response)

    try:
        write_to_cache(
            session, city, combo_key, persona,
            narrative, len(selections), model_used
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(str(e))

    return narrative
