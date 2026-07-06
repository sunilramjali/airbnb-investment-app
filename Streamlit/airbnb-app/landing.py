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

persona = 'No persona selected'

with col1:
    fti = st.button('Yield Maximiser',type='secondary')
with col2:
    el = st.button('Occupancy Optimiser',type='secondary')
with col3:
    pis = st.button('Quality Host',type='secondary')

if fti:
    persona = 'Yield_Maximiser'
if el:
    persona = 'Occupancy_Optimiser'
if pis:
    persona = 'Quality_Host'

st.write('You have chosen: ',persona)
st.session_state['persona'] = persona

#st.code('st.session_state')
#st.session_state