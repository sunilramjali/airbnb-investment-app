# Import python packages
import streamlit as st
import os

st.set_page_config(
    page_title = 'Landing',
    page_icon = '👋'
)
st.sidebar.success('Select a page above')

st.title("Airbnb Investment Intelligence")
st.write(
  """Data-driven insights to help you find the best short-term rental opportunities in the UK. Select your investor profile to get personalised recommendations.
  """
)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

col1,col2,col3 = st.columns(3)

persona = 'Nothing'

with col1:
    fti = st.button('First time investor',type='primary')
with col2:
    el = st.button('Experienced landlord',type='primary')
with col3:
    pis = st.button('Passive income seeker',type='primary')

if fti:
    persona = 'First time investor'
if el:
    persona = 'Experienced landlord'
if pis:
    persona = 'Passive income seeker'

st.write('You have chosen: ',persona)