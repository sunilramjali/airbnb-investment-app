# Import python packages
import streamlit as st
import os

st.set_page_config(
    page_title = 'Landing',
    page_icon = '👋'
)
st.sidebar.success('Select a page above')

st.title("Airbnb Investment Intelligence")
st.warning(
    "LONDON 90-DAY RULE: Short-term lets in London are generally limited to 90 nights per calendar year unless planning permission is granted."
)
st.write(
    """Data-driven insights to help you find the best short-term rental opportunities in the UK. Select your investor profile to get personalised recommendations.
  """
)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()

if "persona" not in st.session_state:
    st.session_state["persona"] = None

st.markdown(
    """
    <style>
    div.stButton > button {
        width: 100%;
        height: 90px;
        font-size: 20px;
        font-weight: 600;
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

col1,col2,col3 = st.columns(3) 

persona_descriptions = {
    "Yield_Maximiser": """
    An investor focused purely on maximising annual rental income.

    **Weight distribution:** 30% Revenue, 30% Occupancy, 20% Price, 10% Rating, 10% Location.

    **Reasoning:** Revenue and occupancy together make up 60% because they are the two strongest direct indicators of financial return. Price is weighted at 20% as higher nightly rates compound revenue gains.
    """,

    "Occupancy_Optimiser": """
    An investor who prioritises keeping their property booked consistently over maximising nightly rate.

    **Weight distribution:** 40% Occupancy, 20% Revenue, 20% Rating, 10% Price, 10% Location.

    **Reasoning:** Occupancy dominates at 40% because consistent bookings are the core goal. Rating is elevated to 20% compared to other personas as higher-rated properties attract more repeat bookings and stay booked longer.
    """,

    "Quality_Host": """
    An investor focused on delivering a premium guest experience.

    **Weight distribution:** 40% Rating, 20% Occupancy, 20% Price, 10% Revenue, 10% Location.

    **Reasoning:** Rating dominates at 40% as guest satisfaction is the primary goal. Price is inverted as this persona actively avoids overpricing, as it risks negative reviews and lower satisfaction scores.
    """
}


with col1: 
    fti = st.button('**Yield Maximiser**',type="primary" if st.session_state["persona"] == "Yield_Maximiser" else "secondary", use_container_width=True) 
with col2: el = st.button('**Occupancy Optimiser**',type="primary" if st.session_state["persona"] == "Occupancy_Optimiser" else "secondary", use_container_width=True) 

with col3: pis = st.button('**Quality Host**',type="primary" if st.session_state["persona"] == "Quality_Host" else "secondary", use_container_width=True) 

if fti:
    st.session_state["persona"] = "Yield_Maximiser"
    st.rerun()

if el:
    st.session_state["persona"] = "Occupancy_Optimiser"
    st.rerun()

if pis:
    st.session_state["persona"] = "Quality_Host"
    st.rerun()

selected_persona = st.session_state["persona"]

if selected_persona is None:
    st.write("You have chosen: ", None)
else:
    #st.write("You have chosen:", selected_persona)
    st.markdown(persona_descriptions[selected_persona])
    if st.button("Continue to Area Overview", use_container_width=True):
        st.switch_page("pages/1_area_overview.py")

