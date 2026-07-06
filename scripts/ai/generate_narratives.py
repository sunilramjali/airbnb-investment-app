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
    python scripts/generate_narratives.py
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

CITIES = ['BRISTOL', 'LONDON', 'GREATER_MANCHESTER']

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

def load_gold_data(conn, city):
    df_borough = pd.read_sql(f"""
        SELECT
            "city",
            "neighbourhood_cleansed",
            "listing_count",
            "avg_price",
            "avg_occupancy",
            "avg_revenue",
            "avg_review_rating",
            "pct_superhost",
            "count_entire_home_apt",
            "count_private_room",
            "score_yield_maximiser",
            "score_occupancy_optimiser",
            "score_quality_host"
        FROM {DATABASE}.{GOLD_SCHEMA}.BOROUGH_SUMMARY
        WHERE "city" = '{city}'
    """, conn)

    df_themes = pd.read_sql(f"""
        SELECT
            "neighbourhood_cleansed",
            "top_theme",
            "pct_mentions_price",
            "pct_mentions_cleanliness",
            "pct_mentions_location",
            "pct_mentions_checkin",
            "avg_sentiment_score"
        FROM {DATABASE}.{GOLD_SCHEMA}.REVIEW_THEMES
        WHERE "city" = '{city}'
    """, conn)

    df = df_borough.merge(
        df_themes,
        on='neighbourhood_cleansed',
        how='left'
    )

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

    for _, row in df.iterrows():
        neighbourhood = row['neighbourhood_cleansed']
        for persona_key, persona in PERSONAS.items():
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

    print(f'{city} complete — {len(df) * len(PERSONAS)} rows generated')
    return pd.DataFrame(all_rows)


# ---------------------------------------------------------------------------
# 5. Write
# ---------------------------------------------------------------------------

def write_to_snowflake(conn, df, overwrite=False):
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
    df_val = pd.read_sql(f"""
        SELECT
            "city",
            "persona",
            "output_type",
            COUNT(*) AS total,
            COUNT("ai_narrative") AS with_narrative,
            COUNT("confidence") AS with_confidence
        FROM {DATABASE}.{GOLD_SCHEMA}.{OUTPUT_TABLE}
        GROUP BY "city", "persona", "output_type"
        ORDER BY "city", "persona", "output_type"
    """, conn)
    print(df_val.to_string(index=False))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print('Initialising connections...')
    conn   = get_snowflake_connection()
    client = get_gemini_client()
    print('Connections established.')

    # Truncate once before loop to avoid duplicates
    try:
        conn.cursor().execute(
            'TRUNCATE TABLE AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS'
        )
        print('AI_OUTPUTS table truncated — starting fresh.')
    except Exception as e:
        print(f'Note: Could not truncate table (may not exist yet): {e}')

    # Process and write each city separately
    for city in CITIES:
        print(f'\nProcessing {city}...')
        df = generate_narratives(conn, client, city)
        write_to_snowflake(conn, df, overwrite=False)
        print(f'{city} complete — {len(df)} rows written.')

    validate(conn)
    conn.close()
    print('Done. Google API key can now be deleted from '
          'aistudio.google.com after verifying results.')
