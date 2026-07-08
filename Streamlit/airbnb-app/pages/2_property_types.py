import streamlit as st
import os

st.cache_data.clear()

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#TITLE ---

st.title('Property Type')
st.subheader('Out of your favourite neighbourhoods, find the best property types based on your selected persona. Choose 3 property types from any of the nieghbourhoods that spark the most interest.')
#SQL QUERY ---

@st.cache_data(ttl=300)
def load_property_types(_session):
    return _session.sql(
        """
         SELECT CASE
                WHEN l._filename ILIKE '%london%' THEN 'London'
                WHEN l._filename ILIKE '%bristol%' THEN 'Bristol'
                WHEN l._filename ILIKE '%manchester%' THEN 'Manchester'
                ELSE 'No city'
            END as city,

            d.NEIGHBOURHOOD, d.ROOM_TYPE, d.PROPERTY_TYPE, d.STRUCTURE_CLASS, COUNT(*) AS LISTING_COUNT

        FROM AIRBNB_INVESTMENT_DB.GOLD.DIM_LISTING d
        
        JOIN AIRBNB_INVESTMENT_DB.SILVER."LISTINGS_CLEANED" l
        
        ON d.NEIGHBOURHOOD = l.NEIGHBOURHOOD

        WHERE NEIGHBOURHOOD IS NOT NULL AND ROOM_TYPE IS NOT NULL AND PROPERTY_TYPE IS NOT NULL AND STRUCTURE_CLASS IS NOT NULL

        GROUP BY CITY, NEIGHBOURHOOD, ROOM_TYPE, PROPERTY_TYPE, STRUCTURE_CLASS

        ORDER BY CITY, NEIGHBOURHOOD, LISTING_COUNT DESC
        """
    ).to_pandas()

property_types = load_property_types(session)

#VISUALISATIONS ---
