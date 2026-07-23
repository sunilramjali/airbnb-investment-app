import streamlit as st
import os
import pydeck as pdk
import json
import altair as alt
import pandas as pd
import numpy as np
from streamlit.components.v1 import html
from db import get_session
from nav import render_logo
#import plotly.graph_objects as go
from snowflake.snowpark.functions import st_x, st_y

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

    [data-testid="stBottomBlockContainer"] {
        background-color: white !important;
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
    @media print {

    @page {
        size: A4 landscape;
        margin: 12mm;
    }

    /* Force the whole page to print in white */
    html,
    body,
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    .block-container {
        background: #ffffff !important;
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    /* Force all text to black */
    h1,
    h2,
    h3,
    h4,
    h5,
    h6,
    p,
    span,
    div,
    label,
    li,
    [data-testid="stMarkdownContainer"],
    [data-testid="stCaptionContainer"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* Hide Streamlit chrome */
    header,
    footer,
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* Hide Streamlit buttons */
    div.stButton,
    [data-testid="stButton"] {
        display: none !important;
    }

    /* Hide the custom print-button iframe */
    iframe {
        display: none !important;
    }

    /* Remove unnecessary app padding */
    .block-container,
    [data-testid="stMainBlockContainer"] {
        max-width: 100% !important;
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Make bordered Streamlit containers printable */
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        background: #ffffff !important;
        background-color: #ffffff !important;
        border-color: #b0b0b0 !important;
        box-shadow: none !important;
        break-inside: avoid !important;
        page-break-inside: avoid !important;
        display: block !important;
    }

    /* Force Streamlit columns to fit the page */
    [data-testid="stHorizontalBlock"] {
        width: 100% !important;
        gap: 12px !important;
        break-inside: avoid !important;
        page-break-inside: avoid !important;
    }

    [data-testid="column"] {
        min-width: 0 !important;
    }

    /* Make Altair chart wrappers printable */
    [data-testid="stVegaLiteChart"] {
        background: #ffffff !important;
        background-color: #ffffff !important;
        width: 100% !important;
        max-width: 100% !important;
        overflow: visible !important;
        break-inside: avoid !important;
        page-break-inside: avoid !important;
    }

    [data-testid="stVegaLiteChart"] > div,
    [data-testid="stVegaLiteChart"] canvas,
    [data-testid="stVegaLiteChart"] svg {
        background: #ffffff !important;
        background-color: #ffffff !important;
        max-width: 100% !important;
    }

    /* Remove dark fills from generic Streamlit blocks */
    [data-testid="stVerticalBlock"],
    [data-testid="stElementContainer"] {
        background: transparent !important;
    }

    /* Hide the logo, buttons and the auto-print iframe when printing.
       Print mode already re-renders only the charts + their titles,
       so no fragile :has() reveal rules are needed here. */
    [data-testid="stImage"],
    div.stButton,
    [data-testid="stButton"],
    iframe {
        display: none !important;
    }
    }
    </style>
    """,
    unsafe_allow_html=True
)

print_mode = st.query_params.get("print") == "1"

if not print_mode:
    render_logo()

page_col1, empty_col, print_col = st.columns([1, 6, 1])

if print_mode:
    with page_col1:
        if st.button("Back", use_container_width=True):
            if "print" in st.query_params:
                del st.query_params["print"]
            st.rerun()
else:
    with page_col1:
        if st.button("Back to Area Overview", use_container_width=True):
            st.switch_page(
                "pages/1_area_overview.py")

    with print_col:
        if st.button("Print", use_container_width=True):
            st.query_params["print"] = "1"
            st.rerun()

if "starred_neighbourhoods" not in st.session_state:
    st.session_state["starred_neighbourhoods"] = []

starred_neighbourhoods = st.session_state["starred_neighbourhoods"]

if len(starred_neighbourhoods) != 3:
    st.warning(
        "Exactly 3 neighbourhoods must be starred before generating "
        "the area comparison."
    )
    st.stop()

session = get_session()

# SQL QUERY FOR SHORT-TERM AND LONG-TERM STRATEGY
@st.cache_data(ttl=300)
def load_area_strategy(_session):
    return _session.sql(
        """
        SELECT
            CITY,
            NEIGHBOURHOOD,
            SUM(LISTING_COUNT) AS LISTING_COUNT,
            SUM(ST_ANNUAL_INCOME * LISTING_COUNT) / NULLIF(SUM(LISTING_COUNT), 0) AS ST_ANNUAL_REVENUE,
            SUM(LT_ANNUAL_INCOME * LISTING_COUNT) / NULLIF(SUM(LISTING_COUNT), 0) AS LT_ANNUAL_RENT,
            SUM(ST_GROSS_YIELD_PCT * LISTING_COUNT) / NULLIF(SUM(LISTING_COUNT), 0) AS ST_GROSS_YIELD_PCT,
            SUM(LT_GROSS_YIELD_PCT * LISTING_COUNT) / NULLIF(SUM(LISTING_COUNT), 0) AS LT_GROSS_YIELD_PCT,
            SUM(ST_VS_LT_INCOME_UPLIFT) AS ST_VS_LT_INCOME_UPLIFT,
            SUM(ST_VS_LT_YIELD_UPLIFT_PPT) AS ST_VS_LT_YIELD_UPLIFT_PPT,
            SUM(ST_TO_LT_INCOME_RATIO) AS ST_TO_LT_INCOME_RATIO

        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_ST_VS_LT

        WHERE
            ST_ANNUAL_INCOME IS NOT NULL
            AND LT_ANNUAL_INCOME IS NOT NULL
            AND LISTING_COUNT > 0

        GROUP BY CITY, NEIGHBOURHOOD

        ORDER BY CITY, NEIGHBOURHOOD
        """
    ).to_pandas()

# SQL QUERY FOR SEASONAL OCCUPANCY
@st.cache_data(ttl=300)
def load_area_seasonal(_session):
    return _session.sql(
        """
        SELECT
            CITY,
            NEIGHBOURHOOD,
            MONTH,
            LISTING_COUNT,
            TOTAL_NIGHTS,
            BOOKED_NIGHTS,
            OCCUPANCY_RATE

        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_SEASONAL

        WHERE
            CITY IS NOT NULL
            AND NEIGHBOURHOOD IS NOT NULL
            AND MONTH IS NOT NULL

        ORDER BY CITY, NEIGHBOURHOOD, MONTH
        """
    ).to_pandas()


# SQL QUERY FOR AREA PERSONA INVESTMENT SCORES
@st.cache_data(ttl=300)
def load_area_persona_scores(_session):
    return _session.sql(
        """
        SELECT
            b.CITY,
            a.NEIGHBOURHOOD,
            AVG(b.SCORE_YIELD_MAXIMISER) AS SCORE_YIELD_MAXIMISER,
            AVG(b.SCORE_OCCUPANCY_OPTIMISER) AS SCORE_OCCUPANCY_OPTIMISER,
            AVG(b.SCORE_QUALITY_HOST) AS SCORE_QUALITY_HOST

        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_LISTING_CANDIDATES a

        INNER JOIN AIRBNB_INVESTMENT_DB.GOLD.INVESTMENT_SCORES b
        
        ON a.LISTING_ID = b.LISTING_ID

        WHERE a.NEIGHBOURHOOD IS NOT NULL AND b.CITY IS NOT NULL

        GROUP BY b.CITY, a.NEIGHBOURHOOD

        ORDER BY b.CITY, a.NEIGHBOURHOOD
        """
    ).to_pandas()

# SQL QUERY FOR POINTS OF INTEREST
@st.cache_data(ttl=300)
def load_area_pois(_session):
    return _session.sql(
        """
        SELECT
            CITY,
            NEIGHBOURHOOD,
            POI_NAME,
            CATEGORY,
            AMENITY_GROUP,
            IS_TRANSPORT,
            IS_DINING,
            LATITUDE,
            LONGITUDE

        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_POI

        WHERE
            CITY IS NOT NULL
            AND NEIGHBOURHOOD IS NOT NULL
            AND POI_NAME IS NOT NULL
            AND AMENITY_GROUP IS NOT NULL
            AND LATITUDE IS NOT NULL
            AND LONGITUDE IS NOT NULL

        ORDER BY
            CITY,
            NEIGHBOURHOOD,
            AMENITY_GROUP,
            POI_NAME
        """
    ).to_pandas()
    
# LOAD DATA
area_persona_scores = load_area_persona_scores(session)

area_strategy = load_area_strategy(session)

area_seasonal = load_area_seasonal(session)

area_pois = load_area_pois(session)

# CREATE DATAFRAME FROM STARRED NEIGHBOURHOODS
selected_areas = pd.DataFrame(
    starred_neighbourhoods
)

selected_areas["NEIGHBOURHOOD_CLEAN"] = (
    selected_areas["neighbourhood"]
    .astype(str)
    .str.strip()
    .str.lower()
)

selected_areas["CITY_CLEAN"] = (
    selected_areas["city"]
    .astype(str)
    .str.strip()
    .str.lower()
)

# PREPARE PERSONA SCORE DATA
area_persona_scores["NEIGHBOURHOOD_CLEAN"] = (
    area_persona_scores["NEIGHBOURHOOD"]
    .astype(str)
    .str.strip()
    .str.lower()
)

area_persona_scores["CITY_CLEAN"] = (
    area_persona_scores["CITY"]
    .astype(str)
    .str.strip()
    .str.lower()
)

comparison_scores = selected_areas.merge(
    area_persona_scores,
    on=[
        "NEIGHBOURHOOD_CLEAN",
        "CITY_CLEAN"
    ],
    how="left"
)


# PREPARE SHORT-TERM AND LONG-TERM STRATEGY DATA
area_strategy["NEIGHBOURHOOD_CLEAN"] = (
    area_strategy["NEIGHBOURHOOD"]
    .astype(str)
    .str.strip()
    .str.lower()
)

area_strategy["CITY_CLEAN"] = (
    area_strategy["CITY"]
    .astype(str)
    .str.strip()
    .str.lower()
)

comparison_strategy = selected_areas.merge(
    area_strategy,
    on=[
        "NEIGHBOURHOOD_CLEAN",
        "CITY_CLEAN"
    ],
    how="left"
)


# PREPARE STRATEGY CHART DATA
strategy_chart_data = comparison_strategy[
    [
        "neighbourhood",
        "city",
        "ST_ANNUAL_REVENUE",
        "LT_ANNUAL_RENT",
        "ST_GROSS_YIELD_PCT",
        "LT_GROSS_YIELD_PCT"
    ]
].copy()

strategy_chart_data["AREA_LABEL"] = (
    strategy_chart_data["neighbourhood"].astype(str)
)

strategy_chart_data[
    [
        "ST_ANNUAL_REVENUE",
        "LT_ANNUAL_RENT",
        "ST_GROSS_YIELD_PCT",
        "LT_GROSS_YIELD_PCT"
    ]
] = strategy_chart_data[
    [
        "ST_ANNUAL_REVENUE",
        "LT_ANNUAL_RENT",
        "ST_GROSS_YIELD_PCT",
        "LT_GROSS_YIELD_PCT"
    ]
].apply(
    pd.to_numeric,
    errors="coerce"
)


# PREPARE SEASONAL OCCUPANCY DATA
area_seasonal["NEIGHBOURHOOD_CLEAN"] = (
    area_seasonal["NEIGHBOURHOOD"]
    .astype(str)
    .str.strip()
    .str.lower()
)

area_seasonal["CITY_CLEAN"] = (
    area_seasonal["CITY"]
    .astype(str)
    .str.strip()
    .str.lower()
)

comparison_seasonal = selected_areas.merge(
    area_seasonal,
    on=[
        "NEIGHBOURHOOD_CLEAN",
        "CITY_CLEAN"
    ],
    how="inner"
)

comparison_seasonal["AREA_LABEL"] = (
    comparison_seasonal["neighbourhood"].astype(str)
)

month_names = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec"
}

comparison_seasonal["MONTH_NAME"] = (
    comparison_seasonal["MONTH"]
    .map(month_names)
)

# PREPARE POINTS OF INTEREST DATA
area_pois["NEIGHBOURHOOD_CLEAN"] = (
    area_pois["NEIGHBOURHOOD"]
    .astype(str)
    .str.strip()
    .str.lower()
)

area_pois["CITY_CLEAN"] = (
    area_pois["CITY"]
    .astype(str)
    .str.strip()
    .str.lower()
)

area_pois["AMENITY_GROUP"] = (
    area_pois["AMENITY_GROUP"]
    .astype(str)
    .str.strip()
)

area_pois["CATEGORY"] = (
    area_pois["CATEGORY"]
    .fillna("Uncategorised")
    .astype(str)
    .str.replace("_", " ", regex=False)
    .str.title()
)

comparison_pois = selected_areas.merge(
    area_pois,
    on=[
        "NEIGHBOURHOOD_CLEAN",
        "CITY_CLEAN"
    ],
    how="inner"
)

#rADAR FUNCTION

# BUILD POI MAP
amenity_group_colours = {
    "Dining & Nightlife": [242, 99, 89, 210],
    "Attractions & Culture": [248, 217, 211, 210],
    "Parks & Green": [120, 190, 120, 210],
    "Education": [102, 153, 255, 210],
    "Fitness": [255, 179, 71, 210],
    "Groceries & Essentials": [153, 102, 204, 210],
    "Health": [90, 180, 172, 210],
    "Transport": [80, 80, 80, 210],
    "Other": [180, 180, 180, 210]
}

def build_poi_map(
    neighbourhood_name,
    city_name,
    neighbourhood_pois
):

    if neighbourhood_pois.empty:
        return None

    map_data = neighbourhood_pois[
        [
            "POI_NAME",
            "CATEGORY",
            "AMENITY_GROUP",
            "IS_TRANSPORT",
            "IS_DINING",
            "LATITUDE",
            "LONGITUDE"
        ]
    ].copy()

    map_data["LATITUDE"] = pd.to_numeric(
        map_data["LATITUDE"],
        errors="coerce"
    )

    map_data["LONGITUDE"] = pd.to_numeric(
        map_data["LONGITUDE"],
        errors="coerce"
    )

    map_data = map_data.dropna(
        subset=[
            "LATITUDE",
            "LONGITUDE"
        ]
    )

    if map_data.empty:
        return None

    map_data["POI_NAME"] = (
        map_data["POI_NAME"]
        .fillna("Unnamed POI")
        .astype(str)
    )

    map_data["CATEGORY"] = (
        map_data["CATEGORY"]
        .fillna("Uncategorised")
        .astype(str)
    )

    map_data["AMENITY_GROUP"] = (
        map_data["AMENITY_GROUP"]
        .fillna("Other")
        .astype(str)
    )

    map_data["TRANSPORT_TEXT"] = map_data["IS_TRANSPORT"].apply(
        lambda value: "Yes" if bool(value) else "No"
    )

    map_data["DINING_TEXT"] = map_data["IS_DINING"].apply(
        lambda value: "Yes" if bool(value) else "No"
    )

    map_data["COLOR"] = map_data["AMENITY_GROUP"].apply(
        lambda group: amenity_group_colours.get(
            group,
            amenity_group_colours["Other"]
        )
    )

    centre_latitude = map_data["LATITUDE"].mean()
    centre_longitude = map_data["LONGITUDE"].mean()

    poi_layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        id=f"poi-points-{city_name}-{neighbourhood_name}",
        get_position=["LONGITUDE", "LATITUDE"],
        get_fill_color="COLOR",
        get_line_color=[0, 0, 0, 255],
        get_radius=45,
        radius_min_pixels=4,
        radius_max_pixels=12,
        stroked=True,
        filled=True,
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True
    )

    view_state = pdk.ViewState(
        latitude=centre_latitude,
        longitude=centre_longitude,
        zoom=12,
        pitch=0
    )

    poi_map = pdk.Deck(
        map_style="light_no_labels",
        layers=[poi_layer],
        initial_view_state=view_state,
        views=[
            pdk.View(
                type="MapView",
                controller={"scrollZoom": False}
            )
        ],
        tooltip={
            "html":
                "<b>{POI_NAME}</b><br/>"
                "Category: {AMENITY_GROUP}<br/>"
                "{CATEGORY}<br/>",
            "style": {
                "backgroundColor": "#FFFFFF",
                "color": "#000000",
                "fontSize": "13px",
                "border": "1px solid #F26359"
            }
        }
    )

    return poi_map

# VISUALISATIONS

# STARRED NEIGHBOURHOODS (hidden when printing)
if not print_mode:
    st.markdown(
        "### Your Starred Neighbourhoods"
    )

    neighbourhood_columns = st.columns(
        3,
        border=True
    )

    for index, neighbourhood in enumerate(
        starred_neighbourhoods[:3]
    ):

        neighbourhood_name = neighbourhood[
            "neighbourhood"
        ]

        city_name = neighbourhood[
            "city"
        ]

        with neighbourhood_columns[index]:

            st.header(
                neighbourhood_name
            )

            st.caption(
                city_name
            )


    st.divider()

# SHORT-TERM VS LONG-TERM STRATEGY
with st.container(
    border=True
):

    st.markdown(
        "### Short-Term vs Long-Term Strategy"
    )

    st.caption(
        "Compare estimated annual income and gross yield for "
        "short-term and long-term investment."
    )

    revenue_chart_data = strategy_chart_data[
        [
            "AREA_LABEL",
            "ST_ANNUAL_REVENUE",
            "LT_ANNUAL_RENT"
        ]
    ].melt(
        id_vars=[
            "AREA_LABEL"
        ],
        value_vars=[
            "ST_ANNUAL_REVENUE",
            "LT_ANNUAL_RENT"
        ],
        var_name="STRATEGY",
        value_name="ANNUAL_INCOME"
    )

    revenue_chart_data["STRATEGY"] = (
        revenue_chart_data["STRATEGY"]
        .replace(
            {
                "ST_ANNUAL_REVENUE": "Short-Term",
                "LT_ANNUAL_RENT": "Long-Term"
            }
        )
    )

    revenue_chart_data = revenue_chart_data.dropna(
        subset=[
            "ANNUAL_INCOME"
        ]
    )


    yield_chart_data = strategy_chart_data[
        [
            "AREA_LABEL",
            "ST_GROSS_YIELD_PCT",
            "LT_GROSS_YIELD_PCT"
        ]
    ].melt(
        id_vars=[
            "AREA_LABEL"
        ],
        value_vars=[
            "ST_GROSS_YIELD_PCT",
            "LT_GROSS_YIELD_PCT"
        ],
        var_name="STRATEGY",
        value_name="GROSS_YIELD"
    )

    yield_chart_data["STRATEGY"] = (
        yield_chart_data["STRATEGY"]
        .replace(
            {
                "ST_GROSS_YIELD_PCT": "Short-Term",
                "LT_GROSS_YIELD_PCT": "Long-Term"
            }
        )
    )

    yield_chart_data = yield_chart_data.dropna(
        subset=[
            "GROSS_YIELD"
        ]
    )


    revenue_col, yield_col = st.columns(
        2,
        gap="medium"
    )


    # ANNUAL REVENUE CHART
    with revenue_col:

        st.markdown(
            "#### Annual Income"
        )

        if revenue_chart_data.empty:

            st.info(
                "No annual income data was found."
            )

        else:

            revenue_chart = (
                alt.Chart(
                    revenue_chart_data
                )
                .mark_bar()
                .encode(
                    x=alt.X(
                        "AREA_LABEL:N",
                        title="",
                        axis=alt.Axis(
                            labelAngle=-25,
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),

                    xOffset=alt.XOffset(
                        "STRATEGY:N"
                    ),

                    y=alt.Y(
                        "ANNUAL_INCOME:Q",
                        title="",
                        axis=alt.Axis(
                            format=",.0f",
                            labelExpr="'£' + format(datum.value, ',.0f')",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),

                    color=alt.Color(
                        "STRATEGY:N",
                        title="Strategy",
                        scale=alt.Scale(
                            domain=[
                                "Short-Term",
                                "Long-Term"
                            ],
                            range=[
                                "#F26359",
                                "#F8D9D3"
                            ]
                        ),
                        legend=alt.Legend(
                            orient="bottom",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),

                    tooltip=[
                        alt.Tooltip(
                            "ANNUAL_INCOME:Q",
                            title="Annual Income (£)",
                            format=",.0f"
                        )
                    ]
                )
                .properties(
                    height=350,
                    background="#FFFFFF"
                )
            )

            st.altair_chart(
                revenue_chart,
                use_container_width=True
            )


# GROSS YIELD CHART
with yield_col:

    st.markdown(
        "#### Gross Yield"
    )

    if yield_chart_data.empty:

        st.info(
            "No gross-yield data was found."
        )

    else:

        yield_chart = (
            alt.Chart(
                yield_chart_data
            )
            .mark_bar()
            .encode(
                x=alt.X(
                    "AREA_LABEL:N",
                    axis=alt.Axis(
                        title="",
                        labelAngle=-25,
                        labelColor="#000000",
                        titleColor="#000000"
                    )
                ),

                xOffset=alt.XOffset(
                    "STRATEGY:N"
                ),

                y=alt.Y(
                    "GROSS_YIELD:Q",
                    scale=alt.Scale(
                        zero=True
                    ),
                    axis=alt.Axis(
                        title="",
                        format=".1f",
                        labelExpr="datum.label + '%'",
                        labelColor="#000000",
                        titleColor="#000000"
                    )
                ),

                color=alt.Color(
                    "STRATEGY:N",
                    title="Strategy",
                    scale=alt.Scale(
                        domain=[
                            "Short-Term",
                            "Long-Term"
                        ],
                        range=[
                            "#F26359",
                            "#F8D9D3"
                        ]
                    ),
                    legend=alt.Legend(
                        orient="bottom",
                        labelColor="#000000",
                        titleColor="#000000"
                    )
                ),

                tooltip=[
                    alt.Tooltip(
                        "GROSS_YIELD:Q",
                        title="Gross Yield (%)",
                        format=".2f"
                    )
                ]
            )
            .properties(
                height=350,
                background="#FFFFFF"
            )
        )

        st.altair_chart(
            yield_chart,
            use_container_width=True
        )

# SEASONAL OCCUPANCY PATTERN
occupancy_col, ai_col =st.columns([1,1])

with occupancy_col:
    with st.container(
        border=True
    ):
    
        st.markdown(
            "### Seasonal Occupancy Pattern"
        )
    
        st.caption(
            "Compare monthly occupancy patterns across the "
            "3 selected neighbourhoods."
        )
    
        if comparison_seasonal.empty:
    
            st.info(
                "No seasonal occupancy data was found for the "
                "selected neighbourhoods."
            )
    
        else:
    
            occupancy_chart = (
                alt.Chart(
                    comparison_seasonal
                )
                .mark_line(
                    point=True,
                    strokeWidth=3
                )
                .encode(
                    x=alt.X(
                        "MONTH_NAME:N",
                        title="Month",
                        sort=[
                            "Jan",
                            "Feb",
                            "Mar",
                            "Apr",
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec"
                        ],
                        axis=alt.Axis(
                            labelAngle=0,
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
    
                    y=alt.Y(
                        "OCCUPANCY_RATE:Q",
                        title="Occupancy Rate",
                        scale=alt.Scale(
                            domain=[
                                0,
                                1
                            ]
                        ),
                        axis=alt.Axis(
                            format=".0%",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
    
                    color=alt.Color(
                        "AREA_LABEL:N",
                        title="Neighbourhood",
                        scale=alt.Scale(
                            range=[
                                "#F26359",
                                "#7A2E2A",
                                "#F5A097"
                            ]
                        ),
                        legend=alt.Legend(
                            orient="bottom",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
    
                    tooltip=[
                        alt.Tooltip(
                            "OCCUPANCY_RATE:Q",
                            title="Occupancy Rate",
                            format=".1%"
                        ),
    
                        alt.Tooltip(
                            "BOOKED_NIGHTS:Q",
                            title="Booked Nights",
                            format=",.0f"
                        ),
    
                        alt.Tooltip(
                            "TOTAL_NIGHTS:Q",
                            title="Total Nights",
                            format=",.0f"
                        )
                    ]
                )
                .properties(
                    height=350,
                    background="#FFFFFF"
                )
            )
    
            st.altair_chart(
                occupancy_chart,
                use_container_width=True
            )

#AI SUMMARY
#with ai_col:
    

st.divider()

# In print mode, only the charts above are shown: auto-open the browser
# print dialog once they have rendered, then stop before the POI section.
if print_mode:
    html(
        "<script>setTimeout(function(){ window.parent.print(); }, 1200);</script>",
        height=0
    )
    st.stop()

# POINTS OF INTEREST MAPS
st.markdown(
    "## Points of Interest"
)

st.caption(
    "Select one or more categories to compare nearby points "
    "of interest across your 3 starred neighbourhoods."
)


# AVAILABLE POI GROUPS
available_amenity_groups = sorted(
    comparison_pois["AMENITY_GROUP"]
    .dropna()
    .astype(str)
    .unique()
    .tolist()
)


# SHARED MULTI-SELECT FILTER
selected_amenity_groups = st.multiselect(
    "Category",
    options=available_amenity_groups,
    default=available_amenity_groups,
    placeholder="Select one or more POI types"
)

st.caption("**Tip: Click fullscreen for better analysis of each neighbourhood**"
)

#LEGEND
if selected_amenity_groups:

    legend_html = ""

    for group in selected_amenity_groups:
        colour = amenity_group_colours.get(
            group,
            amenity_group_colours["Other"]
        )

        rgba_colour = f"rgba({colour[0]}, {colour[1]}, {colour[2]}, {colour[3] / 255})"

        legend_html += f"""
            <div style="
                display: inline-flex;
                align-items: center;
                margin-right: 18px;
                margin-bottom: 10px;
            ">
                <div style="
                    width: 14px;
                    height: 14px;
                    border-radius: 50%;
                    background-color: {rgba_colour};
                    border: 1px solid black;
                    margin-right: 8px;
                "></div>
                <span style="font-size: 14px; color: black;">{group}</span>
            </div>
        """

    st.markdown(
        legend_html,
        unsafe_allow_html=True
    )

if len(selected_amenity_groups) == 0:

    st.info(
        "Select at least one POI type to display the maps."
    )

else:

    filtered_comparison_pois = comparison_pois[
        comparison_pois["AMENITY_GROUP"].isin(
            selected_amenity_groups
        )
    ].copy()


    poi_map_columns = st.columns(
        3,
        gap="medium"
    )


    for index, neighbourhood in enumerate(
        starred_neighbourhoods[:3]
    ):

        neighbourhood_name = neighbourhood[
            "neighbourhood"
        ]

        city_name = neighbourhood[
            "city"
        ]

        neighbourhood_clean = (
            str(neighbourhood_name)
            .strip()
            .lower()
        )

        city_clean = (
            str(city_name)
            .strip()
            .lower()
        )

        neighbourhood_pois = filtered_comparison_pois[
            (
                filtered_comparison_pois[
                    "NEIGHBOURHOOD_CLEAN"
                ] == neighbourhood_clean
            )
            & (
                filtered_comparison_pois[
                    "CITY_CLEAN"
                ] == city_clean
            )
        ].copy()


        with poi_map_columns[index]:

            with st.container(
                border=True
            ):

                st.markdown(
                    f"### {neighbourhood_name}"
                )

                st.caption(
                    city_name
                )

                st.caption(
                    f"{len(neighbourhood_pois):,} POIs shown"
                )

                if neighbourhood_pois.empty:

                    st.info(
                        "No POIs were found for the selected "
                        "amenity groups."
                    )

                else:

                    poi_map = build_poi_map(
                        neighbourhood_name,
                        city_name,
                        neighbourhood_pois
                    )

                    if poi_map is None:

                        st.info(
                            "No valid POI coordinates were found."
                        )

                    else:

                        st.caption(
                            "Hover over a point to view its details."
                        )

                        st.pydeck_chart(
                            poi_map,
                            height=450,
                            use_container_width=True,
                            key=(
                                f"poi_map_"
                                f"{index}_"
                                f"{city_name}_"
                                f"{neighbourhood_name}"
                            )
                        )