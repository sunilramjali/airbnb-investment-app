"""
Generate AI Investment Narratives — Local Script
-------------------------------------------------
Reads borough summary and review theme data from Snowflake Gold tables,
calls the Anthropic API to generate structured investment narratives per
neighbourhood × persona, and writes results back to GOLD.AI_OUTPUTS.

Install dependencies before running:
    pip install snowflake-connector-python anthropic pandas

Required environment variables:
    SNOWFLAKE_USER
    SNOWFLAKE_PASSWORD
    SNOWFLAKE_ACCOUNT
    SNOWFLAKE_WAREHOUSE  (optional, defaults to COMPUTE_WH)
    GOOGLE_API_KEY

Run:
    python scripts/ai/generate_narratives.py
"""

import os
import json
import time
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATABASE       = 'AIRBNB_INVESTMENT_DB'
GOLD_SCHEMA    = 'GOLD'
OUTPUT_TABLE   = 'AI_OUTPUTS'
# MODEL          = 'gemini-2.5-flash-lite'
MODEL          = 'gemini-3.1-flash-lite'
OUTPUT_TYPE    = 'AREA_OVERVIEW'
PROMPT_VERSION = 'v2'
# 'resume' — skip already generated rows, fill gaps only
# 'full'   — delete all existing AREA_OVERVIEW rows and regenerate from scratch
#             Use 'full' when prompt logic has changed or Gold tables have been updated
RUN_MODE       = 'full'

CITIES = ['Bristol', 'London', 'Greater Manchester']
# CITIES = ['Bristol']
PERSONAS = {
    'YIELD_MAXIMISER': {
        'label':     'Yield Maximiser',
        'focus':     'maximising annual revenue, high nightly price, '
                     'strong booking demand',
        'score_col': 'score_yield_maximiser',
    },
    'OCCUPANCY_OPTIMISER': {
        'label':     'Occupancy Optimiser',
        'focus':     'consistent high occupancy, minimal vacancy, '
                     'steady booking flow',
        'score_col': 'score_occupancy_optimiser',
    },
    'QUALITY_HOST': {
        'label':     'Quality Host',
        'focus':     'exceptional guest experience, high ratings, '
                     'superhost status, premium positioning',
        'score_col': 'score_quality_host',
    },
}


# ---------------------------------------------------------------------------
# 0. Connections
# ---------------------------------------------------------------------------

def get_gemini_client():
    return genai.Client(api_key=os.environ['GOOGLE_API_KEY'])


def get_snowflake_connection():
    return snowflake.connector.connect(
        user=os.environ['SNOWFLAKE_USER'],
        password=os.environ['SNOWFLAKE_PASSWORD'],
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH'),
        database=DATABASE,
        schema=GOLD_SCHEMA
    )


# ---------------------------------------------------------------------------
# 1. Load
# ---------------------------------------------------------------------------

def clear_existing_narratives(conn, cities):
    city_list = ', '.join([f"'{c}'" for c in cities])
    conn.cursor().execute(f"""
        DELETE FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS
        WHERE "output_type" = 'AREA_OVERVIEW'
        AND "city" IN ({city_list})
    """)
    print(f'Cleared existing AREA_OVERVIEW rows '
          f'for: {", ".join(cities)}')


def load_existing_narratives(conn, city):
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS')
        df = cur.fetch_pandas_all()
        df.columns = df.columns.str.lower()
        df = df[
            (df['city'] == city) &
            (df['output_type'] == OUTPUT_TYPE) &
            (df['ai_narrative'].notna())
        ][['neighbourhood_cleansed', 'persona']]
        print(f'  Found {len(df)} existing {OUTPUT_TYPE} '
              f'rows for {city} — will skip these')
        return df
    except Exception:
        return pd.DataFrame(
            columns=['neighbourhood_cleansed', 'persona']
        )


def load_gold_data(conn, city):
    cur = conn.cursor()

    # SELECT * avoids column-identifier case issues from Snowpark write_pandas;
    # normalise to lowercase and filter in Python.
    cur.execute(f'SELECT * FROM {DATABASE}.{GOLD_SCHEMA}.BOROUGH_SUMMARY')
    df_borough = cur.fetch_pandas_all()
    df_borough.columns = df_borough.columns.str.lower()
    df_borough = df_borough[df_borough['city'] == city][[
        'city', 'neighbourhood_cleansed', 'listing_count',
        'avg_price', 'avg_occupancy', 'avg_revenue',
        'avg_review_rating', 'pct_superhost',
        'count_entire_home_apt', 'count_private_room',
        'score_yield_maximiser', 'score_occupancy_optimiser',
        'score_quality_host',
    ]]

    cur.execute(f'SELECT * FROM {DATABASE}.{GOLD_SCHEMA}.REVIEW_THEMES')
    df_themes = cur.fetch_pandas_all()
    df_themes.columns = df_themes.columns.str.lower()
    df_themes = df_themes[df_themes['city'] == city][[
        'neighbourhood_cleansed', 'top_theme',
        'pct_mentions_price', 'pct_mentions_cleanliness',
        'pct_mentions_location', 'pct_mentions_checkin',
        'avg_sentiment_score',
    ]]

    df = df_borough.merge(df_themes, on='neighbourhood_cleansed', how='left')
    print(f'Loaded {len(df)} neighbourhoods for {city}')
    return df


# ---------------------------------------------------------------------------
# 2. Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(row, persona_key):
    persona = PERSONAS[persona_key]
    score   = row[persona['score_col']]

    system_prompt = f"""You are an expert Airbnb investment analyst \
advising a {persona['label']} who prioritises {persona['focus']}.

Analyse the neighbourhood data and respond with ONLY a valid \
JSON object in this exact format, no other text:

{{
  "investment_summary": "2-3 sentence overall area assessment \
referencing actual numbers",
  "key_strengths": [
    "specific strength 1",
    "specific strength 2",
    "specific strength 3"
  ],
  "key_risks": [
    "specific risk 1",
    "specific risk 2"
  ],
  "confidence": "high if listing_count > 50 and review rating \
exists, medium if 10-50 listings, low if under 10",
  "recommended_action": "one sentence recommendation for \
this persona"
}}

Rules:
- Reference actual numbers from the data
- Do not mention other personas
- Keep investment_summary under 80 words
- Each strength and risk must be one specific sentence"""

    user_prompt = f"""
Neighbourhood: {row['neighbourhood_cleansed']}
City: {row['city']}
Investment Score ({persona['label']}): {round(float(score), 2) if pd.notna(score) else 'N/A'}/100
Average Nightly Price: £{round(float(row['avg_price']), 2) if pd.notna(row['avg_price']) else 'N/A'}
Estimated Occupancy Rate: {round(float(row['avg_occupancy']) / 365 * 100, 1) if pd.notna(row['avg_occupancy']) else 'N/A'}%
Estimated Annual Revenue: £{round(float(row['avg_revenue']), 2) if pd.notna(row['avg_revenue']) else 'N/A'}
Average Review Rating: {round(float(row['avg_review_rating']), 2) if pd.notna(row['avg_review_rating']) else 'N/A'}/5
Total Listings: {int(row['listing_count']) if pd.notna(row['listing_count']) else 'N/A'}
Superhost Percentage: {round(float(row['pct_superhost']), 1) if pd.notna(row['pct_superhost']) else 'N/A'}%
Entire Home/Apt Listings: {int(row['count_entire_home_apt']) if pd.notna(row['count_entire_home_apt']) else 'N/A'}
Top Review Theme: {row['top_theme'] if pd.notna(row['top_theme']) else 'N/A'}
Price Mentions in Reviews: {round(float(row['pct_mentions_price']), 1) if pd.notna(row['pct_mentions_price']) else 'N/A'}%
Location Mentions in Reviews: {round(float(row['pct_mentions_location']), 1) if pd.notna(row['pct_mentions_location']) else 'N/A'}%
Average Sentiment Score: {round(float(row['avg_sentiment_score']), 4) if pd.notna(row['avg_sentiment_score']) else 'N/A'}
"""
    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# 3. Gemini API call
# ---------------------------------------------------------------------------

def call_gemini(client, system_prompt, user_prompt):
    combined = system_prompt + '\n\n' + user_prompt
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=combined
            )
            return response.text
        except Exception as e:
            if attempt == 2:
                print(f'    Gemini API error (final attempt): {e}')
                return None
            if '429' in str(e):
                wait_time = 15 * (attempt + 1)
            else:
                wait_time = 5
            print(f'    Gemini API error (attempt {attempt + 1}), '
                  f'retrying in {wait_time}s: {e}')
            time.sleep(wait_time)


# ---------------------------------------------------------------------------
# 4. Generate
# ---------------------------------------------------------------------------

def generate_narratives(conn, client, city):
    all_rows = []
    df = load_gold_data(conn, city)

    if RUN_MODE == 'resume':
        existing = load_existing_narratives(conn, city)
    else:
        existing = pd.DataFrame(
            columns=['neighbourhood_cleansed', 'persona']
        )

    for _, row in df.iterrows():
        neighbourhood = row['neighbourhood_cleansed']
        for persona_key, persona in PERSONAS.items():
            if len(existing) > 0:
                already_done = existing[
                    (existing['neighbourhood_cleansed'] == neighbourhood) &
                    (existing['persona'] == persona_key)
                ]
                if len(already_done) > 0:
                    print(f'  {neighbourhood} / {persona_key} '
                          f'— skipping, already generated')
                    continue

            system_prompt, user_prompt = build_prompt(row, persona_key)

            ai_response = call_gemini(client, system_prompt, user_prompt)

            # Parse JSON response
            try:
                parsed     = json.loads(ai_response)
                confidence = parsed.get('confidence', 'medium')
            except (json.JSONDecodeError, TypeError):
                parsed     = None
                confidence = 'low' if ai_response else 'error'

            all_rows.append({
                'city':                   city,
                'neighbourhood_cleansed': neighbourhood,
                'persona':                persona_key,
                'output_type':            OUTPUT_TYPE,
                'investment_score':       round(
                    float(row[persona['score_col']]), 2)
                    if pd.notna(row[persona['score_col']])
                    else None,
                'ai_narrative':           ai_response,
                'confidence':             confidence,
                'metrics_json':           json.dumps({
                    'avg_price':     row['avg_price'],
                    'avg_occupancy': row['avg_occupancy'],
                    'avg_revenue':   row['avg_revenue'],
                    'avg_rating':    row['avg_review_rating'],
                }),
                'prompt_version':         PROMPT_VERSION,
                'model_used':             MODEL,
                'computed_at':            pd.Timestamp.now(),
            })

            print(f'  {neighbourhood} / {persona_key} — done')

            # Small delay to avoid rate limiting
            time.sleep(4)

    return pd.DataFrame(all_rows)


# ---------------------------------------------------------------------------
# 5. Write
# ---------------------------------------------------------------------------

def write_to_snowflake(conn, df, overwrite=False):
    if len(df) == 0:
        print('  No new rows to write.')
        return
    write_pandas(
        conn,
        df,
        OUTPUT_TABLE,
        database=DATABASE,
        schema=GOLD_SCHEMA,
        overwrite=overwrite,
        auto_create_table=True
    )
    print(f'Written {len(df)} rows to '
          f'{GOLD_SCHEMA}.{OUTPUT_TABLE}')


# ---------------------------------------------------------------------------
# 6. Validate
# ---------------------------------------------------------------------------

def validate(conn):
    cur = conn.cursor()
    cur.execute(f'SELECT * FROM {DATABASE}.{GOLD_SCHEMA}.{OUTPUT_TABLE}')
    df = cur.fetch_pandas_all()
    df.columns = df.columns.str.lower()
    df_val = (
        df.groupby(['city', 'persona', 'output_type'])
        .agg(
            total=('city', 'count'),
            with_narrative=('ai_narrative', lambda x: x.notna().sum()),
            with_confidence=('confidence', lambda x: x.notna().sum()),
        )
        .reset_index()
        .sort_values(['city', 'persona', 'output_type'])
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

    if RUN_MODE == 'full':
        clear_existing_narratives(conn, CITIES)

    for city in CITIES:
        print(f'\nProcessing {city}...')
        df_narratives = generate_narratives(conn, client, city)
        write_to_snowflake(conn, df_narratives, overwrite=False)
        print(f'{city} complete — {len(df_narratives)} rows written.')

    validate(conn)
    conn.close()
    print('Done.')
