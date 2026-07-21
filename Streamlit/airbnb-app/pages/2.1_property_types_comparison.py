import streamlit as st
import os
import pydeck as pdk
import json
import pandas as pd
import altair as alt
import numpy as np
from snowflake.snowpark.functions import st_x, st_y
from db import get_session

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
    </style>
    """,
    unsafe_allow_html=True
)

page_col1, empty_col = st.columns([1,7])
with page_col1:
    if st.button('Back to Property Types Overview', use_container_width = True):
        st.switch_page('pages/2_property_types.py')

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
        "Exactly 3 property types must be starred before generating "
        "the property types comparison."
    )
    st.stop()

session = get_session()


# SQL QUERY FOR SHORT-TERM AND LONG-TERM STRATEGY
@st.cache_data(ttl=300)
def load_property_type_strategy(_session):
    return _session.sql(
        """
        SELECT
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS,
            SUM(LISTING_COUNT) AS LISTING_COUNT,
            SUM(
                ST_ANNUAL_REVENUE * LISTING_COUNT
            ) / NULLIF(
                SUM(LISTING_COUNT),
                0
            ) AS ST_ANNUAL_REVENUE,
            SUM(
                LT_ANNUAL_RENT * LISTING_COUNT
            ) / NULLIF(
                SUM(LISTING_COUNT),
                0
            ) AS LT_ANNUAL_RENT,
            SUM(
                ST_GROSS_YIELD_PCT * LISTING_COUNT
            ) / NULLIF(
                SUM(LISTING_COUNT),
                0
            ) AS ST_GROSS_YIELD_PCT,
            SUM(
                LT_GROSS_YIELD_PCT * LISTING_COUNT
            ) / NULLIF(
                SUM(LISTING_COUNT),
                0
            ) AS LT_GROSS_YIELD_PCT

        FROM AIRBNB_INVESTMENT_DB.GOLD.MART_AREA_STRATEGY

        WHERE
            YIELD_COMPARABLE = TRUE
            AND CITY IS NOT NULL
            AND NEIGHBOURHOOD IS NOT NULL
            AND ST_ANNUAL_REVENUE IS NOT NULL
            AND LT_ANNUAL_RENT IS NOT NULL
            AND STRUCTURE_CLASS IS NOT NULL
            AND LISTING_COUNT > 0

        GROUP BY
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS

        ORDER BY
            CITY,
            NEIGHBOURHOOD,
            STRUCTURE_CLASS
        """
    ).to_pandas()


# CREATE DATAFRAME FROM THE 3 STARRED PROPERTY TYPES
comparison_data = pd.DataFrame(starred_property_types[:3]).copy()

required_columns = [
    "property_group",
    "neighbourhood",
    "city",
    "listing_count",
    "investment_score",
    "average_adr",
    "median_adr",
    "average_annual_revenue",
    "median_annual_revenue",
    "average_occupancy_rate",
    "average_rating",
    "average_bedrooms",
    "median_sale_price",
    "sale_txn_count"
]

for column in required_columns:
    if column not in comparison_data.columns:
        comparison_data[column] = pd.NA

numeric_columns = [
    "listing_count",
    "investment_score",
    "average_adr",
    "median_adr",
    "average_annual_revenue",
    "median_annual_revenue",
    "average_occupancy_rate",
    "average_rating",
    "average_bedrooms",
    "median_sale_price",
    "sale_txn_count"
]

comparison_data[numeric_columns] = comparison_data[numeric_columns].apply(
    pd.to_numeric,
    errors="coerce"
)

# Some datasets store occupancy as 0-1 and others as 0-100.
# Convert to a percentage only when values appear to be proportions.
non_null_occupancy = comparison_data["average_occupancy_rate"].dropna()

if (
    not non_null_occupancy.empty
    and non_null_occupancy.max() <= 1
):
    comparison_data["occupancy_percent"] = (
        comparison_data["average_occupancy_rate"] * 100
    )
else:
    comparison_data["occupancy_percent"] = (
        comparison_data["average_occupancy_rate"]
    )

comparison_data["gross_yield_percent"] = (
    comparison_data["median_annual_revenue"]
    / comparison_data["median_sale_price"].replace(0, pd.NA)
    * 100
)

comparison_data["property_label"] = (
    comparison_data["property_group"].astype(str)
    + "\n"
    + comparison_data["neighbourhood"].astype(str)
)

comparison_data["full_label"] = (
    comparison_data["property_group"].astype(str)
    + " — "
    + comparison_data["neighbourhood"].astype(str)
    + ", "
    + comparison_data["city"].astype(str)
)


# MAP DETAILED PROPERTY GROUPS TO THE BROADER STRATEGY CLASSES
def normalise_structure_class(value):
    value_clean = (
        str(value)
        .strip()
        .lower()
    )

    if "house" in value_clean:
        return "house"

    if (
        "flat" in value_clean
        or "apartment" in value_clean
    ):
        return "flat"

    return "others"


def map_property_group_to_structure_class(property_group):
    return normalise_structure_class(
        property_group
    )


comparison_data["CITY_CLEAN"] = (
    comparison_data["city"]
    .astype(str)
    .str.strip()
    .str.lower()
)

comparison_data["NEIGHBOURHOOD_CLEAN"] = (
    comparison_data["neighbourhood"]
    .astype(str)
    .str.strip()
    .str.lower()
)

comparison_data["STRUCTURE_CLASS_CLEAN"] = (
    comparison_data["property_group"]
    .apply(map_property_group_to_structure_class)
)


# LOAD AND PREPARE SHORT-TERM / LONG-TERM STRATEGY DATA
property_type_strategy = load_property_type_strategy(
    session
)

property_type_strategy["CITY_CLEAN"] = (
    property_type_strategy["CITY"]
    .astype(str)
    .str.strip()
    .str.lower()
)

property_type_strategy["NEIGHBOURHOOD_CLEAN"] = (
    property_type_strategy["NEIGHBOURHOOD"]
    .astype(str)
    .str.strip()
    .str.lower()
)

property_type_strategy["STRUCTURE_CLASS_CLEAN"] = (
    property_type_strategy["STRUCTURE_CLASS"]
    .apply(normalise_structure_class)
)

comparison_strategy = comparison_data.merge(
    property_type_strategy,
    on=[
        "CITY_CLEAN",
        "NEIGHBOURHOOD_CLEAN",
        "STRUCTURE_CLASS_CLEAN"
    ],
    how="left",
    suffixes=("", "_STRATEGY")
)

strategy_numeric_columns = [
    "ST_ANNUAL_REVENUE",
    "LT_ANNUAL_RENT",
    "ST_GROSS_YIELD_PCT",
    "LT_GROSS_YIELD_PCT"
]

comparison_strategy[strategy_numeric_columns] = (
    comparison_strategy[strategy_numeric_columns]
    .apply(
        pd.to_numeric,
        errors="coerce"
    )
)

strategy_chart_data = comparison_strategy[
    [
        "property_label",
        "full_label",
        "ST_ANNUAL_REVENUE",
        "LT_ANNUAL_RENT",
        "ST_GROSS_YIELD_PCT",
        "LT_GROSS_YIELD_PCT"
    ]
].copy()


# PAGE TITLE
st.title("Property Types Comparison")

st.subheader(
    "Compare the performance of your 3 starred property types "
    "across investment, revenue, demand, quality and market metrics."
)


# STARRED PROPERTY TYPE CARDS
st.markdown("### Your Starred Property Types")

property_columns = st.columns(
    3,
    border=True
)

for index, property_item in comparison_data.iterrows():

    with property_columns[index]:
        st.header(property_item["property_group"])
        st.write(property_item["neighbourhood"])
        st.caption(property_item["city"])

        st.metric(
            "Investment Score",
            format_decimal(
                property_item["investment_score"]
            )
        )

        st.metric(
            "Median Annual Revenue",
            format_money(
                property_item["median_annual_revenue"]
            )
        )

        st.metric(
            "Occupancy Rate",
            format_percent(
                property_item["occupancy_percent"]
            )
        )

st.divider()


# SHORT-TERM VS LONG-TERM STRATEGY
with st.container(border=True):

    st.markdown("### Short-Term vs Long-Term Strategy")

    st.caption(
        "Compare estimated annual income and gross yield for "
        "short-term and long-term investment."
    )

    st.caption(
        "Strategy figures use the broader structure classes House, "
        "Flat and Others. Detailed property types mapped to Others "
        "share the same strategy-level estimates within a neighbourhood."
    )

    revenue_chart_data = strategy_chart_data[
        [
            "property_label",
            "full_label",
            "ST_ANNUAL_REVENUE",
            "LT_ANNUAL_RENT"
        ]
    ].melt(
        id_vars=[
            "property_label",
            "full_label"
        ],
        value_vars=[
            "ST_ANNUAL_REVENUE",
            "LT_ANNUAL_RENT"
        ],
        var_name="strategy",
        value_name="annual_income"
    )

    revenue_chart_data["strategy"] = (
        revenue_chart_data["strategy"]
        .replace(
            {
                "ST_ANNUAL_REVENUE": "Short-Term",
                "LT_ANNUAL_RENT": "Long-Term"
            }
        )
    )

    revenue_chart_data = revenue_chart_data.dropna(
        subset=["annual_income"]
    )

    yield_chart_data = strategy_chart_data[
        [
            "property_label",
            "full_label",
            "ST_GROSS_YIELD_PCT",
            "LT_GROSS_YIELD_PCT"
        ]
    ].melt(
        id_vars=[
            "property_label",
            "full_label"
        ],
        value_vars=[
            "ST_GROSS_YIELD_PCT",
            "LT_GROSS_YIELD_PCT"
        ],
        var_name="strategy",
        value_name="gross_yield"
    )

    yield_chart_data["strategy"] = (
        yield_chart_data["strategy"]
        .replace(
            {
                "ST_GROSS_YIELD_PCT": "Short-Term",
                "LT_GROSS_YIELD_PCT": "Long-Term"
            }
        )
    )

    yield_chart_data = yield_chart_data.dropna(
        subset=["gross_yield"]
    )

    revenue_col, yield_col = st.columns(
        2,
        gap="medium"
    )

    with revenue_col:

        st.markdown("#### Annual Income")

        if revenue_chart_data.empty:
            st.info(
                "No comparable short-term and long-term annual "
                "income data was found."
            )

        else:
            revenue_chart = (
                alt.Chart(revenue_chart_data)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "property_label:N",
                        title="",
                        axis=alt.Axis(
                            labelAngle=-20,
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    xOffset=alt.XOffset(
                        "strategy:N"
                    ),
                    y=alt.Y(
                        "annual_income:Q",
                        title="",
                        axis=alt.Axis(
                            format=",.0f",
                            labelExpr="'£' + format(datum.value, ',.0f')",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    color=alt.Color(
                        "strategy:N",
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
                            "full_label:N",
                            title="Property Type"
                        ),
                        alt.Tooltip(
                            "strategy:N",
                            title="Strategy"
                        ),
                        alt.Tooltip(
                            "annual_income:Q",
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

    with yield_col:

        st.markdown("#### Gross Yield")

        if yield_chart_data.empty:
            st.info(
                "No comparable short-term and long-term gross-yield "
                "data was found."
            )

        else:
            yield_chart = (
                alt.Chart(yield_chart_data)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "property_label:N",
                        title="",
                        axis=alt.Axis(
                            labelAngle=-20,
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    xOffset=alt.XOffset(
                        "strategy:N"
                    ),
                    y=alt.Y(
                        "gross_yield:Q",
                        title="",
                        scale=alt.Scale(
                            zero=True
                        ),
                        axis=alt.Axis(
                            format=".1f",
                            labelExpr="datum.label + '%'",
                            labelColor="#000000",
                            titleColor="#000000"
                        )
                    ),
                    color=alt.Color(
                        "strategy:N",
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
                            "full_label:N",
                            title="Property Type"
                        ),
                        alt.Tooltip(
                            "strategy:N",
                            title="Strategy"
                        ),
                        alt.Tooltip(
                            "gross_yield:Q",
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

st.divider()


# OPERATING PERFORMANCE AND MARKET CONTEXT

def build_metric_chart(data, metric_label, value_format, color_domain):
    metric_df = data[data["metric"] == metric_label]
    if metric_df.empty:
        return None
    return (
        alt.Chart(metric_df)
        .mark_bar()
        .encode(
            x=alt.X(
                "property_label:N",
                title="",
                axis=alt.Axis(
                    labelAngle=-20,
                    labelFontSize=9,
                    labelLimit=120,
                    labelColor="#000000",
                    titleColor="#000000",
                ),
            ),
            y=alt.Y(
                "value:Q",
                title="",
                axis=alt.Axis(labelColor="#000000", titleColor="#000000"),
            ),
            color=alt.Color(
                "property_label:N",
                scale=alt.Scale(
                    domain=color_domain,
                    range=["#F26359", "#7A2E2A", "#F5A097"],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("property_label:N", title="Property Type"),
                alt.Tooltip("value:Q", title=metric_label, format=value_format),
            ],
        )
        .properties(height=300, background="#FFFFFF")
    )

def render_legend(color_domain):
    colors = ["#F26359", "#7A2E2A", "#F5A097"]
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;margin:2px 16px 2px 0;">'
        f'<span style="width:12px;height:12px;background:{c};'
        f'display:inline-block;margin-right:6px;border-radius:2px;"></span>'
        f'<span style="color:#000000;font-size:12px;">{label}</span></span>'
        for label, c in zip(color_domain, colors)
    )
    st.markdown(
        '<div style="margin-top:8px;">'
        '<div style="color:#000000;font-weight:600;font-size:13px;margin-bottom:4px;">Property Type</div>'
        f'<div style="display:flex;flex-wrap:wrap;">{items}</div></div>',
        unsafe_allow_html=True,
    )

operating_col, market_col = st.columns(
    2,
    gap="medium"
)

with operating_col:

    with st.container(border=True):

        st.markdown("### Operating Performance")

        st.caption(
            "Compare occupancy, guest rating and typical property size."
        )

        operating_chart_data = comparison_data[
            [
                "property_label",
                "occupancy_percent",
                "average_rating",
                "average_bedrooms"
            ]
        ].melt(
            id_vars=["property_label"],
            value_vars=[
                "occupancy_percent",
                "average_rating",
                "average_bedrooms"
            ],
            var_name="metric",
            value_name="value"
        )

        operating_chart_data["metric"] = (
            operating_chart_data["metric"]
            .replace(
                {
                    "occupancy_percent": "Occupancy Rate (%)",
                    "average_rating": "Average Rating",
                    "average_bedrooms": "Average Bedrooms"
                }
            )
        )

        operating_chart_data = operating_chart_data.dropna(
            subset=["value"]
        )

        if operating_chart_data.empty:
            st.info("No operating-performance data was found.")

        else:
            operating_metrics = [
                ("Occupancy Rate (%)", ".1f"),
                ("Average Rating", ".2f"),
                ("Average Bedrooms", ".1f"),
            ]
            color_domain = comparison_data["property_label"].tolist()
            metric_cols = st.columns(len(operating_metrics), gap="small")
            for col, (metric_label, value_format) in zip(metric_cols, operating_metrics):
                with col:
                    st.caption(metric_label)
                    chart = build_metric_chart(operating_chart_data, metric_label, value_format, color_domain)
                    if chart is None:
                        st.info("No data.")
                    else:
                        st.altair_chart(chart, use_container_width=True)
            render_legend(color_domain)
        
with market_col:

    with st.container(border=True):

        st.markdown("### Market Context")

        st.caption(
            "Compare listing supply, sale evidence and the selected "
            "persona's investment score."
        )

        market_chart_data = comparison_data[
            [
                "property_label",
                "investment_score",
                "listing_count",
                "sale_txn_count"
            ]
        ].melt(
            id_vars=["property_label"],
            value_vars=[
                "investment_score",
                "listing_count",
                "sale_txn_count"
            ],
            var_name="metric",
            value_name="value"
        )

        market_chart_data["metric"] = (
            market_chart_data["metric"]
            .replace(
                {
                    "investment_score": "Investment Score",
                    "listing_count": "Listing Count",
                    "sale_txn_count": "Sale Transactions"
                }
            )
        )

        market_chart_data = market_chart_data.dropna(
            subset=["value"]
        )

        if market_chart_data.empty:
            st.info("No market-context data was found.")

        else:
            market_metrics = [
                ("Investment Score", ".2f"),
                ("Listing Count", ",.0f"),
                ("Sale Transactions", ",.0f"),
            ]
            color_domain = comparison_data["property_label"].tolist()
            metric_cols = st.columns(len(market_metrics), gap="small")
            for col, (metric_label, value_format) in zip(metric_cols, market_metrics):
                with col:
                    st.caption(metric_label)
                    chart = build_metric_chart(market_chart_data, metric_label, value_format, color_domain)
                    if chart is None:
                        st.info("No data.")
                    else:
                        st.altair_chart(chart, use_container_width=True)
            render_legend(color_domain)

st.divider()


# DETAILED COMPARISON TABLE
with st.container(border=True):

    st.markdown("### Detailed Comparison")

    display_table = comparison_data[
        [
            "property_group",
            "neighbourhood",
            "city",
            "investment_score",
            "listing_count",
            "average_adr",
            "median_adr",
            "average_annual_revenue",
            "median_annual_revenue",
            "occupancy_percent",
            "average_rating",
            "average_bedrooms",
            "median_sale_price",
            "gross_yield_percent",
            "sale_txn_count"
        ]
    ].copy()

    display_table.columns = [
        "Property Type",
        "Neighbourhood",
        "City",
        "Investment Score",
        "Listings",
        "Average ADR",
        "Median ADR",
        "Average Annual Revenue",
        "Median Annual Revenue",
        "Occupancy Rate",
        "Average Rating",
        "Average Bedrooms",
        "Median Sale Price",
        "Estimated Gross Yield",
        "Sale Transactions"
    ]

    st.dataframe(
        display_table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Investment Score": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "Listings": st.column_config.NumberColumn(
                format="%d"
            ),
            "Average ADR": st.column_config.NumberColumn(
                format="£%,.0f"
            ),
            "Median ADR": st.column_config.NumberColumn(
                format="£%,.0f"
            ),
            "Average Annual Revenue": st.column_config.NumberColumn(
                format="£%,.0f"
            ),
            "Median Annual Revenue": st.column_config.NumberColumn(
                format="£%,.0f"
            ),
            "Occupancy Rate": st.column_config.NumberColumn(
                format="%.1f%%"
            ),
            "Average Rating": st.column_config.NumberColumn(
                format="%.2f"
            ),
            "Average Bedrooms": st.column_config.NumberColumn(
                format="%.1f"
            ),
            "Median Sale Price": st.column_config.NumberColumn(
                format="£%,.0f"
            ),
            "Estimated Gross Yield": st.column_config.NumberColumn(
                format="%.2f%%"
            ),
            "Sale Transactions": st.column_config.NumberColumn(
                format="%d"
            )
        }
    )