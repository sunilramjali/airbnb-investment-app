import streamlit as st
import pandas as pd
from db import get_session

#CUSTOM CSS SCRIPT FOR PAGE LOOK
st.markdown(
    """
    <style>
    /* Main app */
    .stApp {
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
    section[data-testid="stSidebar"] {
        background-color: white !important;
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
    </style>
    """,
    unsafe_allow_html=True
)

page_col1, page_col2, page_col_3, empty_col = st.columns([1,1,1,5])
with page_col1:
    if st.button('Landing', use_container_width = True):
        st.switch_page('landing.py')

with page_col2:
    if st.button('Area Overview', use_container_width = True):
        st.switch_page('pages/1_area_overview.py')

with page_col_3:
    if st.button('Property Types', use_container_width = True):
        st.switch_page('pages/2_property_types.py')


if "selected_listing_property_group" not in st.session_state:
    st.session_state["selected_listing_property_group"] = None

if "selected_listing_neighbourhood" not in st.session_state:
    st.session_state["selected_listing_neighbourhood"] = None

if "selected_listing_city" not in st.session_state:
    st.session_state["selected_listing_city"] = None

if "starred_property_types" not in st.session_state:
    st.session_state["starred_property_types"] = []

if "starred_listings" not in st.session_state:
    st.session_state["starred_listings"] = []

#TITLE ---

st.title('Listing Candidates')
st.subheader('Out of your favourite Property types, find the 10 best listings based on your selected persona. Choose 3 listings that spark the most interest, from any of the property types.')


#SQL QUERY ---
session = get_session()

@st.cache_data(ttl=600)
def load_listings(_session):
    return _session.sql(
            """
                SELECT
                    a.LISTING_ID,
                    a.GEO_POINT,
                    a.INSTANT_BOOKABLE,
                    a.LISTING_URL,
                    a.NAME,
                    a.NEIGHBOURHOOD,
                    a.PICTURE_URL,
                    a.PROPERTY_GROUP,
                    a.PROPERTY_TYPE,
                    a.ROOM_TYPE,
                    a.STRUCTURE_CLASS,
                    a.ACCOMMODATES,
                    a.ADR,
                    a.ANNUAL_REVENUE,
                    a.AREA_MEDIAN_SALE_PRICE,
                    a.BATHROOMS,
                    a.BEDROOMS,
                    a.BEDS,
                    a.DINING_COUNT_500M,
                    a.HOST_ID,
                    a.LATITUDE,
                    a.LONGITUDE,
                    a.NUMBER_OF_REVIEWS,
                    a.OCCUPANCY_RATE,
                    a.POI_COUNT_500M,
                    a.REVIEW_SCORES_RATING,
                    a.REVPAR,
                    a.TRANSPORT_COUNT_500M,
                    b.CITY,
                    b.SCORE_YIELD_MAXIMISER AS INVESTMENT_SCORE_YIELD,
                    b.SCORE_OCCUPANCY_OPTIMISER AS INVESTMENT_SCORE_OCCUPANCY,
                    b.SCORE_QUALITY_HOST AS INVESTMENT_SCORE_QUALITY
                
                FROM AIRBNB_INVESTMENT_DB.GOLD.MART_LISTING_CANDIDATES a
                
                INNER JOIN AIRBNB_INVESTMENT_DB.GOLD.INVESTMENT_SCORES b
                    ON a.LISTING_ID = b.LISTING_ID
                
                WHERE 
                    a.NEIGHBOURHOOD IS NOT NULL
                    AND a.PROPERTY_GROUP IS NOT NULL
                    AND b.CITY IS NOT NULL
                    AND LOWER(TRIM(a.PROPERTY_GROUP)) != 'other / unknown'
                        
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

listing_candidates = load_listings(session)

ai_summary = load_summary(session)

#Visualisations ---
starred_property_types = st.session_state["starred_property_types"]

st.markdown("### Your starred Property Types")

if len(starred_property_types) == 0:
    st.info(
        "You have not starred any Property Types yet. "
        "Go back to the Property Types page and star up to 3 Property Types."
    )

else:
    cols = st.columns(3)

    for i, property_type in enumerate(starred_property_types[:3]):

        property_group = property_type["property_group"]
        neighbourhood_name = property_type["neighbourhood"]
        city_name = property_type["city"]

        button_label = f"{property_group}\n{neighbourhood_name}\n{city_name}"

        with cols[i]:
            if st.button(
                label=button_label,
                key=f"listing_property_type_{i}_{city_name}_{neighbourhood_name}_{property_group}",
                use_container_width=True
            ):
                st.session_state["selected_listing_property_group"] = property_group
                st.session_state["selected_listing_neighbourhood"] = neighbourhood_name
                st.session_state["selected_listing_city"] = city_name
                st.rerun()

selected_property_group = st.session_state["selected_listing_property_group"]
selected_neighbourhood = st.session_state["selected_listing_neighbourhood"]
selected_city = st.session_state["selected_listing_city"]
persona = st.session_state.get("persona", None)

if selected_property_group is not None:

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

            selected_listing_data = listing_candidates[
                (listing_candidates["CITY"].astype(str).str.strip().str.lower() == str(selected_city).strip().lower())
                & (listing_candidates["NEIGHBOURHOOD"].astype(str).str.strip().str.lower() == str(selected_neighbourhood).strip().lower())
                & (listing_candidates["PROPERTY_GROUP"].astype(str).str.strip().str.lower() == str(selected_property_group).strip().lower())
            ].copy()

            if selected_listing_data.empty:
                st.warning("No listings found for this selected property type.")

            else:
                selected_listing_data = selected_listing_data.dropna(subset=[score_column])

                top_10_listings = selected_listing_data.sort_values(
                    by=score_column,
                    ascending=False
                ).head(10)
                
                st.markdown(f"## {selected_property_group}")
                st.caption(f"{selected_neighbourhood}, {selected_city}")
                st.caption(f"Ranking based on persona: {persona}")

                st.divider()

                st.markdown("### Top 10 Listing Candidates")

                list_col, starred_col = st.columns([3, 1], gap="medium")
                
                with list_col:
                
                    if top_10_listings.empty:
                        st.warning("No scored listings found for this property type.")
                
                    else:
                        for rank, row in enumerate(top_10_listings.itertuples(), start=1):
                
                            listing_item = {
                                "listing_id": row.LISTING_ID,
                                "name": row.NAME,
                                "city": row.CITY,
                                "neighbourhood": row.NEIGHBOURHOOD,
                                "property_type": row.PROPERTY_TYPE,
                                "property_group": row.PROPERTY_GROUP,
                                "picture_url": row.PICTURE_URL,
                                "listing_url": row.LISTING_URL,
                                "investment_score": getattr(row, score_column),
                                "persona": persona
                            }
                
                            already_starred = any(
                                item["listing_id"] == row.LISTING_ID
                                for item in st.session_state["starred_listings"]
                            )
                
                            with st.container(border=True):
                
                                row_cols = st.columns([1.2, 2.5, 2, 2, 1.2])
                
                                with row_cols[0]:
                                    if pd.notna(row.PICTURE_URL):
                                        st.image(row.PICTURE_URL, use_container_width=True)
                                    else:
                                        st.write("No image")
                
                                with row_cols[1]:
                                    st.markdown(f"### #{rank} {row.NAME}")
                                    st.write(f"**Neighbourhood:** {row.NEIGHBOURHOOD}")
                                    st.write(f"**Property Type:** {row.PROPERTY_TYPE}")
                                    st.write(f"**Room Type:** {row.ROOM_TYPE}")
                
                                    button_cols = st.columns([1, 1])
                
                                    with button_cols[0]:
                                        if pd.notna(row.LISTING_URL):
                                            st.link_button(
                                                "Open listing",
                                                row.LISTING_URL,
                                                use_container_width=True
                                            )
                
                                    with button_cols[1]:
                                        if already_starred:
                                            st.success("Selected")
                                        else:
                                            if st.button(
                                                "Star",
                                                key=f"star_listing_{row.LISTING_ID}",
                                                use_container_width=True
                                            ):
                                                if len(st.session_state["starred_listings"]) < 3:
                                                    st.session_state["starred_listings"].append(listing_item)
                                                    st.rerun()
                                                else:
                                                    st.warning("You can only star 3 listings.")
                
                                with row_cols[2]:
                                    st.markdown("### Investment")
                                    st.write(f"**Investment Score:** {getattr(row, score_column):,.2f}")
                                    st.write(f"**Annual Revenue:** £{row.ANNUAL_REVENUE:,.0f}" if pd.notna(row.ANNUAL_REVENUE) else "**Annual Revenue:** N/A")
                                    st.write(f"**ADR:** £{row.ADR:,.0f}" if pd.notna(row.ADR) else "**ADR:** N/A")
                                    st.write(f"**RevPAR:** £{row.REVPAR:,.0f}" if pd.notna(row.REVPAR) else "**RevPAR:** N/A")
                
                                with row_cols[3]:
                                    st.markdown("### Listing Details")
                                    st.write(f"**Bedrooms:** {row.BEDROOMS:,.0f}" if pd.notna(row.BEDROOMS) else "**Bedrooms:** N/A")
                                    st.write(f"**Bathrooms:** {row.BATHROOMS:,.0f}" if pd.notna(row.BATHROOMS) else "**Bathrooms:** N/A")
                                    st.write(f"**Beds:** {row.BEDS:,.0f}" if pd.notna(row.BEDS) else "**Beds:** N/A")
                                    st.write(f"**Accommodates:** {row.ACCOMMODATES:,.0f}" if pd.notna(row.ACCOMMODATES) else "**Accommodates:** N/A")
                
                                with row_cols[4]:
                                    st.markdown("### Quality")
                                    st.write(f"**Rating:** {row.REVIEW_SCORES_RATING:,.2f}" if pd.notna(row.REVIEW_SCORES_RATING) else "**Rating:** N/A")
                                    st.write(f"**Reviews:** {row.NUMBER_OF_REVIEWS:,.0f}" if pd.notna(row.NUMBER_OF_REVIEWS) else "**Reviews:** N/A")
                                    st.write(f"**Occupancy:** {row.OCCUPANCY_RATE:,.1f}%" if pd.notna(row.OCCUPANCY_RATE) else "**Occupancy:** N/A")
                
                
                with starred_col:
                
                    with st.container(border=True):
                        st.markdown("### Starred Listings")
                
                        starred_listings = st.session_state["starred_listings"]
                
                        if len(starred_listings) == 0:
                            st.info("No listings starred yet.")
                
                        else:
                            for i, item in enumerate(starred_listings):
                
                                with st.container(border=True):
                
                                    if pd.notna(item["picture_url"]):
                                        st.image(item["picture_url"], use_container_width=True)
                                    else:
                                        st.write("No image")
                
                                    st.markdown(f"### ⭐ {item['name']}")
                                    st.write(f"**{item['city']}**")
                                    st.write(f"**{item['neighbourhood']}**")
                                    st.write(f"**{item['property_type']}**")
                
                                    if "investment_score" in item:
                                        st.caption(f"Investment Score: **{item['investment_score']:,.2f}**")
                
                                    if st.button(
                                        "🗑️",
                                        key=f"remove_starred_listing_{i}_{item['listing_id']}",
                                        use_container_width=True
                                    ):
                                        st.session_state["starred_listings"].pop(i)
                                        st.rerun()
                
                        st.caption(f"{len(starred_listings)} / 3 selected")

#AI-summary --- to be continued