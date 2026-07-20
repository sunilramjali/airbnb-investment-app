# Streamlit landing page: investor persona selection plus a temporary Gemini live-API check.
# Co-authored with CoCo
# Import python packages
import streamlit as st
from db import get_session

#CUSTOM CSS SCRIPT FOR PAGE LOOK
st.markdown(
    """
    <style>
    /* Main app */
    .stApp {
        background-color: white !important;
    }

    [data-testid="stFullScreenFrame"] {
        background-color: white !important;
    }

    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {
        left: 0px !important;
        right: auto !important;
        width: 62% !important;
        max-width: 950px !important;
        min-width: 500px !important;
        margin-left: 0px !important;
        margin-right: auto !important;
        transform: none !important;
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        border-top: none !important;
        pointer-events: none !important;
        bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        padding-bottom: 0 !important;
    }

    [data-testid="stBottomBlockContainer"] > div {
        margin-left: 0px !important;
        margin-right: auto !important;
        width: 100% !important;
        max-width: 950px !important;
        background-color: white !important;
        border: 1px solid #f26359 !important;
        border-radius: 12px !important;
        padding: 16px !important;
        pointer-events: auto !important;
        max-height: 42vh !important;
        overflow-y: auto !important;
    }
    [data-testid="stBottomBlockContainer"] [data-testid="stVerticalBlock"] {
        margin-left: 0px !important;
        margin-right: auto !important;
        width: 100% !important;
    }

    [data-testid="stBottomBlockContainer"] [data-testid="stElementContainer"] {
        margin-left: 0px !important;
        margin-right: auto !important;
    }

    [data-testid="stExpander"] summary {
        background-color: #f8d9d3 !important;
    }

    [data-testid="stExpander"] summary:hover {
        background-color: #f26359 !important;
    }

    [data-testid="stExpander"] details[open] summary {
        background-color: #f8d9d3 !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        display: none !important;
    }

    [data-testid="collapsedControl"] {
        display: none !important;
    }
    
    section[data-testid="stSidebar"] {
        background-color: white !important;
        display: none !important;
    }

    [data-testid="stSelectbox"] input {
        background-color: #f8d9d3 !important;
        color: #f26359 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    [data-testid="stSelectbox"] button {
        background-color: #f8d9d3 !important;
    }

    /* Big headings */
    h1, h2 {
        color: #f26359 !important;
    }

    /* Smaller headings */
    h3, h4, h5, h6 {
        color: #000000 !important;
    }

    /* Normal markdown text */
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: #000000 !important;
    }

    /* Captions */
    [data-testid="stCaptionContainer"] {
        color: #000000 !important;
    }

    div[data-testid="stAlert"] {
        background-color: #FCEDEA !important;
        color: #7A2E2A !important;
        border: 1px solid #F26359 !important;
        border-left: 6px solid #F26359 !important;
        border-radius: 12px !important;
    }

    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        color: #7A2E2A !important;
    }

    /* Metrics */
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        color: #000000 !important;
    }

    /* Buttons */
    div.stButton > button[kind="secondary"] {
        background-color:#FFFAF0 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
        border-radius: 12px !important;
    }

    div.stButton > button[kind="secondary"]:hover {
        background-color: #f8d9d3 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
    }

    div.stButton > button[kind="primary"] {
        background-color: #f8d9d3 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: #f8d9d3 !important;
        border: 2px solid #f26359 !important;
        border-radius: 12px !important;
    }

    div.stButton > button p {
        white-space: pre-line !important;
        text-align: center !important;
        line-height: 1.3 !important;
    }

    [data-testid="stLinkButton"] a {
        background-color:#FFFAF0 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
        border-radius: 12px !important;
    }

    [data-testid="stLinkButton"] a:hover {
        background-color: #f8d9d3 !important;
        width: 100% !important;
        height: 90px !important;
        font-size: 20px !important;
        font-weight: 600 !important;
        color: white !important;
        border: 2px solid #F4EFEB !important;
    }

     /* Multiselect outer box */
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        background-color: #f8d9d3 !important;
    }

    /* Text typed inside the multiselect */
    [data-testid="stMultiSelect"] input {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* Placeholder text */
    [data-testid="stMultiSelect"] input::placeholder {
        color: #7A2E2A !important;
        opacity: 1 !important;
    }

    /* Selected option boxes / tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: #f26359 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }

    /* Text inside selected tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
        color: #ffffff !important;
    }

    /* Remove icon inside selected tags */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }

    /* Dropdown menu background */
    div[data-baseweb="popover"] ul {
        background-color: #ffffff !important;
    }

    /* Dropdown options */
    div[data-baseweb="popover"] li {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    /* Dropdown option hover */
    div[data-baseweb="popover"] li:hover {
        background-color: #f8d9d3 !important;
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

empty_col, page_col1 = st.columns([7,1])
with page_col1:
    if st.button('Documentation', use_container_width = True):
        st.switch_page('pages/4_Documentation.py')

st.title("Airbnb Investment Intelligence")
st.warning(
    "LONDON 90-DAY RULE: Short-term lets in London are generally limited to 90 nights per calendar year unless planning permission is granted."
)
st.write(
    """Data-driven insights to help you find the best short-term rental opportunities in the UK. Select your investor profile to get personalised recommendations.
  """
)

# ===== GEMINI LIVE API CHECK — TEMPORARY, safe to delete this whole block =====
with st.expander("Gemini live API check"):
    if "gemini" not in st.secrets:
        st.warning("No [gemini] key found in secrets.")
    elif st.button("Test Gemini live call"):
        try:
            from gemini import generate
            reply = generate("Reply with exactly: pong")
            st.success("Gemini is working ✅")
            st.write(reply)
        except Exception as e:
            st.error(f"Gemini call failed ❌ — {e}")
# ===== END GEMINI LIVE API CHECK =====

session = get_session()

if "persona" not in st.session_state:
    st.session_state["persona"] = None

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
    st.write("You have chosen: none")
else:
    #st.write("You have chosen:", selected_persona)
    st.markdown(persona_descriptions[selected_persona])
    if st.button("Continue to Area Overview", use_container_width=True):
        st.switch_page("pages/1_area_overview.py")

