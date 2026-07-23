import streamlit as st
from snowflake.snowpark.functions import st_x, st_y
from db import get_session
from nav import render_nav_links

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

render_nav_links()

st.set_page_config(layout='wide')

session = get_session()

# TITLE ---

st.title('Methodology and Risks')
st.subheader('How the app calculates recommendations and how to interpret the results')

# HELPER FUNCTIONS ---

def source_card(title, description):
    st.markdown(
        f"""<div style="background-color: #f4f3ee; border-radius: 10px; padding: 14px; min-height: 105px; margin-bottom: 10px;">
<div style="font-weight: 600; font-size: 15px; margin-bottom: 5px; color: #000000;">{title}</div>
<div style="font-size: 13px; line-height: 1.4; color: #4d4d4d;">{description}</div>
</div>""",
        unsafe_allow_html=True
    )

# PERSONA METHODOLOGY ---

with st.expander('ⓘ  How does the investment score work?', expanded=True):

    st.write(
        """
        The app uses a persona-based investment score. This means the recommendation is not
        the same for every investor. The score changes depending on the investor profile
        selected on the homepage.
        """
    )

    st.write(
        """
        The three investor personas are:
        """
    )

    st.markdown(
        """
        - **Yield Maximiser** — focuses mainly on maximising annual rental income.

        - **Occupancy Optimiser** — focuses on keeping the property booked consistently.

        - **Quality Host** — focuses on guest satisfaction and premium hosting quality.
        """
    )

    st.write(
        """
        Each persona uses the same underlying measures, but gives them different importance.
        This allows the app to explain recommendations based on the investor's goals rather
        than using one generic ranking for everyone.
        """
    )

    st.markdown('#### Persona weightings')

    st.markdown(
        """
        - **Yield Maximiser:** 30% Revenue, 30% Occupancy, 20% Price, 10% Rating, 10% Location.

        - **Occupancy Optimiser:** 40% Occupancy, 20% Revenue, 20% Rating, 10% Price, 10% Location.

        - **Quality Host:** 40% Rating, 20% Occupancy, 20% Price, 10% Revenue, 10% Location.
        """
    )

    st.write(
        """
        These weightings are used to make the score more transparent. For example, a property
        with strong revenue may rank higher for a Yield Maximiser, while a highly rated and
        consistently booked property may be more attractive for a Quality Host or Occupancy
        Optimiser.
        """
    )

# AREA OVERVIEW METHODOLOGY ---

with st.expander('📍  How are neighbourhoods ranked?', expanded=True):

    st.write(
        """
        The Area Overview page ranks neighbourhoods using the selected persona.
        If no persona has been chosen, the app stops and asks the user to return to
        the homepage before continuing.
        """
    )

    st.write(
        """
        The neighbourhood data comes from `MART_AREA_OVERVIEW` and is joined to
        `AI_OUTPUTS` using the neighbourhood name. The app filters the AI output so that
        only rows matching the selected persona and the `area_overview` output type are used.
        """
    )

    st.code(
        """
WHERE LOWER(l."persona") = LOWER('{safe_persona}')
AND lower(l."output_type") = 'area_overview'

ORDER BY l."investment_score" DESC
        """,
        language='sql'
    )

    st.write(
        """
        The displayed investment rank is then created by ordering neighbourhoods from
        highest to lowest investment score.
        """
    )

    st.code(
        """
ROW_NUMBER() OVER (
    ORDER BY l."investment_score" DESC
) AS INVESTMENT_RANK
        """,
        language='sql'
    )

    st.markdown(
        """
        The Area Overview page also displays:

        - **Investment rank** — the neighbourhood's position after sorting by persona-based investment score.
        - **Investment score** — the score stored in `AI_OUTPUTS` for the selected persona.
        - **Median annual revenue** — the median yearly revenue for listings in that neighbourhood.
        - **Average rating** — the average guest rating in that neighbourhood.
        - **POI density** — points of interest per square kilometre.
        - **Area** — the neighbourhood area in square kilometres.
        """
    )

    st.info(
        """
        The Area Overview ranking is no longer based only on annual revenue and price.
        It is now persona-based and ordered by `investment_score`.
        """
    )

# MAP METHODOLOGY ---

with st.expander('🗺️  How does the map work?', expanded=True):

    st.write(
        """
        The map uses neighbourhood boundary polygons from `MART_AREA_OVERVIEW`.
        The boundary is simplified before being displayed so that the map is faster
        and easier to interact with.
        """
    )

    st.markdown(
        """
        - Boundaries are converted to GeoJSON using `ST_ASGEOJSON`.

        - Boundaries are simplified using `ST_SIMPLIFY(n.BOUNDARY, 50)`.

        - The map centre is calculated using the centroid of each simplified boundary.

        - Latitude is extracted using `ST_Y`.

        - Longitude is extracted using `ST_X`.

        - The top three ranked neighbourhoods are highlighted using a stronger colour.

        - Other neighbourhoods are shown in the lighter app background colour.
        """
    )

    st.write(
        """
        Clicking a neighbourhood on the map selects it, adds it to the starred
        neighbourhood list if fewer than three have already been selected, and shows
        the full analytics section for that area.
        """
    )

    st.markdown(
        """
        The map tooltip shows the neighbourhood name, city, investment rank,
        investment score, median annual revenue, average rating, POI density and area.
        """
    )

# PROPERTY TYPE METHODOLOGY ---

with st.expander('🏠  How are property types ranked?', expanded=True):

    st.write(
        """
        The Property Type page starts from the three neighbourhoods starred on the
        Area Overview page. The user then chooses one of those neighbourhoods to compare
        property groups such as House, Apartment / Flat and Other property types.
        """
    )

    st.write(
        """
        The page loads property group data from `MART_PROPERTY_GROUP` and joins it to
        listing-level scores from `INVESTMENT_SCORES`. It groups listings by city,
        neighbourhood and property group, then calculates average persona-specific
        investment scores for each property group.
        """
    )

    st.code(
        """
AVG(b.SCORE_YIELD_MAXIMISER) AS INVESTMENT_SCORE_YIELD,
AVG(b.SCORE_OCCUPANCY_OPTIMISER) AS INVESTMENT_SCORE_OCCUPANCY,
AVG(b.SCORE_QUALITY_HOST) AS INVESTMENT_SCORE_QUALITY
        """,
        language='sql'
    )

    st.write(
        """
        The selected persona determines which score column is used for ranking.
        """
    )

    st.code(
        """
Yield_Maximiser      -> INVESTMENT_SCORE_YIELD
Occupancy_Optimiser  -> INVESTMENT_SCORE_OCCUPANCY
Quality_Host         -> INVESTMENT_SCORE_QUALITY
        """,
        language='text'
    )

    st.markdown(
        """
        The top property types are sorted from highest to lowest score for the selected
        persona. The page also shows listing share using an interactive pie chart.
        """
    )

    st.markdown(
        """
        The pie chart groups property types into:

        - **House**
        - **Apartment / Flat**
        - **Others**
        """
    )

    st.write(
        """
        For each group, the chart summarises listing count, listing share, average
        investment score, ADR, median annual revenue, average rating, average bedrooms,
        median sale price and sale transaction count where available.
        """
    )

# LISTING CANDIDATES METHODOLOGY ---

with st.expander('🏡  How are listing candidates ranked?', expanded=True):

    st.write(
        """
        The Listing Candidates page starts from the property types starred on the
        Property Type page. The user selects one starred property type, and the app
        then finds the best matching listings in that city, neighbourhood and property group.
        """
    )

    st.write(
        """
        Listing data comes from `MART_LISTING_CANDIDATES` and is joined to
        `INVESTMENT_SCORES` using `LISTING_ID`.
        """
    )

    st.markdown(
        """
        The selected persona again determines which score column is used:

        - **Yield Maximiser** uses `INVESTMENT_SCORE_YIELD`.
        - **Occupancy Optimiser** uses `INVESTMENT_SCORE_OCCUPANCY`.
        - **Quality Host** uses `INVESTMENT_SCORE_QUALITY`.
        """
    )

    st.write(
        """
        The app filters listings to the selected city, neighbourhood and property group,
        removes listings without the required persona score, then sorts by that score in
        descending order.
        """
    )

    st.code(
        """
top_10_listings = selected_listing_data.sort_values(
    by=score_column,
    ascending=False
).head(10)
        """,
        language='python'
    )

    st.markdown(
        """
        Each listing card displays:

        - Listing name and image.
        - Neighbourhood, property type and room type.
        - Investment score.
        - Annual revenue.
        - ADR.
        - RevPAR.
        - Bedrooms, bathrooms, beds and guest capacity.
        - Review score, number of reviews and occupancy rate.
        - Link to the original listing where available.
        """
    )

# DATA SOURCES ---

with st.expander('▦  Data sources', expanded=True):

    st.write(
        """
        The app combines Airbnb listing data, neighbourhood-level summary tables,
        listing-level investment scores, property group summaries, AI-generated narratives
        and supporting market data.
        """
    )

    source_col1, source_col2 = st.columns(2)

    with source_col1:
        source_card(
            'Inside Airbnb',
            'Primary source for Airbnb listing information, including listing IDs, neighbourhoods, property types, room types, prices, revenue estimates, availability-related fields, ratings, reviews and listing URLs.'
        )

        source_card(
            'MART_AREA_OVERVIEW',
            'Gold-layer neighbourhood summary table used on the Area Overview page. It provides city, neighbourhood, listing count, ADR, occupancy, annual revenue, ratings, POI metrics, area and boundary geometry.'
        )

        source_card(
            'MART_LISTING_CANDIDATES',
            'Gold-layer listing table used on the Listing Candidates page. It provides listing-level revenue, ADR, RevPAR, occupancy, location, room details, reviews, POI counts, transport counts and listing URLs.'
        )

    with source_col2:
        source_card(
            'INVESTMENT_SCORES',
            'Gold-layer scoring table that stores the persona-specific listing scores: Yield Maximiser, Occupancy Optimiser and Quality Host.'
        )

        source_card(
            'MART_PROPERTY_GROUP',
            'Gold-layer property group table used to compare property types within selected neighbourhoods, including listing counts, ADR, revenue, occupancy, ratings, bedrooms, sale price and transaction counts.'
        )

        source_card(
            'AI_OUTPUTS',
            'Gold-layer table used for persona-specific area scores and AI narrative summaries. The Area Overview page uses it for neighbourhood investment scores and explanatory AI summaries.'
        )

    st.info(
        """
        HM Land Registry and UK House Price Index data are relevant to the wider project
        because sale prices and property market context appear in fields such as
        `MEDIAN_SALE_PRICE`, `AREA_MEDIAN_SALE_PRICE` and sale transaction counts.
        """
    )

# AI SUMMARY ---

with st.expander('✨  How are AI summaries used?', expanded=True):

    st.write(
        """
        AI summaries are stored in `AI_OUTPUTS`. The app does not generate the narrative
        live on the page. It retrieves a stored narrative that matches the selected
        persona, neighbourhood and output type.
        """
    )

    st.markdown(
        """
        On the Area Overview page, the app filters summaries using:

        - selected persona
        - selected neighbourhood
        - `output_type = area_overview`
        """
    )

    st.write(
        """
        If a matching record exists, the app reads the JSON stored in `ai_narrative`
        and displays fields such as investment summary, key strengths, key risks,
        confidence and recommended action.
        """
    )

    st.markdown(
        """
        On the Property Type page, the app uses AI output with `output_type = recommendation`
        to display recommendation commentary for the selected neighbourhood and persona.
        """
    )

    st.warning(
        """
        AI summaries are explanatory commentary. The underlying scores and metrics should
        still be checked before making any investment decision.
        """
    )

# TRANSPARENCY AND LIMITATIONS ---

with st.expander('⚖  Transparency, assumptions & limitations', expanded=True):

    st.markdown('#### What the figures represent')

    st.markdown(
        """
        - **Investment scores are decision-support scores, not guaranteed returns.**
          They rank areas, property groups and listings according to the selected persona.

        - **Estimated annual revenue is not guaranteed income.**
          It is based on historical Airbnb-style listing data and may differ from future performance.

        - **ADR means average daily rate.**
          It represents average nightly pricing and may not equal the final achieved booking price.

        - **RevPAR means revenue per available room/night.**
          In this app it is shown as an investment metric for comparing listing performance.

        - **Occupancy rate is an estimate.**
          It reflects estimated occupied nights or availability-derived booking behaviour and should
          not be treated as a perfect record of actual stays.

        - **Average and median neighbourhood figures are not property-specific forecasts.**
          Individual properties may perform differently depending on quality, management,
          exact location, amenities, seasonality and local competition.

        - **POI and transport counts describe nearby amenities.**
          They help explain location strength but do not guarantee higher revenue.
        """
    )

    st.markdown('#### London short-term letting rules')

    st.markdown(
        """
        - In London, short-term letting of residential properties is generally limited
          to 90 nights per calendar year unless planning permission is granted.

        - This can materially affect annual revenue potential for London listings.

        - Investors should check planning rules, leasehold terms, mortgage conditions,
          insurance requirements and local council rules before operating a short-term rental.
        """
    )

    st.markdown('#### Data limitations')

    st.markdown(
        """
        - The data is a snapshot in time. Listings, prices, reviews, availability and
          local market conditions can change.

        - Inside Airbnb-style data may not capture every active short-term rental listing.

        - Median sale prices and transaction counts depend on available property sales data
          and may be sparse in some neighbourhood/property-type combinations.

        - A high investment score does not include all real-world costs such as mortgage
          payments, furnishing, cleaning, repairs, platform fees, management fees, insurance,
          tax or licensing costs.

        - The app is designed for comparison and research, not final investment decision-making.
        """
    )

    st.markdown('#### Important note')

    st.warning(
        """
        This app does not provide financial, legal, tax or planning advice.
        It is intended to support transparent comparison and stakeholder discussion.
        """
    )

# FOOTER ---

st.markdown(
    """
    <div style="
        text-align: center;
        color: #777777;
        font-size: 12px;
        border-top: 1px solid #e5e5e5;
        margin-top: 35px;
        padding-top: 15px;
    ">
        Estimates are based on Airbnb listing data, gold-layer summary tables and supporting property market data.
        This tool is for research and comparison only.
    </div>
    """,
    unsafe_allow_html=True
)