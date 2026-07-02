import streamlit as st
import os
from snowflake.snowpark.functions import st_x, st_y

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

st.set_page_config(layout = 'wide')

#TITLE ---

st.title('Area Overview')
st.subheader('Use the filters in the sidebar and find the best area for your investment')

#SQL QUERY ---
@st.cache_data(ttl=600)
def load_bristol_area(_session):
    return _session.sql(
    """
        SELECT "neighbourhood_cleansed" as neighbourhood,
            avg("estimated_revenue_l365d"::numeric) as average_annual_revenue,
            avg("price"::numeric) as average_price, 
            count("id") as listings_count,
            ST_Y(ST_CENTROID(ST_COLLECT(TO_GEOGRAPHY("GEOGRAPHY")))) as lat,
            ST_X(ST_CENTROID(ST_COLLECT(TO_GEOGRAPHY("GEOGRAPHY")))) as lon,
            row_number() over (order by average_annual_revenue desc,average_price asc) as investment_rank
        FROM PRACTICE_AIRBNB.PUBLIC."bristol_listings_clean"
        GROUP BY "neighbourhood_cleansed"
        ORDER BY investment_rank
    """
    ).to_pandas()

bristol_area = load_bristol_area(session)

#INTERACTIVE ELEMENTS ---

city = st.sidebar.selectbox('City',('London','Bristol','Manchester'))

if city == 'Bristol':
    st.session_state['bristol_neighbourhoods'] = bristol_area['NEIGHBOURHOOD'].tolist()
else:
    st.session_state['bristol_neighbourhoods'] = []

area = st.sidebar.selectbox('Area', st.session_state['bristol_neighbourhoods'])

#VISUALISATIONS ---



acol1,acol2,acol3 = st.columns([1,1,1],border=True)

def find_best_neighbourhoods(index):
    row = bristol_area.iloc[index]
    st.subheader(str(index+1)+'. '+row['NEIGHBOURHOOD'])
    st.metric('Average annual revenue',f"£{row['AVERAGE_ANNUAL_REVENUE']:,.0f}")
    st.metric('Average price charged per night',f"£{row['AVERAGE_PRICE']:,.0f}")
    st.metric('Number of listings: ',f"{row['LISTINGS_COUNT']}")

with acol1:
    if city =='Bristol':
        find_best_neighbourhoods(0)
    else:
        st.write('No data')
with acol2:
    if city =='Bristol':
        find_best_neighbourhoods(1)
    else:
        st.write('No data')
with acol3:
    if city =='Bristol':
        find_best_neighbourhoods(2)
    else:
        st.write('No data')

if city == 'Bristol':
    st.map(bristol_area)
else:
    st.map()

col1,col2,col3,col4,col5 = st.columns(5,border=True)

with col1:
    if city == 'Bristol':
        st.metric('Average ROI ',f"£{bristol_area['AVERAGE_ANNUAL_REVENUE'][bristol_area['NEIGHBOURHOOD']==area].iloc[0]:,.0f}")
    else:
        st.write('Average Revenue: ','\nUnkown')
with col2:
    if city == 'Bristol':
        st.metric('Average nightly price',f"£{bristol_area['AVERAGE_PRICE'][bristol_area['NEIGHBOURHOOD']==area].iloc[0]:,.2f}")
    else:
        st.write('Average Nightly Price: ','\nUnknown')
with col3:
    st.metric('Number of listings',f"{bristol_area['LISTINGS_COUNT'][bristol_area['NEIGHBOURHOOD']==area].iloc[0]}")
with col4:
    st.write('Nighlife Venues: TBC')
with col5:
    st.write('Tourist Attractions: TBC')

with st.bottom:
    with st.expander('AI Summary'):
        st.write('This is your AI summary using persona: ',st.session_state['persona'])
