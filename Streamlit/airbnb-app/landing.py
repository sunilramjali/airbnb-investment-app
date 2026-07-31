# Streamlit landing page: marketing/info page, links out to Get Started for persona selection.
# Co-authored with CoCo
# Import python packages
import streamlit as st
from styles import apply_theme, TEXT_DARK
from nav import render_nav_links
from asset_utils import get_asset_uri

st.set_page_config(page_title="BnB Invest", page_icon="🏡", layout='wide')

apply_theme(bottom_panel=True)

render_nav_links()

st.markdown(
    """
    <style>
    @keyframes heroReveal {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes heroFadeUp {
        from { opacity: 0; transform: translateY(24px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes heroZoom {
        from { opacity: 0; transform: scale(0.96); }
        to   { opacity: 1; transform: scale(1); }
    }

    .st-key-hero {
        /* Very soft radial glow for depth — existing white/coral palette, just a hint of warmth. */
        background: radial-gradient(ellipse 900px 400px at 50% -10%, rgba(242,99,89,0.07), transparent 70%);
        padding: 12px 0 8px 0;
    }
    .st-key-hero h1 {
        animation: heroReveal 0.9s ease-out both;
    }
    .st-key-hero .landing-subheading {
        color: #F2897E !important;
        animation: heroFadeUp 0.8s ease-out both;
        animation-delay: 0.15s;
    }
    .st-key-hero [data-testid="stMarkdownContainer"] p {
        animation: heroFadeUp 0.8s ease-out both;
        animation-delay: 0.3s;
    }
    .st-key-hero .st-key-cta_get_started {
        animation: heroZoom 0.7s ease-out both;
        animation-delay: 0.5s;
    }
    .st-key-cta_get_started div.stButton > button {
        height: auto !important;
        padding: 16px 20px !important;
        background: linear-gradient(135deg, #F26359, #E8442F) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.01em;
        box-shadow: 0 6px 18px rgba(242, 99, 89, 0.4) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .st-key-cta_get_started div.stButton > button p {
        color: white !important;
    }
    .st-key-cta_get_started div.stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 24px rgba(242, 99, 89, 0.55) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="hero"):
    st.title("Airbnb Investment Intelligence")
    st.markdown(
        "<h3 class='landing-subheading'>Find where your next short-term rental should be</h3>",
        unsafe_allow_html=True,
    )
    st.write(
        """Compare neighbourhoods, property types, and real listings across London, Bristol, and Greater Manchester, scored against what matters most to you.
      """
    )

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    cta_col1, cta_col2, cta_col3 = st.columns([2, 1, 2])
    with cta_col2:
        with st.container(key="cta_get_started"):
            if st.button("Get Started →", type="primary", use_container_width=True):
                st.switch_page("pages/0_Get_Started.py")

# ── KPI stat cards ───────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .kpi-value {
        font-size: 2.1rem;
        font-weight: 700;
        color: #F26359;
        text-align: center;
        line-height: 1.1;
    }
    .kpi-label {
        font-family: monospace;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #333333;
        text-align: center;
        margin-top: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

KPIS = [
    ("1,000+", "Listings Analysed"),
    ("3", "UK Cities Covered"),
    ("3", "Investor Personas"),
    ("4", "Data Sources"),
]

kpi_cols = st.columns(4, border=True)
for col, (value, label) in zip(kpi_cols, KPIS):
    with col:
        st.markdown(f"<div class='kpi-value'>{value}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='kpi-label'>{label}</div>", unsafe_allow_html=True)

# ── What this app does ────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .st-key-what_this_app_does {
        background-color: #FBE0C8;
        padding: 24px 20px 32px;
        margin-top: 32px;
        width: auto;
        max-width: 100vw !important;
        position: relative;
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        overflow: visible !important;
        box-sizing: border-box;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="what_this_app_does"):
    st.markdown("<h3 style='text-align:center;'>What This App Does</h3>", unsafe_allow_html=True)
    st.write(
        "BnB Invest analyses Airbnb listing performance, sale prices, and local amenities "
        "across London, Bristol, and Greater Manchester to help you find where a short-term "
        "rental is most likely to perform well — and why."
    )

    _ICON_ATTRS = 'width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'

    ICON_BAR_CHART = f'<svg xmlns="http://www.w3.org/2000/svg" {_ICON_ATTRS}><line x1="4" y1="20" x2="4" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="20" y1="20" x2="20" y2="14"/></svg>'
    ICON_TARGET = f'<svg xmlns="http://www.w3.org/2000/svg" {_ICON_ATTRS}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/></svg>'
    ICON_MAP_PIN = f'<svg xmlns="http://www.w3.org/2000/svg" {_ICON_ATTRS}><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
    ICON_DOCUMENT = f'<svg xmlns="http://www.w3.org/2000/svg" {_ICON_ATTRS}><rect x="4" y="3" width="16" height="18" rx="2"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="12" y2="16"/></svg>'

    ADVANTAGES = [
        (ICON_BAR_CHART, "Data-driven scoring", "Every neighbourhood and property type is ranked using real listing revenue, occupancy, and rating data — not guesswork."),
        (ICON_TARGET, "Persona-based results", "Recommendations are tailored to what you actually care about: yield, occupancy, or guest experience."),
        (ICON_MAP_PIN, "Local context built in", "Points of interest, transport links, and dining density are factored into every area's score."),
        (ICON_DOCUMENT, "AI-generated summaries", "Plain-English investment summaries, strengths, and risks for every area and property type."),
    ]

    adv_cols = st.columns(4, border=True)
    for col, (icon, heading, description) in zip(adv_cols, ADVANTAGES):
        with col:
            st.markdown(f"<div style='color:#F26359;text-align:center;'>{icon}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-weight:700;text-align:center;margin-bottom:4px;'>{heading}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.85rem;text-align:center;color:#333333;'>{description}</div>", unsafe_allow_html=True)

# ── How it works ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .st-key-how_it_works {
        background-color: #F5C4A0;
        padding: 24px 20px 56px;
        margin-top: -32px;
        width: auto;
        max-width: 100vw !important;
        position: relative;
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        overflow: visible !important;
        box-sizing: border-box;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="how_it_works"):
    st.markdown("<h3 style='text-align:center;margin-top:0;'>How It Works</h3>", unsafe_allow_html=True)

    HOW_IT_WORKS = [
        ("Choose your persona", "Pick the investor profile that matches your goal: Yield Maximiser, Occupancy Optimiser, or Quality Host."),
        ("Explore areas", "Browse ranked neighbourhoods across London, Bristol, and Greater Manchester, and star your top 3."),
        ("Compare property types", "See which property types and bedroom counts perform best in your starred neighbourhoods."),
        ("Review listing candidates", "Get the top 10 real listings matching your criteria, with an AI-generated comparison."),
    ]

    step_cols = st.columns(4)
    for i, (col, (heading, description)) in enumerate(zip(step_cols, HOW_IT_WORKS), start=1):
        with col:
            st.markdown(
                f"""<div style='
                    display: flex; align-items: center; justify-content: center;
                    width: 32px; height: 32px; border-radius: 50%; margin: 0 auto 8px;
                    background-color: #F26359; color: white;
                    font-size: 16px; font-weight: 700;
                '>{i}</div>""",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div style='font-weight:700;text-align:center;margin-bottom:4px;'>{heading}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.85rem;text-align:center;color:#333333;'>{description}</div>", unsafe_allow_html=True)

# ── Built-with logo marquee ──────────────────────────────────────────────────
TECH_STACK = [
    ("airbnb", "Inside Airbnb", 52),
    ("claude", "Claude", 40),
    ("openai", "OpenAI", 40),
    ("snowflake", "Snowflake", 40),
    ("streamlit", "Streamlit", 52),
]
tech_logos = [(get_asset_uri(f"logo_{stem}") or get_asset_uri(stem), label, size) for stem, label, size in TECH_STACK]
tech_logos = [(uri, label, size) for uri, label, size in tech_logos if uri]
tech_items_html = "".join(
    f'''<div class="tech-item">
        <img src="{uri}" alt="{label}" style="height:{size}px;" />
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

FAQ_BG = "#454545"  # lighter than the footer background below it
FAQ_TEXT = "#F2F2F2"

st.markdown(
    f"""
    <style>
    .st-key-faq_section {{
        background-color: {FAQ_BG};
        padding: 32px 20px;
        width: auto;
        max-width: 100vw !important;
        position: relative;
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        margin-top: 32px;
        overflow: visible !important;
        box-sizing: border-box;
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
    margin-top: -16px;
    padding: 20px;
    background-color: #2E2E2E;
    text-align: center;
    width: auto;
    position: relative;
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
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
