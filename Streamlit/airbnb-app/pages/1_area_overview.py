import streamlit as st
import os
from snowflake.snowpark.functions import st_x, st_y

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

st.title('Area Overview')


bristol_area = session.sql("""
SELECT "neighbourhood_cleansed" as neighbourhood, avg("estimated_revenue_l365d"::numeric) as average_annual_revenue, avg("price"::numeric) as average_price, ST_Y(ST_CENTROID(ST_COLLECT(TO_GEOGRAPHY("GEOGRAPHY")))) as lat,
ST_X(ST_CENTROID(ST_COLLECT(TO_GEOGRAPHY("GEOGRAPHY")))) as lon
FROM PRACTICE_AIRBNB.PUBLIC."bristol_listings_clean"
GROUP BY "neighbourhood_cleansed"
                      """
).to_pandas()

city = st.sidebar.selectbox('City',('London','Bristol','Manchester'))

if city == 'Bristol':
    area_options = bristol_area['NEIGHBOURHOOD'].tolist()
else:
    area_options = []

area = st.sidebar.selectbox('Area', area_options)

col1,col2,col3,col4 = st.columns(4,border=True)

with col1:
    st.write('Average ROI: ')
with col2:
    st.write('Average Nightly Price: ')
with col3:
    st.write('Nighlife Venues: TBC')
with col4:
    st.write('Tourist Attractions: TBC')

if city == 'Bristol':
    st.map(bristol_area)
else:
    st.map()

with st.bottom:
    with st.expander('AI Summary'):
        st.write('This is your AI summary')
