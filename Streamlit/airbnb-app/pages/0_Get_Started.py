# Get Started page: city, budget, and investor persona selection, the first step of the main flow.
import streamlit as st
from db import get_session
from styles import apply_theme, CORAL
from nav import render_breadcrumb
from asset_utils import get_asset_uri
import persist

st.set_page_config(page_title="Get Started - BnB Invest", page_icon="🏡", layout='wide')

apply_theme()

render_breadcrumb("get_started")

session = get_session()

st.title('Get Started')

# ── 1. Cities ────────────────────────────────────────────────────────────────
st.subheader('Select which cities to include in your search.')

#City cards (also act as the city filter — click to toggle a city on/off)
CITIES = ["London", "Manchester", "Bristol"]
# Display name -> actual CITY value in the data (the mart uses "Greater Manchester").
CITY_VALUES = {"London": "London", "Manchester": "Greater Manchester", "Bristol": "Bristol"}

if 'selected_cities' not in st.session_state:
    st.session_state['selected_cities'] = persist.get_cities(CITIES)

selected_display_cities = st.session_state['selected_cities']

city_button_css = ""
for name in CITIES:
    uri = get_asset_uri(name.lower())
    bg_img = f"url('{uri}')" if uri else "none"
    bg_fallback = "#1a1a1a" if uri else "linear-gradient(135deg, #7A2E2A, #F26359)"
    is_selected = name in selected_display_cities
    shadow = (
        f"inset 0 0 0 3px {CORAL}, 0 6px 16px rgba(0,0,0,0.25)"
        if is_selected else "0 2px 12px rgba(0,0,0,0.08)"
    )
    filter_css = "none" if is_selected else "brightness(0.6) saturate(0.7)"
    city_button_css += f"""
    .st-key-city_{name} div.stButton > button {{
        position: relative !important;
        height: 220px !important; width: 100% !important; border: none !important;
        border-radius: 12px !important;
        background-image: linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 100%), {bg_img} !important;
        background-size: cover !important; background-position: center !important;
        background-color: {bg_fallback} !important;
        display: flex !important; align-items: flex-end !important; justify-content: flex-start !important;
        padding: 12px 16px !important; color: #ffffff !important; font-size: 1.15rem !important;
        font-weight: 700 !important; letter-spacing: -0.02em !important; text-align: left !important;
        text-shadow: 0 1px 4px rgba(0,0,0,0.8) !important;
        box-shadow: {shadow} !important;
        filter: {filter_css};
        transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
    }}
    .st-key-city_{name} div.stButton > button p {{
        color: #ffffff !important;
    }}
    .st-key-city_{name} div.stButton > button:hover {{
        height: 220px !important; width: 100% !important; border: none !important;
        border-radius: 12px !important;
        background-image: linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 100%), {bg_img} !important;
        background-size: cover !important; background-position: center !important;
        background-color: {bg_fallback} !important;
        color: #ffffff !important; font-size: 1.15rem !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(0,0,0,0.2) !important;
        transform: translateY(-2px);
        filter: none;
    }}
    .st-key-city_{name} div.stButton > button:hover p {{
        color: #ffffff !important;
    }}
    """

st.markdown(f"<style>{city_button_css}</style>", unsafe_allow_html=True)

city_cols = st.columns(len(CITIES), gap="medium")
for col, name in zip(city_cols, CITIES):
    with col:
        if st.button(name, key=f"city_{name}", use_container_width=True):
            s = set(selected_display_cities)
            if name in s:
                if len(s) > 1:
                    s.discard(name)
            else:
                s.add(name)
            st.session_state['selected_cities'] = [c for c in CITIES if c in s]
            persist.set_cities(st.session_state['selected_cities'])
            st.rerun()

# ── 2. Budget ────────────────────────────────────────────────────────────────
st.divider()
st.subheader('Set your maximum budget.')

if 'max_budget' not in st.session_state:
    st.session_state['max_budget'] = persist.get_budget(1_000_000)

budget_col, budget_empty_col = st.columns([1, 3])
with budget_col:
    max_budget = st.slider(
        'Maximum budget (median sale price)',
        min_value=0,
        max_value=1_000_000,
        value=st.session_state['max_budget'],
        step=25_000,
        format="£%d",
    )
    if max_budget != st.session_state['max_budget']:
        st.session_state['max_budget'] = max_budget
        persist.set_budget(max_budget)

# ── 3. Investor Profile ───────────────────────────────────────────────────────
st.divider()
st.subheader('Select the investor profile that matches your goal to get tailored recommendations.')

if "persona" not in st.session_state:
    st.session_state["persona"] = persist.get_persona()

col1, col2, col3 = st.columns(3)

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
    persist.set_persona("Yield_Maximiser")
    st.rerun()

if el:
    st.session_state["persona"] = "Occupancy_Optimiser"
    persist.set_persona("Occupancy_Optimiser")
    st.rerun()

if pis:
    st.session_state["persona"] = "Quality_Host"
    persist.set_persona("Quality_Host")
    st.rerun()

selected_persona = st.session_state["persona"]

if selected_persona is None:
    st.caption("Select an investor profile above to see tailored recommendations.")
else:
    st.markdown(persona_descriptions[selected_persona])
    if st.button("Continue to Area Overview", use_container_width=True):
        st.switch_page("pages/1_area_overview.py")
