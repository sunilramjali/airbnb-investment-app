import streamlit as st
import os
import pandas as pd
import json
import time

def format_money(value):
    if pd.isna(value):
        return "N/A"
    return f"£{value:,.0f}"


def format_number(value):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.0f}"


def format_decimal(value, decimals=2):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def format_percent(value):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.1f}%"

st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
    div.stButton > button {
        white-space: pre-line;
        min-height: 80px;
    }

    div.stButton > button p {
        white-space: pre-line;
        text-align: center;
        font-size: 13px;
        line-height: 1.3;
    }

    div.stButton > button p::first-line {
        font-size: 18px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#AI_COOLDOWN_SECONDS = 60

#if "property_ai_summaries" not in st.session_state:
 #   st.session_state["property_ai_summaries"] = {}

#if "last_property_ai_call_time" not in st.session_state:
 #   st.session_state["last_property_ai_call_time"] = 0
    
if "starred_neighbourhoods" not in st.session_state:
    st.session_state["starred_neighbourhoods"] = []

if "selected_property_neighbourhood" not in st.session_state:
    st.session_state["selected_property_neighbourhood"] = None

if "selected_property_city" not in st.session_state:
    st.session_state["selected_property_city"] = None

if "starred_property_types" not in st.session_state:
    st.session_state["starred_property_types"] = []

if len(st.session_state['starred_property_types']) == 3:
    if st.button('Continue to Listing Candidates'):
        st.switch_page('pages/3_listing_candidates.py')
else:
    st.button('Continue to Listing Candidates', disabled = True)
    st.caption('Select exactly 3 Property Types before continuing.')
#TITLE ---

st.title('Property Type')
st.subheader('Out of your favourite neighbourhoods, find the best property types based on your selected persona. Choose 3 property types from any of the nieghbourhoods that spark the most interest.')
#SQL QUERY ---

@st.cache_data(ttl=300)
def load_property_types(_session):
    return _session.sql(
        """
       SELECT
            j1.CITY,
            p.NEIGHBOURHOOD,
            p.PROPERTY_GROUP,
            p.LISTING_COUNT,
            p.AVG_ADR AS average_adr,
            p.MEDIAN_ADR AS median_adr,
            p.AVG_ANNUAL_REVENUE AS average_annual_revenue,
            p.MEDIAN_ANNUAL_REVENUE AS median_annual_revenue,
            p.AVG_OCCUPANCY_RATE AS average_occupancy_rate,
            p.AVG_RATING AS average_rating,
            p.AVG_BEDROOMS AS average_bedrooms,
            p.MEDIAN_SALE_PRICE AS median_sale_price,
            p.SALE_TXN_COUNT AS sale_txn_count,
            j1.INVESTMENT_SCORE_YIELD,
            j1.INVESTMENT_SCORE_OCCUPANCY,
            j1.INVESTMENT_SCORE_QUALITY
    
        FROM (
            SELECT 
                a.NEIGHBOURHOOD,
                a.PROPERTY_GROUP,
                b.CITY,
                AVG(b.SCORE_YIELD_MAXIMISER) AS INVESTMENT_SCORE_YIELD,
                AVG(b.SCORE_OCCUPANCY_OPTIMISER) AS INVESTMENT_SCORE_OCCUPANCY,
                AVG(b.SCORE_QUALITY_HOST) AS INVESTMENT_SCORE_QUALITY
        
            FROM AIRBNB_INVESTMENT_DB.GOLD.MART_LISTING_CANDIDATES a
        
            LEFT JOIN AIRBNB_INVESTMENT_DB.GOLD.INVESTMENT_SCORES b
            
            ON a.LISTING_ID = b.LISTING_ID
        
            WHERE a.NEIGHBOURHOOD IS NOT NULL AND a.PROPERTY_GROUP IS NOT NULL AND b.CITY IS NOT NULL
        
            GROUP BY b.CITY, a.NEIGHBOURHOOD, a.PROPERTY_GROUP
        ) j1
        
        JOIN AIRBNB_INVESTMENT_DB.GOLD.MART_PROPERTY_GROUP p
        
        ON p.NEIGHBOURHOOD = j1.NEIGHBOURHOOD AND p.PROPERTY_GROUP = j1.PROPERTY_GROUP
        
        WHERE p.NEIGHBOURHOOD IS NOT NULL AND p.PROPERTY_GROUP IS NOT NULL AND LOWER(TRIM(p.PROPERTY_GROUP)) != 'other / unknown'
        
        ORDER BY j1.CITY, p.NEIGHBOURHOOD, p.PROPERTY_GROUP;
            """
    ).to_pandas()

@st.cache_data(ttl=300)
def load_summary(_session):
    return _session.sql(
        """
        SELECT *
        FROM AIRBNB_INVESTMENT_DB.GOLD.AI_OUTPUTS
    """
    ).to_pandas()

property_types = load_property_types(session)

ai_summary = load_summary(session)

#VISUALISATIONS ---
starred_neighbourhoods = st.session_state["starred_neighbourhoods"]

st.markdown("### Your starred neighbourhoods")

if len(starred_neighbourhoods) == 0:
    st.info(
        "You have not starred any neighbourhoods yet. "
        "Go back to the Area Overview page and star up to 3 neighbourhoods."
    )

else:
    cols = st.columns(3)

    for i, neighbourhood in enumerate(starred_neighbourhoods[:3]):

        neighbourhood_name = neighbourhood["neighbourhood"]
        city_name = neighbourhood["city"]

        button_label = f"{neighbourhood_name}\n{city_name}"

        with cols[i]:
            if st.button(
                label=button_label,
                key=f"property_neighbourhood_{i}_{city_name}_{neighbourhood_name}",
                use_container_width=True
            ):
                st.session_state["selected_property_neighbourhood"] = neighbourhood_name
                st.session_state["selected_property_city"] = city_name


selected_neighbourhood = st.session_state["selected_property_neighbourhood"]
selected_city = st.session_state["selected_property_city"]
persona = st.session_state.get("persona", None)

if selected_neighbourhood is not None:

    if persona is None:
        st.warning("No persona has been selected yet.")

    else:
        persona_clean = str(persona).strip().lower()

        if persona_clean == "yield_maximiser":
            score_column = "INVESTMENT_SCORE_YIELD"

        elif persona_clean == "occupancy_optimiser":
            score_column = "INVESTMENT_SCORE_OCCUPANCY"

        elif persona_clean == "quality_host":
            score_column = "INVESTMENT_SCORE_QUALITY"

        else:
            score_column = None
            st.warning(f"Unknown persona selected: {persona}")

        if score_column is not None:

            neighbourhood_data = property_types[
                (property_types["CITY"].astype(str).str.strip().str.lower() == str(selected_city).strip().lower())
                & (property_types["NEIGHBOURHOOD"].astype(str).str.strip().str.lower() == str(selected_neighbourhood).strip().lower())
            ].copy()

            if neighbourhood_data.empty:
                st.warning("No property group data found for this neighbourhood.")

            else:
                neighbourhood_data = neighbourhood_data.dropna(subset=[score_column])

                selected_city = neighbourhood_data["CITY"].iloc[0]

                st.markdown(f"## {selected_neighbourhood}")
                st.caption(f"City: {selected_city}")
                st.caption(f"Ranking based on persona: {persona}")

                st.markdown("### Top 3 Property Types")

                top_3 = neighbourhood_data.sort_values(
                    by=score_column,
                    ascending=False
                ).head(3)

                top_cols = st.columns(3)

                for i, row in enumerate(top_3.itertuples()):
                    with top_cols[i]:

                        with st.container(border=True):
                            st.markdown(f"## **{row.PROPERTY_GROUP}**")

                            st.metric(
                                label="Investment Score",
                                value=f"{getattr(row, score_column):,.2f}"
                            )

                            st.caption(f"Listings: {row.LISTING_COUNT:,.0f}")

                st.divider()

                all_property_types = neighbourhood_data.sort_values(
                    by=score_column,
                    ascending=False
                )

                list_col, starred_col = st.columns([2, 1], gap="medium")

                with list_col:
                    st.markdown("### All Property Types in this neighbourhood")

                    for row in all_property_types.itertuples():
                        property_group = row.PROPERTY_GROUP
                        neighbourhood = row.NEIGHBOURHOOD
                        city = row.CITY
                        listing_count = row.LISTING_COUNT
                        investment_score = getattr(row, score_column)

                        property_item = {
                            "property_group": property_group,
                            "neighbourhood": neighbourhood,
                            "city": city,
                            "listing_count": listing_count,
                            "investment_score": investment_score,
                            "persona": persona,
                            "average_adr": row.AVERAGE_ADR,
                            "median_adr": row.MEDIAN_ADR,
                            "average_annual_revenue": row.AVERAGE_ANNUAL_REVENUE,
                            "median_annual_revenue": row.MEDIAN_ANNUAL_REVENUE,
                            "average_occupancy_rate": row.AVERAGE_OCCUPANCY_RATE,
                            "average_rating": row.AVERAGE_RATING,
                            "average_bedrooms": row.AVERAGE_BEDROOMS,
                            "median_sale_price": row.MEDIAN_SALE_PRICE,
                            "sale_txn_count": row.SALE_TXN_COUNT
                        }

                        property_key = f"{city}_{neighbourhood}_{property_group}_{persona}"

                        already_starred = any(
                            f"{item['city']}_{item['neighbourhood']}_{item['property_group']}_{item.get('persona', '')}" == property_key
                            for item in st.session_state["starred_property_types"]
                        )

                        with st.container(border=True):
                            row_cols = st.columns([2.4, 1.8, 2.2, 1])

                            with row_cols[0]:
                                st.markdown(f"## {property_group}")
                        
                            with row_cols[1]:
                                st.markdown("### Performance")
                                st.write(f"**Investment Score:** {format_decimal(investment_score, 2)}")
                                st.write(f"**Listings:** {format_number(listing_count)}")
                                st.write(f"**Avg Occupancy:** {format_percent(row.AVERAGE_OCCUPANCY_RATE)}")
                                st.write(f"**Avg Rating:** {format_decimal(row.AVERAGE_RATING, 2)}")
                                st.write(f"**Avg Bedrooms:** {format_decimal(row.AVERAGE_BEDROOMS, 1)}")
                            
                            with row_cols[2]:
                                st.markdown("### Financials")
                                st.write(f"**Avg ADR:** {format_money(row.AVERAGE_ADR)}")
                                st.write(f"**Median ADR:** {format_money(row.MEDIAN_ADR)}")
                                st.write(f"**Avg Annual Revenue:** {format_money(row.AVERAGE_ANNUAL_REVENUE)}")
                                st.write(f"**Median Annual Revenue:** {format_money(row.MEDIAN_ANNUAL_REVENUE)}")
                                st.write(f"**Median Sale Price:** {format_money(row.MEDIAN_SALE_PRICE)}")
                                st.write(f"**Sale Transactions:** {format_number(row.SALE_TXN_COUNT)}")
                        
                            with row_cols[3]:
                                if already_starred:
                                    st.success("Selected")
                                else:
                                    if st.button(
                                        "Star",
                                        key=f"star_property_{property_key}",
                                        use_container_width=True
                                    ):
                                        if len(st.session_state["starred_property_types"]) < 3:
                                            st.session_state["starred_property_types"].append(property_item)
                                            st.rerun()
                                        else:
                                            st.warning("You can only star 3 property types.")

                with starred_col:
                    with st.container(border=True):
                        st.markdown("### Starred Property Types")

                        starred_property_types = st.session_state["starred_property_types"]

                        if len(starred_property_types) == 0:
                            st.info("No property types starred yet.")

                        else:
                            for i, item in enumerate(starred_property_types):
                                with st.container(border=True):
                                    st.markdown(f"### ⭐ {item['property_group']}")
                                    st.markdown(f"**{item['neighbourhood']}**")
                                    st.caption(item["city"])

                                    if "investment_score" in item:
                                        st.caption(f"Investment Score: {item['investment_score']:,.2f}")

                                    if st.button(
                                        "Remove",
                                        key=f"remove_starred_property_{i}_{item['city']}_{item['neighbourhood']}_{item['property_group']}",
                                        use_container_width=True
                                    ):
                                        st.session_state["starred_property_types"].pop(i)
                                        st.rerun()

                        st.caption(f"{len(starred_property_types)} / 3 selected")

#---
with st.bottom:
    with st.expander("AI Summary"):

        persona = st.session_state.get("persona", None)
        selected_neighbourhood = st.session_state.get("selected_property_neighbourhood", None)
        selected_city = st.session_state.get("selected_property_city", None)

        if persona is None:
            st.warning("No persona has been selected yet.")

        elif selected_neighbourhood is None:
            st.warning("No neighbourhood has been selected yet.")

        else:
            st.write("This is your AI summary using persona:", persona)

            st.header(selected_neighbourhood)

            mask = (
                (ai_summary["persona"].astype(str).str.strip().str.lower() == str(persona).strip().lower())
                & (ai_summary["neighbourhood_cleansed"].astype(str).str.strip().str.lower() == str(selected_neighbourhood).strip().lower())
                & (ai_summary["output_type"].astype(str).str.strip().str.lower() == "recommendation")
            )

            matches = ai_summary.loc[mask, "ai_narrative"]

            if not matches.empty:
                narrative_dict = json.loads(matches.iloc[0])

                recommendation_summary = narrative_dict.get(
                    "recommendation_summary",
                    narrative_dict.get(
                        "investment_summary",
                        narrative_dict.get(
                            "summary",
                            "No recommendation summary available."
                        )
                    )
                )
            
                top_pick = narrative_dict.get("top_pick", None)
                top_pick_reason = narrative_dict.get("top_pick_reason", None)
                second_pick = narrative_dict.get("second_pick", None)
                second_pick_reason = narrative_dict.get("second_pick_reason", None)
                what_to_avoid = narrative_dict.get("what_to_avoid", None)
            
                st.write(recommendation_summary)
            
                st.subheader("**Top Pick**")
                st.write(f"**{top_pick}**")
            
                st.caption("Reason:")
                st.write(top_pick_reason)
            
                st.subheader("**Second Pick**")
                st.write(f"**{second_pick}**")

                st.caption("Reason:")
                st.write(second_pick_reason)

                st.subheader("**What to Avoid**")
                st.write(what_to_avoid)
            
            else:
                st.warning(
                    "No AI recommendation found for this persona/neighbourhood combination."
                )