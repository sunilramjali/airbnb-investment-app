# Streamlit landing page: investor persona selection and navigation.
# Co-authored with CoCo
# Import python packages
import streamlit as st
from db import get_session
from styles import apply_theme, TEXT_DARK
from nav import render_nav_links
from asset_utils import get_asset_uri

st.set_page_config(page_title="BnB Invest", page_icon="🏡", layout='wide')

apply_theme(bottom_panel=True)

render_nav_links()

st.title("Airbnb Investment Intelligence")
st.markdown(
    """
    <style>
    .landing-subheading {
        color: #F2897E !important;
    }
    </style>
    <h3 class="landing-subheading">Data-driven insights for UK short-term rental investors</h3>
    """,
    unsafe_allow_html=True,
)
st.warning(
    "LONDON 90-DAY RULE: Short-term lets in London are generally limited to 90 nights per calendar year unless planning permission is granted."
)
st.write(
    """Data-driven insights to help you find the best short-term rental opportunities in the UK. Select your investor profile to get personalised recommendations.
  """
)

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

# ── What this app does ────────────────────────────────────────────────────────
st.markdown("<h3 style='text-align:center;'>What This App Does</h3>", unsafe_allow_html=True)
st.write(
    "BnB Invest analyses Airbnb listing performance, sale prices, and local amenities "
    "across London, Bristol, and Greater Manchester to help you find where a short-term "
    "rental is most likely to perform well — and why."
)

ADVANTAGES = [
    ("\U0001F4CA", "Data-driven scoring", "Every neighbourhood and property type is ranked using real listing revenue, occupancy, and rating data — not guesswork."),
    ("\U0001F3AF", "Persona-based results", "Recommendations are tailored to what you actually care about: yield, occupancy, or guest experience."),
    ("\U0001F5FA️", "Local context built in", "Points of interest, transport links, and dining density are factored into every area's score."),
    ("\U0001F916", "AI-generated summaries", "Plain-English investment summaries, strengths, and risks for every area and property type."),
]

adv_cols = st.columns(4, border=True)
for col, (icon, heading, description) in zip(adv_cols, ADVANTAGES):
    with col:
        st.markdown(f"<div style='font-size:28px;text-align:center;'>{icon}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-weight:700;text-align:center;margin-bottom:4px;'>{heading}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:0.85rem;text-align:center;color:#333333;'>{description}</div>", unsafe_allow_html=True)

# ── Built-with logo marquee ──────────────────────────────────────────────────
TECH_STACK = [
    ("airbnb", "Inside Airbnb", 48),
    ("claude", "Claude", 32),
    ("openai", "OpenAI", 32),
    ("databricks", "Databricks", 48),
    ("streamlit", "Streamlit", 48),
]
tech_logos = [(get_asset_uri(f"logo_{stem}") or get_asset_uri(stem), label, size) for stem, label, size in TECH_STACK]
tech_logos = [(uri, label, size) for uri, label, size in tech_logos if uri]
tech_items_html = "".join(
    f'''<div class="tech-item">
        <img src="{uri}" alt="{label}" style="height:{size}px;" />
        <span>{label}</span>
    </div>'''
    for uri, label, size in tech_logos
)
tech_section_html = f'''
<style>
.tech-section {{
    margin-top: 48px;
    text-align: center;
}}
.tech-label {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {TEXT_DARK};
    margin-bottom: 12px;
}}
.tech-track {{
    display: flex;
    width: 100%;
    justify-content: space-evenly;
    flex-wrap: wrap;
    gap: 40px;
}}
.tech-item {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}}
.tech-item img {{
    filter: grayscale(100%);
    opacity: 0.5;
    transition: filter 0.2s ease, opacity 0.2s ease;
}}
.tech-item:hover img {{
    filter: grayscale(0%);
    opacity: 1;
}}
.tech-item span {{
    font-size: 14px;
    font-weight: 600;
    color: #000000;
    white-space: nowrap;
}}
</style>
<div class="tech-section">
    <div class="tech-label">Built With</div>
    <div class="tech-track">
        {tech_items_html}
    </div>
</div>
''' if tech_logos else ""

st.markdown(tech_section_html, unsafe_allow_html=True)

# ── FAQ ───────────────────────────────────────────────────────────────────────
FAQ = [
    (
        "What data does this app use?",
        "Airbnb listing data for London, Bristol, and Greater Manchester, combined with "
        "HM Land Registry sale prices, points of interest, transport links, and rental "
        "market statistics.",
    ),
    (
        "How is the investment score calculated?",
        "Each neighbourhood and property type is scored against your selected investor "
        "persona (Yield Maximiser, Occupancy Optimiser, or Quality Host), which weights "
        "revenue, occupancy, rating, price, and location differently depending on your goal.",
    ),
    (
        "What is the London 90-day rule?",
        "Short-term lets in London are generally limited to 90 nights per calendar year "
        "unless planning permission is granted. Factor this into any yield estimate for "
        "London properties.",
    ),
    (
        "Can I use this for investment advice?",
        "This tool surfaces data-driven insights to help inform your research, but it "
        "is not financial or investment advice. Always do your own due diligence before "
        "committing to a purchase.",
    ),
]

FAQ_BG = "#2E2E2E"  # matches the footer background
FAQ_TEXT = "#F2F2F2"

st.markdown(
    f"""
    <style>
    [data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-faq_section) {{
        overflow: visible !important;
    }}
    .st-key-faq_section {{
        background-color: {FAQ_BG};
        padding: 32px 20px;
        width: 100vw;
        position: relative;
        left: 50%;
        right: 50%;
        margin-left: -50vw;
        margin-right: -50vw;
        margin-top: 32px;
        overflow: visible !important;
    }}
    .st-key-faq_section h3 {{
        color: {FAQ_TEXT} !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] {{
        background-color: transparent !important;
        border-color: #4A4A4A !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] summary {{
        background-color: #3D3D3D !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] summary:hover {{
        background-color: #4A4A4A !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] details[open] summary {{
        background-color: #3D3D3D !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] summary p,
    .st-key-faq_section [data-testid="stMarkdownContainer"] p {{
        color: {FAQ_TEXT} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="faq_section"):
    st.markdown("<h3 style='text-align:center;'>Frequently Asked Questions</h3>", unsafe_allow_html=True)
    for question, answer in FAQ:
        with st.expander(question):
            st.write(answer)

# ── Footer constants ──────────────────────────────────────────────────────────
LINKEDIN_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M22.23 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.46c.98 0 1.77-.77 1.77-1.72V1.72C24 .77 23.21 0 22.23 0zM7.06 20.45H3.56V9h3.5v11.45zM5.31 7.43c-1.12 0-2.03-.92-2.03-2.05 0-1.13.91-2.05 2.03-2.05 1.12 0 2.03.92 2.03 2.05 0 1.13-.91 2.05-2.03 2.05zM20.45 20.45h-3.5v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.44-2.13 2.94v5.67h-3.5V9h3.36v1.56h.05c.47-.89 1.62-1.85 3.34-1.85 3.57 0 4.23 2.35 4.23 5.41v6.33z"/></svg>'
GITHUB_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.57.11.78-.25.78-.55 0-.27-.01-1.16-.02-2.11-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.26-1.28-5.26-5.7 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.58.24 2.75.12 3.04.74.81 1.18 1.84 1.18 3.1 0 4.43-2.71 5.4-5.28 5.69.42.36.78 1.08.78 2.18 0 1.57-.01 2.84-.01 3.23 0 .31.21.67.79.55A10.51 10.51 0 0 0 23.5 12c0-6.27-5.23-11.5-11.5-11.5z"/></svg>'

TEAM = [
    ("Adam Choy",      "https://www.linkedin.com/in/adam-choy-b95715190/"),
    ("Sunil Ramjali",  "https://www.linkedin.com/in/sunilramjali/"),
    ("Kanmani Vijay",  "https://www.linkedin.com/in/kanmani-vijay-8451a322b/"),
]

GITHUB_URL = "https://github.com/sunilramjali/airbnb-investment-app"
DATA_SOURCES = "Inside Airbnb, HM Land Registry, Overture Maps"

team_links = " &middot; ".join([
    f'<a href="{url}" target="_blank" style="color:var(--text);text-decoration:none;'
    f'display:inline-flex;align-items:center;gap:5px;font-size:0.82rem;">'
    f'{LINKEDIN_ICON} {name}</a>'
    for name, url in TEAM
])

github_link = (
    f'<a href="{GITHUB_URL}" target="_blank" style="color:var(--text);text-decoration:none;'
    f'display:inline-flex;align-items:center;gap:5px;font-size:0.82rem;">'
    f'{GITHUB_ICON} View on GitHub</a>'
)

FOOTER_TEXT = "#F2F2F2"  # light, for readability on the dark footer background

footer_html = f'''
<style>
:root {{
    --text: {FOOTER_TEXT};
}}
/* Streamlit reserves bottom padding on the page by default; drop it so the
   footer sits flush against the true bottom of the page. */
.block-container,
[data-testid="stMainBlockContainer"] {{
    padding-bottom: 0 !important;
}}
.app-footer {{
    margin-top: 32px;
    padding: 20px;
    background-color: #2E2E2E;
    text-align: center;
    width: 100vw;
    position: relative;
    left: 50%;
    right: 50%;
    margin-left: -50vw;
    margin-right: -50vw;
}}
.app-footer .footer-label {{
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {FOOTER_TEXT};
    margin-bottom: 10px;
}}
.app-footer a:hover {{
    color: #0a66c2 !important;
}}
.app-footer .footer-divider {{
    width: 100%;
    max-width: 400px;
    margin: 16px auto;
    border: none;
    border-top: 1px solid #4A4A4A;
}}
.app-footer .footer-meta {{
    font-size: 0.78rem;
    color: #B5B5B5;
    line-height: 1.6;
}}
</style>
<div class="app-footer">
    <div class="footer-label">Made By</div>
    <div>{team_links}</div>
    <hr class="footer-divider" />
    <div>{github_link}</div>
    <div class="footer-meta">
        Data sourced from {DATA_SOURCES}.<br/>
        &copy; 2026 BnB Invest. For research purposes only &mdash; not financial advice.
    </div>
</div>
'''

st.markdown(footer_html, unsafe_allow_html=True)

