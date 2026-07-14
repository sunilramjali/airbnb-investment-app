import streamlit as st
import os

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#TITLE ---

st.title('Recommendations')

@st.cache_data(ttl=600)
def load_listings(_session):
    return _session.sql(
            """
        SELECT CASE
                WHEN _filename ILIKE '%london%' THEN 'London'
                WHEN _filename ILIKE '%bristol%' THEN 'Bristol'
                WHEN _filename ILIKE '%manchester%' THEN 'Manchester'
                ELSE 'No city'
            END as city,
            listing_id,
            name, 
            picture_url,
            description, 
            neighbourhood, 
            estimated_revenue_l365d, 
            price, 
            review_scores_rating, 
            bedrooms, 
            bathrooms, 
            property_type, 
            room_type, 
            row_number() over (order by estimated_revenue_l365d desc,price asc,review_scores_rating desc) as investment_rank
        FROM AIRBNB_INVESTMENT_DB.SILVER.LISTINGS_CLEANED
        ORDER BY investment_rank
    """).to_pandas()

listings_ranked = load_listings(session)

#INTERACTIVE ELEMENTS ---

property_type_selection = st.session_state['property_type_selection']

property_type_selection = st.sidebar.multiselect('property type',property_type_selection,default=property_type_selection)

def clear_saved():
    st.session_state['saved_listings']=set()

st.sidebar.button('Clear saved listings',on_click=clear_saved)

#VISUALISATIONS ---

saved_df = listings_ranked[listings_ranked['LISTING_ID'].isin(st.session_state.get('saved_listings', set()))]
st.dataframe(saved_df)