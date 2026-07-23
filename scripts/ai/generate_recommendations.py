"""
Generate AI Recommendation Summaries — Local Script
----------------------------------------------------
Reads borough summary, review theme, and investment score
data from Snowflake Gold tables, calls the Gemini API to
generate structured property-type recommendation summaries
per neighbourhood × persona, and appends results to
GOLD.AI_OUTPUTS (output_type = 'RECOMMENDATION').

Install dependencies before running:
    pip install snowflake-connector-python google-genai pandas

Required environment variables:
    SNOWFLAKE_USER
    SNOWFLAKE_PASSWORD
    SNOWFLAKE_ACCOUNT
    SNOWFLAKE_WAREHOUSE  (optional, defaults to COMPUTE_WH)
    GOOGLE_API_KEY

Run:
    python scripts/ai/generate_recommendations.py
"""

import os
import sys
import json
import time
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from google import genai

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE       = 'AIRBNB_INVESTMENT_DB'
SILVER_SCHEMA  = 'SILVER'
GOLD_SCHEMA    = 'GOLD'
OUTPUT_TABLE   = 'AI_OUTPUTS'
MODEL          = 'gemini-3.1-flash-lite'
OUTPUT_TYPE    = 'RECOMMENDATION'
PROMPT_VERSION = 'v1'
# 'resume' — skip already generated rows, fill gaps only
# 'full'   — delete existing RECOMMENDATION rows for all cities and regenerate from scratch
#             Use 'full' when prompt logic has changed
RUN_MODE       = 'full'
DRY_RUN        = False  # True = count combos and exit; False = run normally

# CITIES = ['Bristol', 'London', 'Greater Manchester']
CITIES = ['Bristol']
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
# 0. Connections
# ---------------------------------------------------------------------------

def get_snowflake_connection():
    return snowflake.connector.connect(
        user=os.environ['SNOWFLAKE_USER'],
        password=os.environ['SNOWFLAKE_PASSWORD'],
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH'),
        database=DATABASE,
        schema=GOLD_SCHEMA
    )


def get_gemini_client():
    return genai.Client(api_key=os.environ['GOOGLE_API_KEY'])


def clear_existing_recommendations(conn, cities):
    city_list = ', '.join([f"'{c}'" for c in cities])
    conn.cursor().execute(f"""
        DELETE FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS
        WHERE "output_type" = 'RECOMMENDATION'
        AND "city" IN ({city_list})
    """)
    print(f'Cleared existing RECOMMENDATION rows '
          f'for: {", ".join(cities)}')


def load_existing_recommendations(conn, city):
    try:
        df = pd.read_sql(f"""
            SELECT "neighbourhood_cleansed", "persona"
            FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS
            WHERE "city" = '{city}'
            AND "output_type" = 'RECOMMENDATION'
            AND "ai_narrative" IS NOT NULL
        """, conn)
        print(f'  Found {len(df)} existing RECOMMENDATION '
              f'rows for {city} — will skip these')
        return df
    except Exception:
        return pd.DataFrame(
            columns=['neighbourhood_cleansed', 'persona']
        )


# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------

def load_borough_data(conn, city):
    cur = conn.cursor()

    # SELECT * avoids column-identifier case issues from Snowpark write_pandas;
    # normalise to lowercase and filter/join in Python.
    cur.execute('SELECT * FROM AIRBNB_INVESTMENT_DB.GOLD.BOROUGH_SUMMARY')
    df_borough = cur.fetch_pandas_all()
    df_borough.columns = df_borough.columns.str.lower()
    df_borough = df_borough[df_borough['city'] == city]

    cur.execute('SELECT * FROM AIRBNB_INVESTMENT_DB.GOLD.REVIEW_THEMES')
    df_themes = cur.fetch_pandas_all()
    df_themes.columns = df_themes.columns.str.lower()
    df_themes = df_themes[df_themes['city'] == city][[
        'neighbourhood_cleansed', 'top_theme',
        'pct_mentions_price', 'pct_mentions_location',
        'avg_sentiment_score',
    ]]

    df = df_borough.merge(df_themes, on='neighbourhood_cleansed', how='left')
    print(f'Loaded {len(df)} neighbourhoods for {city}')
    return df


def load_property_bedroom_data(conn, city):
    df = pd.read_sql(f"""
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
            FROM AIRBNB_INVESTMENT_DB.GOLD.MART_LISTING_CANDIDATES a
            LEFT JOIN AIRBNB_INVESTMENT_DB.GOLD.INVESTMENT_SCORES b
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
        JOIN AIRBNB_INVESTMENT_DB.GOLD.MART_BEDROOMS p
            ON p.NEIGHBOURHOOD = j1.NEIGHBOURHOOD
            AND p.STRUCTURE_CLASS = j1.STRUCTURE_CLASS
            AND p.CITY = j1.CITY
            AND p.BEDROOM_BUCKET = j1.BEDROOM_BUCKET
        WHERE p.NEIGHBOURHOOD IS NOT NULL
        AND p.STRUCTURE_CLASS IS NOT NULL
        AND LOWER(TRIM(p.STRUCTURE_CLASS)) != 'other / unknown'
        AND j1.CITY = '{city}'
        ORDER BY p.NEIGHBOURHOOD, p.STRUCTURE_CLASS, p.BEDROOM_BUCKET
    """, conn)

    df.columns = df.columns.str.lower()
    df = df.rename(columns={'neighbourhood': 'neighbourhood_cleansed'})

    print(f'Loaded property/bedroom data: '
          f'{len(df)} neighbourhood x structure x bedroom '
          f'combinations for {city}')
    return df


def load_strategy_data(conn, city):
    df_strategy = pd.read_sql(f"""
        SELECT * FROM AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_STRATEGY
        WHERE UPPER(CITY) = UPPER('{city}')
        AND STRUCTURE_CLASS != 'Other'
        AND YIELD_COMPARABLE = TRUE
    """, conn)
    df_strategy.columns = df_strategy.columns.str.lower()

    df_bedrooms = pd.read_sql(f"""
        SELECT * FROM
        AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_STRATEGY_BEDROOMS
        WHERE UPPER(CITY) = UPPER('{city}')
        AND STRUCTURE_CLASS != 'Other'
        AND YIELD_COMPARABLE = TRUE
        AND LISTING_COUNT >= 3
        ORDER BY NEIGHBOURHOOD, STRUCTURE_CLASS, BEDROOM_SORT
    """, conn)
    df_bedrooms.columns = df_bedrooms.columns.str.lower()

    if 'neighbourhood' in df_bedrooms.columns:
        df_bedrooms = df_bedrooms.rename(
            columns={'neighbourhood': 'neighbourhood_cleansed'}
        )

    print(f'Loaded strategy data: {len(df_strategy)} area '
          f'strategy rows, {len(df_bedrooms)} bedroom '
          f'strategy rows for {city}')
    return df_strategy, df_bedrooms


# ---------------------------------------------------------------------------
# 2. Prompt builder
# ---------------------------------------------------------------------------

def build_recommendation_prompt(neighbourhood, persona_key,
                                 top_3, borough_row):
    persona   = PERSONAS[persona_key]
    score_col = persona['score_col']

    top_3_text = ''
    for i, (_, row) in enumerate(top_3.iterrows()):
        disclaimer = ''
        count = int(row['listing_count'])
        if count < 3:
            disclaimer = ' WARNING: only 1-2 listings — treat with caution'
        elif count < 10:
            disclaimer = ' (limited sample — interpret carefully)'

        top_3_text += (
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
from highest to lowest investment score for this persona. \
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
  "second_pick": "MUST be the second structure type + bedroom count \
combination listed exactly, e.g. 'Flat, 2 bedrooms', or null if \
only one combination is available",
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

Property types ranked by average investment score
(each score is the mean across all listings of that type
in this neighbourhood):
{top_3_text}

Neighbourhood context:
Total listings: {int(borough_row['listing_count'])}
Avg nightly price: £{round(float(borough_row['avg_price']), 2)}
Avg occupancy: {round(float(borough_row['avg_occupancy']) / 365 * 100, 1)}%
Avg annual revenue: £{round(float(borough_row['avg_revenue']), 2):,.0f}
Avg review rating: {round(float(borough_row['avg_review_rating']), 2)}/5
Superhost percentage: {round(float(borough_row['pct_superhost']), 1)}%
Top review theme: {borough_row['top_theme'] if pd.notna(borough_row.get('top_theme')) else 'N/A'}
Price mentions in reviews: {round(float(borough_row['pct_mentions_price']), 1) if pd.notna(borough_row.get('pct_mentions_price')) else 'N/A'}%
Location mentions in reviews: {round(float(borough_row['pct_mentions_location']), 1) if pd.notna(borough_row.get('pct_mentions_location')) else 'N/A'}%
Avg sentiment score: {round(float(borough_row['avg_sentiment_score']), 4) if pd.notna(borough_row.get('avg_sentiment_score')) else 'N/A'}
"""
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# 3. Gemini API call
# ---------------------------------------------------------------------------



def call_gemini(client, system_prompt, user_prompt):
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
                wait_time = 15 * (attempt + 1)
                print(f'    Rate limit — waiting {wait_time}s '
                      f'before retry {attempt + 1}/{max_retries}')
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f'    Error — waiting 5s before retry '
                      f'{attempt + 1}/{max_retries}: {e}')
                time.sleep(5)
            else:
                print(f'    Gemini API error: {e}')
                return None
    return None


# ---------------------------------------------------------------------------
# 4. Parse response
# ---------------------------------------------------------------------------

def parse_response(ai_response):
    try:
        clean_response = ai_response
        if ai_response:
            clean_response = ai_response.strip()
            if clean_response.startswith('```'):
                parts = clean_response.split('```')
                clean_response = parts[1]
                if clean_response.startswith('json'):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()
        parsed     = json.loads(clean_response)
        confidence = parsed.get('confidence', 'medium')
        return clean_response, confidence
    except (json.JSONDecodeError, TypeError):
        return ai_response, 'low' if ai_response else 'error'
    except Exception as e:
        print(f'    Unexpected parsing error: {e}')
        return ai_response, 'error'


# ---------------------------------------------------------------------------
# 5. Generate
# ---------------------------------------------------------------------------

def generate_recommendations(conn, client, city,
                              df_borough, df_property):
    rows = []

    if RUN_MODE == 'resume':
        existing = load_existing_recommendations(conn, city)
    else:
        existing = pd.DataFrame(
            columns=['neighbourhood_cleansed', 'persona']
        )
    neighbourhood_count = 0
    for _, borough_row in df_borough.iterrows():
        if neighbourhood_count >= 1:
            break
        neighbourhood_count += 1
        neighbourhood = borough_row['neighbourhood_cleansed']

        neighbourhood_props = df_property[
            df_property['neighbourhood_cleansed'] == neighbourhood
        ].copy()

        if len(neighbourhood_props) == 0:
            print(f'  Skipping {neighbourhood} — '
                  f'no property type data')
            continue

        for persona_key, persona in PERSONAS.items():
            score_col = persona['score_col']

            if len(existing) > 0:
                already_done = existing[
                    (existing['neighbourhood_cleansed']
                     == neighbourhood) &
                    (existing['persona'] == persona_key)
                ]
                if len(already_done) > 0:
                    print(f'  {neighbourhood} / {persona_key} '
                          f'— skipping, already generated')
                    continue

            top_3 = neighbourhood_props.nlargest(
                3, score_col
            ).reset_index(drop=True)

            if len(top_3) == 0:
                continue

            system_prompt, user_prompt = build_recommendation_prompt(
                neighbourhood, persona_key, top_3, borough_row
            )
            print(user_prompt)
            ai_response = call_gemini(client, system_prompt, user_prompt)

            clean_response, confidence = parse_response(ai_response)

            rows.append({
                'city':                   city,
                'neighbourhood_cleansed': neighbourhood,
                'persona':                persona_key,
                'output_type':            OUTPUT_TYPE,
                'investment_score':       round(float(
                    borough_row[f'score_{persona_key.lower()}']), 2)
                    if pd.notna(borough_row.get(
                        f'score_{persona_key.lower()}')) else None,
                'ai_narrative':           clean_response,
                'confidence':             confidence,
                'metrics_json':           json.dumps({
                    'top_property_group':  top_3.iloc[0]['structure_class'],
                    'top_bedroom_bucket':  top_3.iloc[0]['bedroom_bucket'],
                    'top_avg_score':       float(top_3.iloc[0][score_col]),
                    'listing_count':       int(top_3.iloc[0]['listing_count']),
                    'top_avg_revenue':     float(top_3.iloc[0]['avg_revenue']),
                }),
                'prompt_version':         PROMPT_VERSION,
                'model_used':             MODEL,
                'computed_at':            pd.Timestamp.now(),
            })

            print(f'  {neighbourhood} / {persona_key} '
                  f'/ RECOMMENDATION — done')
            time.sleep(4)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 6. Write
# ---------------------------------------------------------------------------

def write_to_snowflake(conn, df):
    if len(df) == 0:
        print('  No new rows to write.')
        return
    write_pandas(
        conn,
        df,
        OUTPUT_TABLE,
        database=DATABASE,
        schema=GOLD_SCHEMA,
        overwrite=False,
        auto_create_table=True
    )
    print(f'Written {len(df)} rows to '
          f'{GOLD_SCHEMA}.{OUTPUT_TABLE}')


# ---------------------------------------------------------------------------
# 7. Validate
# ---------------------------------------------------------------------------

def validate(conn):
    cur = conn.cursor()
    cur.execute('SELECT * FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS')
    df = cur.fetch_pandas_all()
    df.columns = df.columns.str.lower()
    df = df[df['output_type'] == 'RECOMMENDATION']
    df_val = (
        df.groupby(['city', 'persona', 'output_type'])
        .agg(
            total=('city', 'count'),
            with_narrative=('ai_narrative', lambda x: x.notna().sum()),
            high_confidence=('confidence', lambda x: (x == 'high').sum()),
            medium_confidence=('confidence', lambda x: (x == 'medium').sum()),
            low_confidence=('confidence', lambda x: (x == 'low').sum()),
            errors=('confidence', lambda x: (x == 'error').sum()),
        )
        .reset_index()
        .sort_values(['city', 'persona'])
    )
    print(df_val.to_string(index=False))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print('Initialising connections...')
    conn   = get_snowflake_connection()
    client = get_gemini_client()
    print('Connections established.')
    print(f'Run mode: {RUN_MODE}')

    if DRY_RUN:
        print('DRY RUN — counting (neighbourhood x persona) '
              'combinations only')
        grand_total = 0
        for city in CITIES:
            df_borough  = load_borough_data(conn, city)
            df_property = load_property_bedroom_data(conn, city)
            city_count  = 0
            for _, borough_row in df_borough.iterrows():
                neighbourhood = borough_row['neighbourhood_cleansed']
                neighbourhood_props = df_property[
                    df_property['neighbourhood_cleansed'] == neighbourhood
                ]
                if len(neighbourhood_props) > 0:
                    city_count += len(PERSONAS)
            print(f'  {city}: {city_count} combinations')
            grand_total += city_count
        print(f'Total across all cities: {grand_total}')
        conn.close()
        sys.exit(0)

    if RUN_MODE == 'full':
        clear_existing_recommendations(conn, CITIES)

    for city in CITIES:
        print(f'\nProcessing {city}...')
        df_borough              = load_borough_data(conn, city)
        df_property             = load_property_bedroom_data(conn, city)
        df_recs = generate_recommendations(
            conn, client, city, df_borough, df_property
        )
        write_to_snowflake(conn, df_recs)
        print(f'{city} complete — {len(df_recs)} rows written.')

    validate(conn)
    conn.close()
    print('Done. Recommendation summaries generated '
          'for all cities.')
