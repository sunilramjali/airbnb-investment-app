# Helper for the Area Comparison page: caches and generates persona-based ST-vs-LT + seasonal neighbourhood comparisons via the shared Gemini gateway.
# Co-authored with CoCo
"""
area_comparison_helper.py
--------------------------
Helper module for the Area Comparison page's "starred neighbourhoods"
ST vs LT comparison feature. Import and call
get_or_generate_comparison() — all other functions are internal.

Runs inside Snowflake Streamlit (Snowpark session).
Does NOT use snowflake.connector, streamlit, or a main block.

Scope: ST-vs-LT strategy + seasonal occupancy trend, aggregated
across all property structures per neighbourhood (matching the
Area Comparison page, which is not structure-segmented). The
ST vs LT figures use the same listing-count-weighted aggregation
the page uses. Season averages are nights-weighted
(sum(booked_nights) / sum(total_nights)) rather than a plain mean of
monthly OCCUPANCY_RATE.
"""

import json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE       = 'AIRBNB_INVESTMENT_DB'
GOLD_SCHEMA    = 'GOLD'
CACHE_TABLE    = 'ST_VS_LT_COMPARISON_CACHE'
MODEL          = 'gemini-3.1-flash-lite'
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
            'maximising total annual income — comparing short-term '
            '(Airbnb) revenue against long-term rental income to '
            'find the higher-earning strategy per neighbourhood'
        ),
    },
    'OCCUPANCY_OPTIMISER': {
        'label': 'Occupancy Optimiser',
        'focus': (
            'stable, predictable booking demand — weighing short-term '
            'occupancy resilience across seasons against the '
            'guaranteed, flat occupancy of a long-term let'
        ),
    },
    'QUALITY_HOST': {
        'label': 'Quality Host',
        'focus': (
            'a sustainable, manageable hosting strategy — whether the '
            'short-term strategy is viable without excessive seasonal '
            'turnover, or whether a long-term let is the lower-effort, '
            'guest-experience-friendly choice'
        ),
    },
}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def make_cache_key(neighbourhoods):
    """Sorted, comma-joined neighbourhood names, e.g. 'Ashley,Clifton,Redland'."""
    return ','.join(sorted(n.strip() for n in neighbourhoods))


def check_cache(session, city, neighbourhood_group, persona):
    try:
        result = session.sql(f"""
            SELECT AI_NARRATIVE
            FROM {DATABASE}.{GOLD_SCHEMA}.{CACHE_TABLE}
            WHERE CITY = '{city}'
            AND NEIGHBOURHOOD_GROUP = '{neighbourhood_group}'
            AND PERSONA = '{persona}'
            LIMIT 1
        """).to_pandas()

        if len(result) > 0:
            val = result.iloc[0]['AI_NARRATIVE']
            if val and str(val).strip():
                return str(val)
        return None
    except Exception:
        return None


def write_to_cache(session, city, neighbourhood_group, persona,
                   narrative, neighbourhood_count):
    # Parameterized INSERT (bind variables) — needs only INSERT privilege on the
    # pre-created table, avoiding the CREATE TABLE / temp-stage rights that
    # write_pandas requires. Binds also make the JSON narrative injection-safe.
    insert_sql = f"""
        INSERT INTO {DATABASE}.{GOLD_SCHEMA}.{CACHE_TABLE}
            (CITY, NEIGHBOURHOOD_GROUP, PERSONA,
             NEIGHBOURHOOD_COUNT, AI_NARRATIVE,
             MODEL_USED, PROMPT_VERSION, COMPUTED_AT)
        SELECT ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ
    """
    params = [
        city, neighbourhood_group, persona,
        int(neighbourhood_count), narrative,
        MODEL, PROMPT_VERSION,
    ]

    try:
        session.sql(insert_sql, params=params).collect()
    except Exception as e:
        # Surface, don't swallow: a silent failure here is why the cache
        # never populated. Caller can log/handle it.
        raise RuntimeError(f'Cache write failed: {e}') from e


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_area_strategy(session, city, neighbourhoods):
    """Headline ST vs LT row per neighbourhood, aggregated across all
    property structures. Uses the same listing-count-weighted math as
    the Area Comparison page so the AI summary matches the on-page charts."""
    quoted = ','.join(f"'{n}'" for n in neighbourhoods)

    df = session.sql(f"""
        SELECT
            NEIGHBOURHOOD,
            SUM(LISTING_COUNT) AS LISTING_COUNT,
            SUM(ST_ANNUAL_INCOME * LISTING_COUNT)
                / NULLIF(SUM(LISTING_COUNT), 0) AS ST_ANNUAL_REVENUE,
            SUM(LT_ANNUAL_INCOME * LISTING_COUNT)
                / NULLIF(SUM(LISTING_COUNT), 0) AS LT_ANNUAL_RENT,
            SUM(ST_GROSS_YIELD_PCT * LISTING_COUNT)
                / NULLIF(SUM(LISTING_COUNT), 0) AS ST_GROSS_YIELD_PCT,
            SUM(LT_GROSS_YIELD_PCT * LISTING_COUNT)
                / NULLIF(SUM(LISTING_COUNT), 0) AS LT_GROSS_YIELD_PCT
        FROM {DATABASE}.{GOLD_SCHEMA}.MART_ST_VS_LT
        WHERE CITY = '{city}'
        AND NEIGHBOURHOOD IN ({quoted})
        AND SUFFICIENT_SAMPLE = TRUE
        AND ST_ANNUAL_INCOME IS NOT NULL
        AND LT_ANNUAL_INCOME IS NOT NULL
        AND LISTING_COUNT > 0
        GROUP BY NEIGHBOURHOOD
    """).to_pandas()

    df.columns = df.columns.str.lower()
    return df


def load_area_seasonal(session, city, neighbourhoods):
    """Monthly occupancy per neighbourhood, from MART_AREA_SEASONAL.
    No STRUCTURE_CLASS on this table — seasonality is neighbourhood-level,
    aggregated across property types."""
    quoted = ','.join(f"'{n}'" for n in neighbourhoods)

    df = session.sql(f"""
        SELECT
            NEIGHBOURHOOD,
            MONTH,
            LISTING_COUNT,
            BOOKED_NIGHTS,
            TOTAL_NIGHTS,
            OCCUPANCY_RATE
        FROM {DATABASE}.{GOLD_SCHEMA}.MART_AREA_SEASONAL
        WHERE CITY = '{city}'
        AND NEIGHBOURHOOD IN ({quoted})
    """).to_pandas()

    df.columns = df.columns.str.lower()
    return df


def summarise_seasonality(seasonal_df):
    """Collapse monthly occupancy into per-neighbourhood season averages
    (Winter/Spring/Summer/Autumn), plus peak and trough season.

    Uses a nights-weighted average (sum(booked_nights) / sum(total_nights))
    rather than a plain mean of monthly rates, so months with more nights
    sampled aren't diluted by thinner months."""
    if seasonal_df.empty:
        return {}

    seasonal_df = seasonal_df.copy()
    seasonal_df['season'] = seasonal_df['month'].map(MONTH_TO_SEASON)

    summary = {}
    for neighbourhood, group in seasonal_df.groupby('neighbourhood'):
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

        summary[neighbourhood] = {
            'season_avg': season_avg,
            'peak_season': peak,
            'trough_season': trough,
        }

    return summary


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def format_area_block(row, seasonality):
    seasonal_info = seasonality.get(row['neighbourhood'], {})
    season_avg = seasonal_info.get('season_avg', {})

    season_text = ', '.join(
        f"{season}: {rate * 100:.0f}%"
        for season, rate in season_avg.items()
    ) if season_avg else 'No seasonal data available'

    return (
        f"Neighbourhood: {row['neighbourhood']}\n"
        f"  Short-term annual revenue: "
        f"£{float(row['st_annual_revenue']):,.0f}\n"
        f"  Short-term gross yield: "
        f"{float(row['st_gross_yield_pct']):.1f}%\n"
        f"  Long-term annual rent: "
        f"£{float(row['lt_annual_rent']):,.0f}\n"
        f"  Long-term gross yield: "
        f"{float(row['lt_gross_yield_pct']):.1f}%\n"
        f"  Active listings sampled: {int(row['listing_count'])}\n"
        f"  Seasonal occupancy by season: {season_text}\n"
        f"  Peak season: {seasonal_info.get('peak_season', 'N/A')}, "
        f"Trough season: {seasonal_info.get('trough_season', 'N/A')}"
    )


def build_prompt(city, neighbourhoods, persona, area_df, seasonality):
    persona_info = PERSONAS[persona]

    area_blocks = '\n\n'.join([
        format_area_block(row, seasonality)
        for _, row in area_df.iterrows()
    ])

    system_prompt = f"""You are an expert property investment analyst \
advising a {persona_info['label']} who prioritises \
{persona_info['focus']}.

You are comparing short-term (Airbnb) versus long-term rental \
strategy across {len(neighbourhoods)} neighbourhoods in {city} \
(across all property types): {', '.join(neighbourhoods)}.

CRITICAL PERSONA RULES:
- YIELD_MAXIMISER: lead with the ST vs LT annual income and gross \
yield gap in cash terms. State plainly which strategy wins in each \
neighbourhood and by how much.
- OCCUPANCY_OPTIMISER: lead with seasonal occupancy stability. \
Treat a long-term let's flat, guaranteed occupancy as the benchmark \
against short-term seasonal swings. Name peak and trough seasons.
- QUALITY_HOST: lead with operational sustainability — how much \
seasonal turnover the short-term strategy implies, and whether \
that trade-off is worth it versus the lower-effort long-term option.

Interpret seasonal occupancy data in terms of seasons (Winter, \
Spring, Summer, Autumn), not individual months — never name an \
individual month.

MANDATORY CROSS-REFERENCE RULE: never report seasonal occupancy \
as a standalone fact. Always run it back through the persona's \
primary metric and state a verdict. High occupancy in a season is \
only good news for this persona if it also supports what they \
actually care about — otherwise say so plainly.
Example for a Yield Maximiser: "Occupancy peaks in Summer, but \
short-term annual revenue here is still below the long-term rent, \
so this is not the area for a quick-yield strategy despite the \
strong occupancy."
Example for an Occupancy Optimiser: "Occupancy stays above 80% \
even in the Winter trough, meaning the short-term strategy holds \
up better here than the seasonal swing elsewhere would suggest."
Apply the same logic style to whichever persona is selected.

Respond with ONLY a valid JSON object, no other text:
{{
  "comparison_summary": "2-3 sentences comparing ST vs LT strategy \
across these neighbourhoods specifically for a \
{persona_info['label']}. Lead with the persona's primary concern. \
Reference actual yield and revenue numbers.",
  "best_neighbourhood": "name of the neighbourhood that best suits \
this persona's strategy, and which strategy (ST or LT) wins there",
  "best_neighbourhood_reason": "one sentence on exactly why, using \
specific numbers",
  "key_differentiator": "the single most important factor that \
separates these neighbourhoods for this persona's ST vs LT decision",
  "seasonality_verdict": "one sentence naming the peak and trough \
seasons for the relevant neighbourhood(s), then explicitly judging \
whether that seasonal pattern actually serves this persona's \
primary metric — following the mandatory cross-reference rule \
above, with numbers",
  "what_to_avoid": "one specific risk or red flag a \
{persona_info['label']} should watch for when choosing between \
these neighbourhoods"
}}"""

    user_prompt = f"""
City: {city}
Persona: {persona_info['label']}
Neighbourhoods compared: {', '.join(neighbourhoods)}

AREA-LEVEL ST VS LT DATA (all property types):
{area_blocks}
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

def get_or_generate_comparison(session, api_key, city, neighbourhoods,
                                persona):
    """
    Check cache for an existing ST vs LT comparison narrative across up
    to 3 starred neighbourhoods; generate and cache one if absent.
    Returns a JSON string or None if data is insufficient.

    Parameters
    ----------
    session         : Snowpark session (already open)
    api_key         : Google API key, e.g. from st.secrets
    city            : e.g. 'Bristol'
    neighbourhoods  : list of 2-3 starred neighbourhood names,
                      e.g. ['Ashley', 'Clifton', 'Redland']
    persona         : 'YIELD_MAXIMISER' | 'OCCUPANCY_OPTIMISER' |
                      'QUALITY_HOST'
    """
    if not neighbourhoods or len(neighbourhoods) < 2:
        return None

    neighbourhood_group = make_cache_key(neighbourhoods)

    # Step 1: Check cache
    cached = check_cache(session, city, neighbourhood_group, persona)
    if cached:
        return cached

    # Step 2: Load area-level ST vs LT data (all structures aggregated)
    area_df = load_area_strategy(session, city, neighbourhoods)

    # Need a row for every starred neighbourhood for a fair comparison
    if len(area_df) < len(neighbourhoods):
        return None

    # Step 3: Load seasonal data
    seasonal_df = load_area_seasonal(session, city, neighbourhoods)
    seasonality = summarise_seasonality(seasonal_df)

    # Step 4: Build prompt and call Gemini
    system_prompt, user_prompt = build_prompt(
        city, neighbourhoods, persona, area_df, seasonality
    )

    ai_response = call_gemini(api_key, system_prompt, user_prompt)

    if not ai_response:
        return None

    narrative = parse_response(ai_response)

    # Step 5: Store in cache. A cache-write failure must not break the page —
    # the narrative is already generated — so log and continue.
    try:
        write_to_cache(
            session, city, neighbourhood_group, persona,
            narrative, len(neighbourhoods)
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(str(e))

    # Step 6: Return narrative
    return narrative
