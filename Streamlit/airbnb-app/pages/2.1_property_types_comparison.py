# Property Types Comparison page: charts + persona-based AI comparison across 3 starred property/bedroom picks.
# Co-authored with CoCo
import os
import sys
import json

import streamlit as st
import pandas as pd
import altair as alt
from streamlit.components.v1 import html
from db import get_session
from nav import render_logo

# Make the repo's shared AI helpers importable (scripts/ai lives outside the app dir).
_SCRIPTS_AI = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "ai")
)
if _SCRIPTS_AI not in sys.path:
    sys.path.insert(0, _SCRIPTS_AI)
import property_types_comparison_helper as ptch

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

    /* Make bordered Streamlit containers printable.
       Do NOT force break-inside: avoid on the whole wrapper — a tall
       container that cannot fit on a page pushes to the next page and
       leaves large whitespace. Page breaks are controlled per-chart below. */
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        background: #ffffff !important;
        background-color: #ffffff !important;
        border-color: #b0b0b0 !important;
        box-shadow: none !important;
        display: block !important;
    }

    /* Stack columns vertically so each chart prints full width instead of
       being squeezed into narrow side-by-side halves that overflow. */
    [data-testid="stHorizontalBlock"] {
        display: block !important;
        width: 100% !important;
    }

    [data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
        display: block !important;
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

# Explicit chart dimensions for print/PDF export. In print mode columns are
# stacked full width (see @media print CSS), so every chart uses a single wide,
# fixed size that fits A4 landscape cleanly instead of scaling to screen width.
PRINT_CHART_WIDTH = 950
PRINT_CHART_HEIGHT = 300

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
        if st.button("Back to Property Types", use_container_width=True):
            st.switch_page(
                "pages/2_property_types.py")

    with print_col:
        if st.button("Print", use_container_width=True):
            st.query_params["print"] = "1"
            st.rerun()

session = get_session()

# FORMAT FUNCTIONS
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


# SESSION STATE
if "starred_property_types" not in st.session_state:
    st.session_state["starred_property_types"] = []

starred_property_types = st.session_state["starred_property_types"]

if len(starred_property_types) != 3:
    st.warning(
        "Exactly 3 property and bedroom combinations must be starred "
        "before generating this comparison."
    )
    st.stop()

required_starred_fields = [
    "city",
    "neighbourhood",
    "structure_class",
    "bedroom_group"
]

if any(
    field not in item
    for item in starred_property_types
    for field in required_starred_fields
):
    st.warning(
        "Your current starred selections were created before structure "
        "class and bedroom bucket were added. Clear them, return to the "
        "Property Types page and star the 3 options again."
    )
    st.stop()

session = get_session()

# SQL QUERY FOR SHORT-TERM VS LONG-TERM STRATEGY
@st.cache_data(ttl=300)
def load_property_strategy(_session):
    return _session.sql(
        """
        SELECT
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_BUCKET,
            BEDROOM_SORT,
            LISTING_COUNT,
            OCCUPANCY_CAP_NIGHTS,
            MEDIAN_SALE_PRICE,
            ST_ANNUAL_INCOME,
            ST_GROSS_YIELD_PCT,
            ASSUMED_LT_GROSS_YIELD_PCT,
            LT_ANNUAL_INCOME,
            LT_GROSS_YIELD_PCT,
            LT_RENT_SOURCE,
            ST_VS_LT_INCOME_UPLIFT,
            ST_VS_LT_YIELD_UPLIFT_PPT,
            ST_TO_LT_INCOME_RATIO,
            ST_WINS,
            SUFFICIENT_SAMPLE
        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_ST_VS_LT
        WHERE
            CITY IS NOT NULL
            AND NEIGHBOURHOOD IS NOT NULL
            AND STRUCTURE_CLASS IS NOT NULL
            AND BEDROOM_BUCKET IS NOT NULL
        ORDER BY
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_SORT
        """
    ).to_pandas()

# SQL QUERY FOR PROPERTY-LEVEL SEASONAL OCCUPANCY
@st.cache_data(ttl=300)
def load_property_seasonal(_session):
    return _session.sql(
        """
        SELECT
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_BUCKET,
            BEDROOM_SORT,
            MONTH,
            LISTING_COUNT,
            TOTAL_NIGHTS,
            BOOKED_NIGHTS,
            OCCUPANCY_RATE,
            SUFFICIENT_SAMPLE
        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_PROPERTY_SEASONAL
        WHERE
            CITY IS NOT NULL
            AND NEIGHBOURHOOD IS NOT NULL
            AND STRUCTURE_CLASS IS NOT NULL
            AND BEDROOM_BUCKET IS NOT NULL
            AND MONTH IS NOT NULL
        ORDER BY
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            BEDROOM_SORT,
            MONTH
        """
    ).to_pandas()

property_strategy = load_property_strategy(session)
property_seasonal = load_property_seasonal(session)

# PREPARE THE 3 STARRED OPTIONS
selected_properties = pd.DataFrame(starred_property_types[:3]).copy()

for source_column, clean_column in [
    ("city", "CITY_CLEAN"),
    ("neighbourhood", "NEIGHBOURHOOD_CLEAN"),
    ("structure_class", "STRUCTURE_CLASS_CLEAN"),
    ("bedroom_group", "BEDROOM_BUCKET_CLEAN")
]:
    selected_properties[clean_column] = (
        selected_properties[source_column]
        .astype(str)
        .str.strip()
        .str.lower()
    )

selected_properties["PROPERTY_LABEL"] = (
    selected_properties["structure_class"].astype(str)
    + " — "
    + selected_properties["bedroom_group"].astype(str)
    + " bedroom"
    + "\n"
    + selected_properties["neighbourhood"].astype(str)
)

selected_properties["FULL_LABEL"] = (
    selected_properties["structure_class"].astype(str)
    + " — "
    + selected_properties["bedroom_group"].astype(str)
    + " bedroom, "
    + selected_properties["neighbourhood"].astype(str)
    + ", "
    + selected_properties["city"].astype(str)
)

# PREPARE MART_ST_VS_LT
for source_column, clean_column in [
    ("CITY", "CITY_CLEAN"),
    ("NEIGHBOURHOOD", "NEIGHBOURHOOD_CLEAN"),
    ("STRUCTURE_CLASS", "STRUCTURE_CLASS_CLEAN"),
    ("BEDROOM_BUCKET", "BEDROOM_BUCKET_CLEAN")
]:
    property_strategy[clean_column] = (
        property_strategy[source_column]
        .astype(str)
        .str.strip()
        .str.lower()
    )

comparison_strategy = selected_properties.merge(
    property_strategy,
    on=[
        "CITY_CLEAN",
        "NEIGHBOURHOOD_CLEAN",
        "STRUCTURE_CLASS_CLEAN",
        "BEDROOM_BUCKET_CLEAN"
    ],
    how="left",
    suffixes=("", "_STRATEGY")
)

strategy_columns = [
    "ST_ANNUAL_INCOME",
    "LT_ANNUAL_INCOME",
    "ST_GROSS_YIELD_PCT",
    "LT_GROSS_YIELD_PCT"
]
comparison_strategy[strategy_columns] = comparison_strategy[strategy_columns].apply(
    pd.to_numeric,
    errors="coerce"
)

# PREPARE MART_PROPERTY_SEASONAL
for source_column, clean_column in [
    ("CITY", "CITY_CLEAN"),
    ("NEIGHBOURHOOD", "NEIGHBOURHOOD_CLEAN"),
    ("STRUCTURE_CLASS", "STRUCTURE_CLASS_CLEAN"),
    ("BEDROOM_BUCKET", "BEDROOM_BUCKET_CLEAN")
]:
    property_seasonal[clean_column] = (
        property_seasonal[source_column]
        .astype(str)
        .str.strip()
        .str.lower()
    )

comparison_seasonal = selected_properties.merge(
    property_seasonal,
    on=[
        "CITY_CLEAN",
        "NEIGHBOURHOOD_CLEAN",
        "STRUCTURE_CLASS_CLEAN",
        "BEDROOM_BUCKET_CLEAN"
    ],
    how="inner",
    suffixes=("", "_SEASONAL")
)

month_names = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}
comparison_seasonal["MONTH_NAME"] = comparison_seasonal["MONTH"].map(month_names)

# PAGE TITLE AND SELECTED PROPERTY CARDS (hidden when printing)
if not print_mode:
    st.title("Property Types Comparison")
    st.subheader(
        "Compare short-term and long-term performance and seasonal occupancy "
        "across your 3 selected property and bedroom combinations."
    )

    st.markdown("### Your Starred Property Types")
    property_columns = st.columns(3, border=True)

    for index, property_item in selected_properties.iterrows():
        with property_columns[index]:
            st.header(property_item["structure_class"])
            st.markdown(f"**Bedrooms: {property_item['bedroom_group']}**")
            st.write(property_item["neighbourhood"])
            st.caption(property_item["city"])

    st.divider()

# SHORT-TERM VS LONG-TERM STRATEGY
with st.container(border=True):
    st.markdown("### Short-Term vs Long-Term Strategy")
    st.caption(
        "Compare estimated annual income and gross yield for short-term "
        "and long-term investment."
    )

    revenue_chart_data = comparison_strategy[
        ["PROPERTY_LABEL", "FULL_LABEL", "ST_ANNUAL_INCOME", "LT_ANNUAL_INCOME"]
    ].melt(
        id_vars=["PROPERTY_LABEL", "FULL_LABEL"],
        value_vars=["ST_ANNUAL_INCOME", "LT_ANNUAL_INCOME"],
        var_name="STRATEGY",
        value_name="ANNUAL_INCOME"
    )
    revenue_chart_data["STRATEGY"] = revenue_chart_data["STRATEGY"].replace({
        "ST_ANNUAL_INCOME": "Short-Term",
        "LT_ANNUAL_INCOME": "Long-Term"
    })
    revenue_chart_data = revenue_chart_data.dropna(subset=["ANNUAL_INCOME"])

    yield_chart_data = comparison_strategy[
        ["PROPERTY_LABEL", "FULL_LABEL", "ST_GROSS_YIELD_PCT", "LT_GROSS_YIELD_PCT"]
    ].melt(
        id_vars=["PROPERTY_LABEL", "FULL_LABEL"],
        value_vars=["ST_GROSS_YIELD_PCT", "LT_GROSS_YIELD_PCT"],
        var_name="STRATEGY",
        value_name="GROSS_YIELD"
    )
    yield_chart_data["STRATEGY"] = yield_chart_data["STRATEGY"].replace({
        "ST_GROSS_YIELD_PCT": "Short-Term",
        "LT_GROSS_YIELD_PCT": "Long-Term"
    })
    yield_chart_data = yield_chart_data.dropna(subset=["GROSS_YIELD"])

    revenue_col, yield_col = st.columns(2, gap="medium")

    with revenue_col:
        st.markdown("#### Annual Income")
        if revenue_chart_data.empty:
            st.info("No annual income data was found for the selected options.")
        else:
            revenue_chart = (
                alt.Chart(revenue_chart_data)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "PROPERTY_LABEL:N",
                        title="Property Type",
                        axis=alt.Axis(
                            labelAngle=-25,
                            labelColor="#000000",
                            titleColor="#000000",
                            labelLimit=180
                        )
                    ),
                    xOffset=alt.XOffset("STRATEGY:N"),
                    y=alt.Y(
                        "ANNUAL_INCOME:Q",
                        title="Annual Income (£)",
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
                            domain=["Short-Term", "Long-Term"],
                            range=["#F26359", "#F8D9D3"]
                        ),
                        legend=alt.Legend(
                            orient="bottom",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    tooltip=[
                        alt.Tooltip("FULL_LABEL:N", title="Property Type"),
                        alt.Tooltip("STRATEGY:N", title="Strategy"),
                        alt.Tooltip(
                            "ANNUAL_INCOME:Q",
                            title="Annual Income (£)",
                            format=",.0f"
                        )
                    ]
                )
                .properties(height=PRINT_CHART_HEIGHT if print_mode else 350, background="#FFFFFF")
            )
            if print_mode:
                revenue_chart = revenue_chart.properties(width=PRINT_CHART_WIDTH)
            st.altair_chart(revenue_chart, use_container_width=not print_mode)

    with yield_col:
        st.markdown("#### Gross Yield")
        if yield_chart_data.empty:
            st.info("No gross-yield data was found for the selected options.")
        else:
            yield_chart = (
                alt.Chart(yield_chart_data)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "PROPERTY_LABEL:N",
                        title="Property Type",
                        axis=alt.Axis(
                            labelAngle=-25,
                            labelColor="#000000",
                            titleColor="#000000",
                            labelLimit=180
                        )
                    ),
                    xOffset=alt.XOffset("STRATEGY:N"),
                    y=alt.Y(
                        "GROSS_YIELD:Q",
                        title="Gross Yield (%)",
                        scale=alt.Scale(zero=True),
                        axis=alt.Axis(
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
                            domain=["Short-Term", "Long-Term"],
                            range=["#F26359", "#F8D9D3"]
                        ),
                        legend=alt.Legend(
                            orient="bottom",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    tooltip=[
                        alt.Tooltip("FULL_LABEL:N", title="Property Type"),
                        alt.Tooltip("STRATEGY:N", title="Strategy"),
                        alt.Tooltip(
                            "GROSS_YIELD:Q",
                            title="Gross Yield (%)",
                            format=".2f"
                        )
                    ]
                )
                .properties(height=PRINT_CHART_HEIGHT if print_mode else 350, background="#FFFFFF")
            )
            if print_mode:
                yield_chart = yield_chart.properties(width=PRINT_CHART_WIDTH)
            st.altair_chart(yield_chart, use_container_width=not print_mode)

st.divider()

# SEASONAL OCCUPANCY
occupancy_col, ai_col =st.columns([1,1])

with occupancy_col:
    with st.container(border=True):
        st.markdown("### Seasonal Occupancy Pattern")
        st.caption(
            "Compare monthly occupancy across the 3 selected property and "
            "bedroom combinations."
        )
    
        if comparison_seasonal.empty:
            st.info("No seasonal occupancy data was found for the selected options.")
        else:
            occupancy_chart = (
                alt.Chart(comparison_seasonal)
                .mark_line(point=True, strokeWidth=3)
                .encode(
                    x=alt.X(
                        "MONTH_NAME:N",
                        title="Month",
                        sort=[
                            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
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
                        scale=alt.Scale(domain=[0, 1]),
                        axis=alt.Axis(
                            format=".0%",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    color=alt.Color(
                        "PROPERTY_LABEL:N",
                        title="Property Type",
                        scale=alt.Scale(
                            range=["#F26359", "#7A2E2A", "#F5A097"]
                        ),
                        legend=alt.Legend(
                            orient="bottom",
                            labelColor="#000000",
                            titleColor="#000000",
                            labelLimit=300
                        )
                    ),
                    tooltip=[
                        alt.Tooltip("FULL_LABEL:N", title="Property Type"),
                        alt.Tooltip("MONTH_NAME:N", title="Month"),
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
                        ),
                        alt.Tooltip(
                            "LISTING_COUNT:Q",
                            title="Listings",
                            format=",.0f"
                        ),
                        alt.Tooltip(
                            "SUFFICIENT_SAMPLE:N",
                            title="Sufficient Sample"
                        )
                    ]
                )
                .properties(height=PRINT_CHART_HEIGHT if print_mode else 400, background="#FFFFFF")
            )
            if print_mode:
                occupancy_chart = occupancy_chart.properties(width=PRINT_CHART_WIDTH)
            st.altair_chart(occupancy_chart, use_container_width=not print_mode)

#AI SUMMARY
# In-memory cache (per running app) layered on the persistent Snowflake
# PROPERTY_COMPARISON_CACHE table. Leading-underscore args are skipped by
# Streamlit's hasher; combos is a tuple so it hashes.
@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_comparison(_session, _api_key, city, combos, persona):
    selections = [
        {"neighbourhood": n, "structure_class": s, "bedroom_bucket": b}
        for (n, s, b) in combos
    ]
    return ptch.get_or_generate_comparison(
        _session,
        _api_key,
        city,
        selections,
        persona,
    )


st.divider()

with st.container(border=True):

    st.markdown("### AI Comparison: Property Types")

    st.caption(
        "Persona-based short-term vs long-term and seasonality summary "
        "across your 3 selected property and bedroom combinations."
    )

    persona = st.session_state.get("persona")
    api_key = st.secrets.get("gemini", {}).get("api_key")

    comparison_city = starred_property_types[0]["city"]
    comparison_combos = tuple(
        (
            str(item["neighbourhood"]),
            str(item["structure_class"]),
            str(item["bedroom_group"]),
        )
        for item in starred_property_types[:3]
    )

    if persona is None:
        if not print_mode:
            st.info("Select a persona on the landing page to enable the AI summary.")
    elif not api_key:
        if not print_mode:
            st.info("Add a [gemini] api_key to secrets to enable the AI summary.")
    else:
        # Auto-generate in print mode so the AI summary lands in the PDF
        # without a manual click (buttons are hidden when printing).
        if print_mode or st.button("Generate AI summary", use_container_width=True):

            try:
                with st.spinner("Generating AI comparison..."):
                    narrative_json = get_cached_comparison(
                        session,
                        api_key,
                        comparison_city,
                        comparison_combos,
                        persona.upper(),
                    )
            except Exception as e:
                narrative_json = None
                st.error(f"AI comparison failed: {e}")

            if narrative_json is None:
                st.info(
                    "Not enough comparable data for these combinations "
                    "to generate a summary."
                )
            else:
                try:
                    data = json.loads(narrative_json)
                except (ValueError, TypeError):
                    data = None

                if data is None:
                    st.write(narrative_json)
                else:
                    st.write(data.get("comparison_summary", ""))

                    best = data.get("best_combination")
                    if best:
                        st.markdown(f"**Best fit: {best}**")
                        st.write(data.get("best_combination_reason", ""))

                    if data.get("st_vs_lt_insight"):
                        st.markdown("**Short-term vs long-term**")
                        st.write(data["st_vs_lt_insight"])

                    if data.get("seasonality_verdict"):
                        st.markdown("**Seasonal trend**")
                        st.write(data["seasonality_verdict"])

                    if data.get("what_to_avoid"):
                        st.markdown("**What to avoid**")
                        st.write(data["what_to_avoid"])

# In print mode only the labeled charts and the AI summary are shown: open the
# browser print dialog once they have fully rendered (the AI text is generated
# synchronously above, so it is already in the DOM), then stop.
if print_mode:
    html(
        "<script>setTimeout(function(){ window.parent.print(); }, 1800);</script>",
        height=0
    )
    st.stop()
    