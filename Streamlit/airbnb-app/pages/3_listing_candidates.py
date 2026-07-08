import streamlit as st
import os

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

#SQL QUERY ---
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
#listings_ranked
#st.stop()
#TITLE ---

st.title('Listing Candidates')
st.subheader('Use the filters in the sidebar to find your perfect listing')

#INTERACTIVE ELEMENTS ---

city = st.sidebar.selectbox('City',('All','London','Bristol','Manchester'))

if city != None:
    property_type_selection = listings_ranked['PROPERTY_TYPE'].unique().tolist()
else:
    property_type_selection = []

st.session_state['property_type_selection']=property_type_selection

property_type_selection = st.sidebar.multiselect('Property type',property_type_selection,default=property_type_selection)

def clear_saved():
    st.session_state['saved_listings']=set()

st.sidebar.button('Clear saved listings',on_click=clear_saved)

#st.write(listings_ranked.columns.tolist())
#st.stop()

#TOP THREE LISTINGS CARDS ---
#THIS FUNCTION RETURNS RELEVANT DATA FOR A SPECIFIC RANK OF LISTINGS
def get_data_at_rank(index,cty):
    if cty != 'All':
        row = listings_ranked[(listings_ranked['PROPERTY_TYPE'].isin(property_type_selection))&(listings_ranked['CITY']==cty)].iloc[index]
    else:
        row = listings_ranked[listings_ranked['PROPERTY_TYPE'].isin(property_type_selection)].iloc[index]

    listing_id = row['LISTING_ID']
    url = row['PICTURE_URL']
    desc = row['DESCRIPTION']
    if desc != None:
        st.image(url, caption=desc)
    else:
        st.image(url, caption='No description')

    st.checkbox(
        'Save listing',
        value=listing_id in st.session_state['saved_listings'],
        key=f'save_{listing_id}',
        on_change=toggle_save,
        args=(listing_id,)
    )

    st.write('Yearly revenue: ', row['ESTIMATED_REVENUE_L365D'])
    st.write('Price per night: ', row['PRICE'])
    st.write('Average rating: ', row['REVIEW_SCORES_RATING'])

    st.write('Property Type: ', row['PROPERTY_TYPE'])
    st.write('Room Type: ', row['ROOM_TYPE'])
    st.write('Bedrooms: ',row['BEDROOMS'])
    st.write('Bathrooms: ',row['BATHROOMS'])

    return

col1,col2,col3 = st.columns(3,border=True)

if 'saved_listings' not in st.session_state:
    st.session_state['saved_listings'] = set()

def toggle_save(listing_id):
    saved = st.session_state['saved_listings']
    if listing_id in saved:
        saved.remove(listing_id)
    else:
        saved.add(listing_id)

with col1:
    #FIRST BEST LISTING
    if city != None:
        try:
            get_data_at_rank(0,city)
        except IndexError:
            st.write('No value')
    else:
        st.write('No data')
with col2:
    #SECOND BEST LISTING
    if city != None:
        try:
            get_data_at_rank(1,city)
        except IndexError:
            st.write('No value')
    else:
        st.write('No data')
with col3:
    #THIRD BEST LISTING
    if city != None:
        try:
            get_data_at_rank(2,city)
        except IndexError:
            st.write('No value')
    else:
        st.write('No data')

#listings_ranked[listings_ranked['PROPERTY_TYPE'].isin(property_type_selection)]
#bristol_property_type_ranked[bristol_property_type_ranked['property_type'].isin(property_type_selection)]

with st.bottom:
    with st.expander('AI Summary'):
        st.write('This is your AI summary using persona: ',st.session_state['persona'])



