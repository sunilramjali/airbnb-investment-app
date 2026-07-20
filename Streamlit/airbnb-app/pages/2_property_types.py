
import streamlit as st
import pandas as pd
import json
import time
import altair as alt
from db import get_session
st.set_page_config(page_title="Property Types", layout="wide")

#CUSTOM CSS SCRIPT FOR PAGE LOOK
st.markdown(
    """
    <style>
    /* Main app */
    .stApp {
        background-color: white !important;
    }

    [data-testid="stFullScreenFrame"] {
        background-color: white !important;
    }

    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {
        left: 0px !important;
        right: auto !important;
        width: 62% !important;
        max-width: 950px !important;
        min-width: 500px !important;
        margin-left: 0px !important;
        margin-right: auto !important;
        transform: none !important;
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        border-top: none !important;
        pointer-events: none !important;
        bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        padding-bottom: 0 !important;
    }

    [data-testid="stBottomBlockContainer"] > div {
        margin-left: 0px !important;
        margin-right: auto !important;
        width: 100% !important;
        max-width: 950px !important;
        background-color: white !important;
        border: 1px solid #f26359 !important;
        border-radius: 12px !important;
        padding: 16px !important;
        pointer-events: auto !important;
        max-height: 42vh !important;
        overflow-y: auto !important;
    }
    [data-testid="stBottomBlockContainer"] [data-testid="stVerticalBlock"] {
        margin-left: 0px !important;
        margin-right: auto !important;
        width: 100% !important;
    }

    [data-testid="stBottomBlockContainer"] [data-testid="stElementContainer"] {
        margin-left: 0px !important;
        margin-right: auto !important;
    }

    [data-testid="stExpander"] summary {
        background-color: #f8d9d3 !important;
    }

    [data-testid="stExpander"] summary:hover {
        background-color: #f26359 !important;
    }

    [data-testid="stExpander"] details[open] summary {
        background-color: #f8d9d3 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        display: none !important;
    }

    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] {
        background-color: white !important;
        display: none !important;
    }

    [data-testid="stSelectbox"] input {
        background-color: #f8d9d3 !important;
        color: #f26359 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    [data-testid="stSelectbox"] button {
        background-color: #f8d9d3 !important;
    }

    /* Big headings */
    h1, h2 {
        color: #f26359 !important;
    }

    /* Smaller headings */
    h3, h4, h5, h6 {
        color: #000000 !important;
    }

    /* Normal markdown text */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: #000000 !important;
    }

    /* Captions */
    [data-testid="stCaptionContainer"] {
        color: #000000 !important;
    }

    div[data-testid="stAlert"] {
        background-color: #FCEDEA !important;
        color: #7A2E2A !important;
        border: 1px solid #F26359 !important;
        border-left: 6px solid #F26359 !important;
        border-radius: 12px !important;
    }

    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        color: #7A2E2A !important;
    }

    /* Metrics */
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        color: #000000 !important;
    }

    /* Buttons */
    div.stButton > button[kind="secondary"] {
        background-color:#FFFAF0 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
        border-radius: 12px !important;
    }

    div.stButton > button[kind="secondary"]:hover {
        background-color: #f8d9d3 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
    }

    div.stButton > button[kind="primary"] {
        background-color: #f8d9d3 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: #f8d9d3 !important;
        border: 2px solid #f26359 !important;
        border-radius: 12px !important;
    }

    div.stButton > button p {
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.3 !important;
    }

    [data-testid="stLinkButton"] a {
        background-color:#FFFAF0 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
        border-radius: 12px !important;
    }

    [data-testid="stLinkButton"] a:hover {
        background-color: #f8d9d3 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
    }

     /* Multiselect outer box */
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        background-color: #f8d9d3 !important;
    }

    /* Text typed inside the multiselect */
    [data-testid="stMultiSelect"] input {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* Placeholder text */
    [data-testid="stMultiSelect"] input::placeholder {
        color: #7A2E2A !important;
        opacity: 1 !important;
    }

    /* Selected option boxes / tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: #f26359 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }

    /* Text inside selected tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
        color: #ffffff !important;
    }

    /* Remove icon inside selected tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }

    /* Dropdown menu background */
    div[data-baseweb="popover"] ul {
        background-color: #ffffff !important;
    }

    /* Dropdown options */
    div[data-baseweb="popover"] li {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    /* Dropdown option hover */
    div[data-baseweb="popover"] li:hover {
        background-color: #f8d9d3 !important;
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

page_col1, page_col2, empty_col, page_col3 = st.columns([1,1,5,1])
with page_col1:
    if st.button('Landing', use_container_width = True):
        st.switch_page('landing.py')

with page_col2:
    if st.button('Area Overview', use_container_width = True):
        st.switch_page('pages/1_area_overview.py')
        
with page_col3:
    if st.button('Documentaion', use_container_width = True):
        st.switch_page('pages/4_Documentation.py')

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

session = get_session()

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

if "property_pie_view" not in st.session_state:
    st.session_state["property_pie_view"] = "main"


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
                    st.markdown("### Property Type Listing Share")

                    chart_data = all_property_types.copy()
                
                    def get_pie_group(property_group):
                        property_group_clean = str(property_group).strip().lower()
                
                        if property_group_clean == "house":
                            return "House"
                        elif property_group_clean == "apartment / flat":
                            return "Apartment / Flat"
                        else:
                            return "Others"
                
                    chart_data["PIE_GROUP"] = chart_data["PROPERTY_GROUP"].apply(get_pie_group)
                
                    def create_property_item(selected_row):
                        return {
                            "property_group": selected_row["PROPERTY_GROUP"],
                            "neighbourhood": selected_row["NEIGHBOURHOOD"],
                            "city": selected_row["CITY"],
                            "listing_count": selected_row["LISTING_COUNT"],
                            "investment_score": selected_row[score_column],
                            "persona": persona,
                            "average_adr": selected_row["AVERAGE_ADR"],
                            "median_adr": selected_row["MEDIAN_ADR"],
                            "average_annual_revenue": selected_row["AVERAGE_ANNUAL_REVENUE"],
                            "median_annual_revenue": selected_row["MEDIAN_ANNUAL_REVENUE"],
                            "average_occupancy_rate": selected_row["AVERAGE_OCCUPANCY_RATE"],
                            "average_rating": selected_row["AVERAGE_RATING"],
                            "average_bedrooms": selected_row["AVERAGE_BEDROOMS"],
                            "median_sale_price": selected_row["MEDIAN_SALE_PRICE"],
                            "sale_txn_count": selected_row["SALE_TXN_COUNT"]
                        }
                
                    def property_is_already_starred(property_item):
                        property_key = (
                            f"{property_item['city']}_"
                            f"{property_item['neighbourhood']}_"
                            f"{property_item['property_group']}_"
                            f"{property_item['persona']}"
                        )
                
                        return any(
                            f"{item['city']}_{item['neighbourhood']}_{item['property_group']}_{item.get('persona', '')}" == property_key
                            for item in st.session_state["starred_property_types"]
                        )
                
                    def star_property(selected_row):
                        property_item = create_property_item(selected_row)
                
                        if not property_is_already_starred(property_item):
                            if len(st.session_state["starred_property_types"]) >= 3:
                                st.warning("You can only star 3 property types.")
                
                            else:
                                st.session_state["starred_property_types"].append(property_item)
                                st.success(f"Added {property_item['property_group']} to starred property types.")
                                st.rerun()
                
                    if st.session_state["property_pie_view"] == "main":

                        chart_data["MEDIAN_ANNUAL_REVENUE_PER_ROOM"] = (chart_data["MEDIAN_ANNUAL_REVENUE"] / chart_data["AVERAGE_BEDROOMS"].replace(0, pd.NA))

                        grouped_chart_data = (
                            chart_data
                            .groupby("PIE_GROUP", as_index=False)
                            .agg(
                                LISTING_COUNT=("LISTING_COUNT", "sum"),
                                INVESTMENT_SCORE=("INVESTMENT_SCORE_YIELD" if score_column == "INVESTMENT_SCORE_YIELD" else score_column, "mean"),
                                AVERAGE_ADR=("AVERAGE_ADR", "mean"),
                                MEDIAN_ADR=("MEDIAN_ADR", "mean"),
                                MEDIAN_ANNUAL_REVENUE_PER_ROOM=("MEDIAN_ANNUAL_REVENUE_PER_ROOM", "mean"),
                                AVERAGE_ANNUAL_REVENUE=("AVERAGE_ANNUAL_REVENUE", "mean"),
                                MEDIAN_ANNUAL_REVENUE=("MEDIAN_ANNUAL_REVENUE", "mean"),
                                AVERAGE_OCCUPANCY_RATE=("AVERAGE_OCCUPANCY_RATE", "mean"),
                                AVERAGE_RATING=("AVERAGE_RATING", "mean"),
                                AVERAGE_BEDROOMS=("AVERAGE_BEDROOMS", "mean"),
                                MEDIAN_SALE_PRICE=("MEDIAN_SALE_PRICE", "mean"),
                                SALE_TXN_COUNT=("SALE_TXN_COUNT", "sum")
                            )
                        )
                
                        total_listings = grouped_chart_data["LISTING_COUNT"].sum()
                
                        grouped_chart_data["LISTING_PERCENTAGE"] = (
                            grouped_chart_data["LISTING_COUNT"] / total_listings * 100
                        )
                
                        property_selection = alt.selection_point(
                            fields=["PIE_GROUP"],
                            name="main_property_select"
                        )
                
                        pie_chart = (
                            alt.Chart(grouped_chart_data)
                            .mark_arc(stroke="white", strokeWidth=2)
                            .encode(
                                theta=alt.Theta("LISTING_COUNT:Q"),
                                color=alt.Color(
                                    "PIE_GROUP:N",
                                    title="Property Type",
                                    scale=alt.Scale(scheme="category10")
                                ),
                                opacity=alt.condition(
                                    property_selection,
                                    alt.value(1),
                                    alt.value(0.45)
                                ),
                                tooltip=[
                                    alt.Tooltip("PIE_GROUP:N", title="Property Type"),
                                    alt.Tooltip("LISTING_PERCENTAGE:Q", title="Listing Share (%)", format=".1f"),
                                    alt.Tooltip("LISTING_COUNT:Q", title="Listings", format=",.0f"),
                                    alt.Tooltip("MEDIAN_ANNUAL_REVENUE_PER_ROOM:Q", title="Median AR per Room", format=",.0f"),
                                    alt.Tooltip("INVESTMENT_SCORE:Q", title="Avg Investment Score", format=".2f"),
                                    alt.Tooltip("AVERAGE_ADR:Q", title="Avg ADR", format=",.0f"),
                                    #alt.Tooltip("MEDIAN_ADR:Q", title="Median ADR", format=",.0f"),
                                    #alt.Tooltip("AVERAGE_ANNUAL_REVENUE:Q", title="Avg Annual Revenue", format=",.0f"),
                                    alt.Tooltip("MEDIAN_ANNUAL_REVENUE:Q", title="Median AR", format=",.0f"),
                                    #alt.Tooltip("AVERAGE_OCCUPANCY_RATE:Q", title="Avg Occupancy", format=".1f"),
                                    alt.Tooltip("AVERAGE_RATING:Q", title="Avg Rating", format=".2f"),
                                    alt.Tooltip("AVERAGE_BEDROOMS:Q", title="Avg Bedrooms", format=".1f"),
                                    alt.Tooltip("MEDIAN_SALE_PRICE:Q", title="Median Sale Price", format=",.0f"),
                                    alt.Tooltip("SALE_TXN_COUNT:Q", title="Sale Transactions", format=",.0f"),
                                ]
                            )
                            .add_params(property_selection)
                            .properties(height=420, background="#FFFFFF")
                            .configure_legend(labelColor="#000000", titleColor="#000000")
                        )
                
                        pie_event = st.altair_chart(
                            pie_chart,
                            use_container_width=True,
                            key=f"main_property_type_pie_{selected_city}_{selected_neighbourhood}_{persona}",
                            on_select="rerun"
                        )
                
                        selected_group = None
                
                        try:
                            selection_data = pie_event["selection"]["main_property_select"]
                            if len(selection_data) > 0:
                                selected_group = selection_data[0]["PIE_GROUP"]
                        except Exception:
                            selected_group = None
                
                        if selected_group == "Others":
                            st.session_state["property_pie_view"] = "others"
                            st.rerun()
                
                        elif selected_group in ["House", "Apartment / Flat"]:
                            selected_rows = chart_data[
                                chart_data["PROPERTY_GROUP"].astype(str).str.strip().str.lower()
                                == selected_group.strip().lower()
                            ]
                
                            if not selected_rows.empty:
                                star_property(selected_rows.iloc[0])
                
                    else:
                        st.markdown("#### Other Property Types")
                
                        if st.button("Back to main property groups"):
                            st.session_state["property_pie_view"] = "main"
                            st.rerun()
                
                        other_chart_data = chart_data[
                            chart_data["PIE_GROUP"] == "Others"
                        ].copy()
                
                        total_other_listings = other_chart_data["LISTING_COUNT"].sum()
                
                        other_chart_data["LISTING_PERCENTAGE"] = (
                            other_chart_data["LISTING_COUNT"] / total_other_listings * 100
                        )
                
                        other_selection = alt.selection_point(
                            fields=["PROPERTY_GROUP"],
                            name="other_property_select"
                        )
                
                        other_pie_chart = (
                            alt.Chart(other_chart_data)
                            .mark_arc(stroke="white", strokeWidth=2)
                            .encode(
                                theta=alt.Theta("LISTING_COUNT:Q"),
                                color=alt.Color(
                                    "PROPERTY_GROUP:N",
                                    title="Other Property Types",
                                    scale=alt.Scale(scheme='set3')
                                ),
                                opacity=alt.condition(
                                    other_selection,
                                    alt.value(1),
                                    alt.value(0.45)
                                ),
                                tooltip=[
                                    alt.Tooltip("PROPERTY_GROUP:N", title="Property Type"),
                                    alt.Tooltip("LISTING_PERCENTAGE:Q", title="Listing Share (%)", format=".1f"),
                                    alt.Tooltip("LISTING_COUNT:Q", title="Listings", format=",.0f"),
                                    alt.Tooltip(f"{score_column}:Q", title="Investment Score", format=".2f"),
                                    alt.Tooltip("AVERAGE_ADR:Q", title="Avg ADR", format=",.0f"),
                                    alt.Tooltip("MEDIAN_ADR:Q", title="Median ADR", format=",.0f"),
                                    alt.Tooltip("AVERAGE_ANNUAL_REVENUE:Q", title="Avg Annual Revenue", format=",.0f"),
                                    alt.Tooltip("MEDIAN_ANNUAL_REVENUE:Q", title="Median Annual Revenue", format=",.0f"),
                                    alt.Tooltip("AVERAGE_OCCUPANCY_RATE:Q", title="Avg Occupancy", format=".1f"),
                                    alt.Tooltip("AVERAGE_RATING:Q", title="Avg Rating", format=".2f"),
                                    alt.Tooltip("AVERAGE_BEDROOMS:Q", title="Avg Bedrooms", format=".1f"),
                                    alt.Tooltip("MEDIAN_SALE_PRICE:Q", title="Median Sale Price", format=",.0f"),
                                    alt.Tooltip("SALE_TXN_COUNT:Q", title="Sale Transactions", format=",.0f"),
                                ]
                            )
                            .add_params(other_selection)
                            .properties(height=420, background="#FFFFFF")
                            .configure_legend(labelColor="#000000", titleColor="#000000")
                        )
                
                        other_pie_event = st.altair_chart(
                            other_pie_chart,
                            use_container_width=True,
                            key=f"other_property_type_pie_{selected_city}_{selected_neighbourhood}_{persona}",
                            on_select="rerun"
                        )
                
                        selected_other_property = None
                
                        try:
                            other_selection_data = other_pie_event["selection"]["other_property_select"]
                            if len(other_selection_data) > 0:
                                selected_other_property = other_selection_data[0]["PROPERTY_GROUP"]
                        except Exception:
                            selected_other_property = None
                
                        if selected_other_property is not None:
                            selected_rows = other_chart_data[
                                other_chart_data["PROPERTY_GROUP"] == selected_other_property
                            ]
                
                            if not selected_rows.empty:
                                star_property(selected_rows.iloc[0])

                with starred_col:
                    with st.container(border=True):
                        st.markdown("### Starred Property Types")

                        starred_property_types = st.session_state["starred_property_types"]
                        starred_count = len(starred_property_types)
                
                        st.write(f"{starred_count}/3 selected")
                
                        if starred_count < 3:
                            st.info("Select 3 property types to continue.")
                        elif starred_count == 3:
                            st.success("Ready to continue.")
                
                        if starred_count == 0:
                            st.write("No property types starred yet.")
                
                        else:
                            for item in starred_property_types:
                                property_group = item["property_group"]
                                neighbourhood = item["neighbourhood"]
                                city_name = item["city"]
                
                                star_col1, star_col2 = st.columns([3, 1])
                
                                with star_col1:
                                    st.write(f"**⭐ {property_group}**")
                                    st.write(neighbourhood)
                                    st.caption(city_name)
                
                                    if "investment_score" in item:
                                        st.caption(f"Investment Score: {item['investment_score']:,.2f}")
                
                                with star_col2:
                                    if st.button(
                                        "🗑️",
                                        key="remove_starred_property_" + city_name + "_" + neighbourhood + "_" + property_group,
                                        use_container_width=True
                                    ):
                                        st.session_state["starred_property_types"].remove(item)
                                        st.rerun()
                        
                        if len(st.session_state['starred_property_types']) == 3:
                            if st.button('Generate Analysis', use_container_width = True):
                                st.switch_page('pages/2.1_property_types_comparison.py')
                            if st.button('Continue to Listing Candidates', use_container_width = True):
                                st.switch_page('pages/3_listing_candidates.py')
                        else:
                            st.button('Generate Analysis', disabled = True)
                            st.button('Continue to Listing Candidates', disabled = True)
                            st.caption('Select exactly 3 Property Types before continuing.')
#---
with st.bottom:
    #with st.expander("AI Summary"):

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

            with st.expander('Click for more'):
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