import streamlit as st
import os
from snowflake.snowpark.functions import st_x, st_y



conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

st.title('Methodology and Risks')



