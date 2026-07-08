import streamlit as st
import os
import pandas as pd

st.cache_data.clear()

st.set_page_config(layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

if "starred_neighbourhoods" not in st.session_state:
    st.session_state["starred_neighbourhoods"] = []

if "selected_property_neighbourhood" not in st.session_state:
    st.session_state["selected_property_neighbourhood"] = None
#TITLE ---

st.title('Property Type')
st.subheader('Out of your favourite neighbourhoods, find the best property types based on your selected persona. Choose 3 property types from any of the nieghbourhoods that spark the most interest.')
#SQL QUERY ---

@st.cache_data(ttl=300)
def load_property_types(_session):
    return _session.sql(
        """
        SELECT CITY, NEIGHBOURHOOD, ROOM_TYPE, PROPERTY_TYPE, STRUCTURE_CLASS, COUNT(*) AS LISTING_COUNT
        
        FROM AIRBNB_INVESTMENT_DB.GOLD.DIM_LISTING l

        WHERE NEIGHBOURHOOD IS NOT NULL AND ROOM_TYPE IS NOT NULL AND PROPERTY_TYPE IS NOT NULL AND STRUCTURE_CLASS IS NOT NULL

        GROUP BY CITY, NEIGHBOURHOOD, ROOM_TYPE, PROPERTY_TYPE, STRUCTURE_CLASS

        ORDER BY CITY, NEIGHBOURHOOD, LISTING_COUNT DESC
        """
    ).to_pandas()

property_types = load_property_types(session)

#VISUALISATIONS ---
starred_neighbourhoods = st.session_state["starred_neighbourhoods"]

st.markdown("### Your starred neighbourhoods")

if len(starred_neighbourhoods) == 0:
    st.info("You have not starred any neighbourhoods yet. Go back to the Area Overview page and star up to 3 neighbourhoods.")

else:
    cols = st.columns(3)

    for i, neighbourhood in enumerate(starred_neighbourhoods[:3]):
        with cols[i]:
            if st.button(
                neighbourhood,
                key=f"property_neighbourhood_{neighbourhood}",
                use_container_width=True
            ):
                st.session_state["selected_property_neighbourhood"] = neighbourhood

selected_neighbourhood = st.session_state["selected_property_neighbourhood"]

if selected_neighbourhood is None and len(starred_neighbourhoods) > 0:
    selected_neighbourhood = starred_neighbourhoods[0]
    st.session_state["selected_property_neighbourhood"] = selected_neighbourhood

if selected_neighbourhood is not None:

    neighbourhood_data = property_types[
        property_types["NEIGHBOURHOOD"] == selected_neighbourhood
    ].copy()

    st.markdown(f"## {selected_neighbourhood}")

    st.markdown("### Top 3 property type combinations")

    top_3 = neighbourhood_data.sort_values(
        by="LISTING_COUNT",
        ascending=False
    ).head(3)

    if top_3.empty:
        st.warning("No property type data found for this neighbourhood.")

    else:
        top_cols = st.columns(3)

        for i, row in enumerate(top_3.itertuples()):
            with top_cols[i]:
                st.markdown(
                    f"""
                    <div style="
                        background-color: #f4f3ee;
                        border-radius: 12px;
                        padding: 18px;
                        min-height: 180px;
                        border: 1px solid #ddd;
                    ">
                        <div style="
                            font-size: 15px;
                            font-weight: 700;
                            margin-bottom: 10px;
                        ">
                            Option {i + 1}
                        </div>

                        <div style="font-size: 13px; margin-bottom: 6px;">
                            <b>Room type:</b> {row.ROOM_TYPE}
                        </div>

                        <div style="font-size: 13px; margin-bottom: 6px;">
                            <b>Property type:</b> {row.PROPERTY_TYPE}
                        </div>

                        <div style="font-size: 13px; margin-bottom: 6px;">
                            <b>Structure class:</b> {row.STRUCTURE_CLASS}
                        </div>

                        <div style="
                            font-size: 20px;
                            font-weight: 700;
                            margin-top: 14px;
                        ">
                            {row.LISTING_COUNT}
                        </div>

                        <div style="font-size: 12px; color: #666;">
                            listings
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown("### All property type combinations")

                all_property_types = neighbourhood_data.sort_values(
                    by="LISTING_COUNT",
                    ascending=False
                )
        
                st.dataframe(
                    all_property_types[
                        [
                            "ROOM_TYPE",
                            "PROPERTY_TYPE",
                            "STRUCTURE_CLASS",
                            "LISTING_COUNT"
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True
                )
