import streamlit as st
import os

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#SQL QUERY ---
@st.cache_data(ttl=600)

def load_bristol_listings(_session):
    return _session.sql(
            """
        SELECT "name", 
            "picture_url",
            "description", 
            "neighbourhood_cleansed" as "neighbourhood", 
            "estimated_revenue_l365d"::numeric as "estimated_revenue_l365d", 
            "price"::numeric as "price", 
            "review_scores_rating", 
            "bedrooms", 
            "bathrooms", 
            "property_type", 
            "room_type", 
            row_number() over (order by "estimated_revenue_l365d" desc,"price" asc,"review_scores_rating" desc) as "investment_rank"
        FROM PRACTICE_AIRBNB.PUBLIC."bristol_listings_clean"
        ORDER BY "investment_rank"
    """).to_pandas()

bristol_listings_ranked = load_bristol_listings(session)

#TITLE ---

st.title('Listing Candidates')

#INTERACTIVE ELEMENTS ---

city = st.sidebar.selectbox('City',('London','Bristol','Manchester'))

if city == 'Bristol':
    property_type_selection = bristol_listings_ranked['property_type'].unique().tolist()
else:
    property_type_selection = []

st.session_state['property_type_selection']=property_type_selection

property_type_selection = st.sidebar.multiselect('property type',property_type_selection,default=property_type_selection)

#st.write(bristol_listings_ranked.columns.tolist())
#st.stop()

#TOP THREE LISTINGS CARDS ---
#THIS FUNCTION RETURNS RELEVANT DATA FOR A SPECIFIC RANK OF LISTINGS
def get_data_at_rank(index):
    row = bristol_listings_ranked[bristol_listings_ranked['property_type'].isin(property_type_selection)].iloc[index]
    url = row['picture_url']
    desc = row['description']
    st.image(url, caption=desc)

    st.write('Yearly revenue: ', row['estimated_revenue_l365d'])
    st.write('Price per night: ', row['price'])
    st.write('Average rating: ', row['review_scores_rating'])

    st.write('Property Type: ', row['property_type'])
    st.write('Room Type: ', row['room_type'])
    st.write('Bedrooms: ',row['bedrooms'])
    st.write('Bathrooms: ',row['bathrooms'])

col1,col2,col3 = st.columns(3,border=True)

with col1:
    #FIRST BEST LISTING
    if city == 'Bristol':
        get_data_at_rank(0)
    else:
        st.write('No data')
with col2:
    #SECOND BEST LISTING
    if city =='Bristol':
        get_data_at_rank(1)
    else:
        st.write('No data')
with col3:
    #THIRD BEST LISTING
    if city == 'Bristol':
        get_data_at_rank(2)
    else:
        st.write('No data')

bristol_listings_ranked[bristol_listings_ranked['property_type'].isin(property_type_selection)]
#bristol_property_type_ranked[bristol_property_type_ranked['property_type'].isin(property_type_selection)]

with st.bottom:
    with st.expander('AI Summary'):
        st.write('This is your AI summary using persona: ',st.session_state['persona'])



