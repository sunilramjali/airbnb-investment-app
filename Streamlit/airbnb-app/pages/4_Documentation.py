
import streamlit as st
import os
from snowflake.snowpark.functions import st_x, st_y


conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

st.set_page_config(layout='wide')

# TITLE ---

st.title('Methodology and Risks')
st.subheader('How the app calculates area comparisons and how to interpret the results')

# HELPER FUNCTIONS ---

def source_card(title, description):
    st.markdown(
        f"""<div style="background-color: #f4f3ee; border-radius: 10px; padding: 14px; min-height: 100px; margin-bottom: 10px;">
<div style="font-weight: 600; font-size: 15px; margin-bottom: 5px;">
{title}
</div>
<div style="font-size: 13px; line-height: 1.4; color: #4d4d4d;">
{description}
</div>
</div>""",
        unsafe_allow_html=True
    )

# METHODOLOGY ---

with st.expander('ⓘ  How are areas ranked?', expanded=True):

    st.write(
        """
        The Area Overview page ranks neighbourhoods using a transparent ordering rule.
        It is not currently a weighted investment score or a machine-learning prediction.
        """
    )

    st.write(
        """
        For each neighbourhood, the app calculates the average annual revenue,
        average nightly price and number of Airbnb listings.
        """
    )

    st.markdown(
        """
        - **Average annual revenue** — the average of `ESTIMATED_REVENUE_L365D`
          across listings in that neighbourhood.

        - **Average nightly price** — the average of the listing `PRICE` field
          across listings in that neighbourhood.

        - **Number of listings** — the count of listing IDs associated with that
          neighbourhood.

        - **City** — assigned from the original source filename. Listings with
          filenames containing `london`, `bristol`, or `manchester` are labelled
          accordingly.
        """
    )

    st.write('Areas are then ranked using the following SQL logic:')

    st.code(
        """
ROW_NUMBER() OVER (
    ORDER BY average_annual_revenue DESC,
             average_price ASC
) AS investment_rank
        """,
        language='sql'
    )

    st.write(
        """
        This means that areas with higher average annual revenue appear first.
        Where two areas have similar revenue, the area with the lower average
        nightly price appears higher in the ranking.
        """
    )

    st.info(
        """
        The selected investor persona does not currently change the Area Overview
        ranking. It is used when retrieving the AI Summary for the selected area.
        """
    )

# MAP METHODOLOGY ---

with st.expander('🗺️  How does the map work?', expanded=True):

    st.write(
        """
        The map uses neighbourhood boundary polygons from the
        `NEIGHBOURHOODS_GEO_CLEANED` table.
        """
    )

    st.markdown(
        """
        - Each neighbourhood is displayed using its stored geographic boundary.

        - The centre point of each boundary is calculated using
          `ST_CENTROID(boundary)`.

        - Latitude is extracted using `ST_Y(...)`.

        - Longitude is extracted using `ST_X(...)`.

        - The colour intensity of each neighbourhood is based on its average
          annual revenue.
        """
    )

    st.write(
        """
        Hovering over an area on the map displays the neighbourhood name and
        its average annual revenue.
        """
    )

# DATA SOURCES ---

with st.expander('▦  Data sources', expanded=True):

    st.write(
        """
        The app combines Airbnb listing data with geographic neighbourhood data.
        Additional public sources can be incorporated as the investment model develops.
        """
    )

    source_col1, source_col2 = st.columns(2)

    with source_col1:
        source_card(
            'Inside Airbnb',
            """
            Primary source for Airbnb listing information, including listing IDs,
            neighbourhoods, nightly prices, estimated annual revenue and review data.
            """
        )

        source_card(
            'Neighbourhood geographic data',
            """
            Geographic boundary data used to display neighbourhood polygons,
            calculate map centroids and support area-level comparisons.
            """
        )

    with source_col2:
        source_card(
            'HM Land Registry',
            """
            Intended source for property transaction data. This can support future
            calculations such as median sale price, gross rental yield and payback period.
            """
        )

        source_card(
            'UK House Price Index',
            """
            Intended source for wider property-price trends and local market context.
            This can help place Airbnb revenue data alongside longer-term property trends.
            """
        )

# AI SUMMARY ---

with st.expander('✨  AI summary methodology', expanded=True):

    st.write(
        """
        The Area Overview page displays an AI-generated summary for the selected
        neighbourhood and investor persona.
        """
    )

    st.markdown(
        """
        The app searches the `AI_OUTPUTS` table using:

        - the selected investor persona
        - the selected neighbourhood
        """
    )

    st.write(
        """
        If a matching record exists, the app reads the stored `ai_narrative`
        JSON and displays its `investment_summary` field.
        """
    )

    st.warning(
        """
        AI summaries should be treated as explanatory commentary, not as a
        replacement for the underlying metrics or independent investment research.
        """
    )

# TRANSPARENCY AND LIMITATIONS ---

with st.expander('⚖  Transparency, assumptions & limitations', expanded=True):

    st.markdown('#### What the figures represent')

    st.markdown(
        """
        - **Estimated annual revenue is not guaranteed income.** It is based on
          historical Airbnb listing data and may differ from future performance.

        - **Average neighbourhood figures are not property-specific forecasts.**
          Individual listings can perform differently because of property condition,
          exact location, guest capacity, management quality and seasonality.

        - **Average nightly price is not the same as a guaranteed achieved price.**
          It is calculated from listing price data and may not reflect discounts,
          cancellations, promotions or actual booking outcomes.

        - **Listing coverage may be incomplete.** Inside Airbnb data may not include
          every active short-term rental listing in every area.
        """
    )

    st.markdown('#### London short-term letting rules')

    st.markdown(
        """
        - In London, using a residential property as short-term accommodation for
          more than 90 nights in a calendar year generally requires planning permission.

        - This can materially affect potential annual revenue for London listings.

        - Investors should also check leasehold conditions, mortgage terms,
          insurance requirements and local council rules before operating a
          short-term rental.
        """
    )

    st.markdown('#### Important note')

    st.warning(
        """
        This app is designed to support initial research and comparison.
        It does not provide financial, legal, tax or planning advice.
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
        Estimates are based on Airbnb listing data and supporting geographic data.
        This tool is for research and comparison only.
    </div>
    """,
    unsafe_allow_html=True
)


