# Streamlit landing page: marketing/info page, links out to Get Started for persona selection.
# Co-authored with CoCo
# Import python packages
import streamlit as st
import pandas as pd
from styles import apply_theme, TEXT_DARK, CORAL, ROSEWOOD, INK, STEEL, TANGELO
from nav import render_nav_links
from asset_utils import get_asset_uri
from db import get_session

st.set_page_config(page_title="BnB Invest", page_icon="🏡", layout='wide')

apply_theme(bottom_panel=True)

render_nav_links()

# Signature element: the skyline art bookends the page — dusk here in the hero
# (arrival), a lighter dawn tone in the footer (resolution). One orchestrated
# load-in (background settles, then text arrives in sequence) replaces the
# previous scattered fade-ups + hover-lifts scattered across the page.
HERO_SKYLINE_URI = get_asset_uri("footer_skyline")

st.markdown(
    f"""
    <style>
    @keyframes heroSettle {{
        from {{ opacity: 0; transform: scale(1.04); }}
        to   {{ opacity: 1; transform: scale(1); }}
    }}
    @keyframes heroFadeUp {{
        from {{ opacity: 0; transform: translateY(18px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    /* Slow drift across the skyline, so the hero feels alive without
       distracting from the text sitting on top of it. */
    @keyframes heroKenBurns {{
        0%   {{ transform: scale(1) translate(0, 0); }}
        100% {{ transform: scale(1.08) translate(-1%, -1%); }}
    }}
    @keyframes heroTwinkle {{
        0%, 100% {{ opacity: 0.15; transform: scale(0.7); }}
        50%      {{ opacity: 1;    transform: scale(1.4); }}
    }}

    .st-key-hero {{
        position: relative;
        z-index: 0;
        overflow: hidden;
        background-color: {INK};
        border-radius: 24px;
        padding: 64px 48px;
        min-height: 440px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        animation: heroSettle 1.1s ease-out both;
    }}
    /* Skyline art, isolated on its own layer so the filter below tints the
       image without dragging the foreground text along with it. */
    .st-key-hero::before {{
        content: "";
        position: absolute;
        inset: 0;
        z-index: -1;
        background:
            linear-gradient(100deg, rgba(43,33,31,0.92) 0%, rgba(43,33,31,0.65) 42%, rgba(43,33,31,0.2) 68%, rgba(43,33,31,0) 85%),
            url('{HERO_SKYLINE_URI}') center 30% / cover no-repeat;
        filter: sepia(0.4) hue-rotate(-30deg) saturate(1.5) brightness(0.9);
        transform-origin: center 70%;
        animation: heroKenBurns 22s ease-in-out infinite alternate;
    }}
    /* A handful of faint building-light twinkles, layered above the skyline
       and below the text. */
    .hero-twinkles {{
        position: absolute;
        inset: 0;
        z-index: -1;
        pointer-events: none;
    }}
    .hero-twinkles span {{
        position: absolute;
        width: 3px;
        height: 3px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255,245,220,0.95) 0%, rgba(255,245,220,0) 70%);
        animation: heroTwinkle 3.4s ease-in-out infinite both;
    }}
    .st-key-hero h1 {{
        color: #FFFAF0 !important;
        font-size: 2.6rem !important;
        line-height: 1.15;
        max-width: 620px;
        animation: heroFadeUp 0.7s ease-out both;
        animation-delay: 0.35s;
    }}
    .st-key-hero .landing-subheading {{
        color: #F2D9D3 !important;
        font-weight: 500 !important;
        max-width: 520px;
        animation: heroFadeUp 0.7s ease-out both;
        animation-delay: 0.5s;
    }}
    .st-key-hero .hero-ticker {{
        animation: heroFadeUp 0.7s ease-out both;
        animation-delay: 0.65s;
    }}
    .st-key-hero .st-key-cta_get_started {{
        animation: heroFadeUp 0.7s ease-out both;
        animation-delay: 0.8s;
    }}
    .hero-ticker {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.82rem;
        letter-spacing: 0.05em;
        color: {STEEL};
        background: rgba(92,114,133,0.15);
        border: 1px solid rgba(92,114,133,0.4);
        border-radius: 8px;
        display: inline-block;
        padding: 8px 16px;
        margin: 20px 0 28px;
    }}
    .hero-ticker b {{
        color: #FFFAF0;
        font-weight: 600;
    }}
    .st-key-cta_get_started div.stButton > button {{
        height: auto !important;
        padding: 16px 20px !important;
        background: linear-gradient(135deg, {CORAL}, {TANGELO}) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.01em;
        box-shadow: 0 6px 18px rgba(242, 99, 89, 0.4) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .st-key-cta_get_started div.stButton > button p {{
        color: white !important;
    }}
    .st-key-cta_get_started div.stButton > button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 10px 24px rgba(242, 99, 89, 0.55) !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="hero"):
    st.markdown(
        """<div class="hero-twinkles">
            <span style="top:36%; left:54%; animation-delay:0s;"></span>
            <span style="top:44%; left:62%; animation-delay:0.9s;"></span>
            <span style="top:33%; left:70%; animation-delay:1.7s;"></span>
            <span style="top:49%; left:77%; animation-delay:0.4s;"></span>
            <span style="top:40%; left:84%; animation-delay:1.3s;"></span>
            <span style="top:53%; left:91%; animation-delay:2.1s;"></span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.title("See what it'll actually earn, before you buy it.")
    st.markdown(
        "<h3 class='landing-subheading'>London, Bristol, and Greater Manchester — "
        "scored against what you actually care about.</h3>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='hero-ticker'><b>1,000+</b> LISTINGS &nbsp;·&nbsp; "
        "<b>3</b> CITIES &nbsp;·&nbsp; <b>3</b> PERSONAS &nbsp;·&nbsp; "
        "<b>4</b> DATA SOURCES</div>",
        unsafe_allow_html=True,
    )

    cta_col1, cta_col2, cta_col3 = st.columns([2, 1, 2])
    with cta_col2:
        with st.container(key="cta_get_started"):
            if st.button("Get Started →", type="primary", use_container_width=True):
                st.switch_page("pages/0_Get_Started.py")

# ── What this app does (editorial 2-col list, not a 4-card grid) ───────────────
_ICON_ATTRS = 'width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#F26359" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
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
advantages_rows_html = "".join(
    f'''<div class="advantage-row">
        <div class="advantage-icon">{icon}</div>
        <div>
            <div class="advantage-heading">{heading}</div>
            <div class="advantage-desc">{description}</div>
        </div>
    </div>'''
    for icon, heading, description in ADVANTAGES
)

st.markdown(
    f"""
    <style>
    .st-key-what_this_app_does {{
        background-color: #FBE0C8;
        padding: 48px 20px;
        margin-top: 32px;
        width: auto;
        max-width: 100vw !important;
        position: relative;
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        overflow: visible !important;
        box-sizing: border-box;
    }}
    .st-key-what_this_app_does [data-testid="stHorizontalBlock"] {{
        max-width: 1100px;
        margin: 0 auto !important;
        align-items: flex-start !important;
    }}
    .what-app-intro h3 {{
        margin-top: 0;
    }}
    .advantage-row {{
        display: flex;
        gap: 16px;
        padding: 16px 0;
        border-top: 1px solid rgba(92,114,133,0.3);
    }}
    .advantage-row:first-child {{
        border-top: none;
    }}
    .advantage-icon {{
        flex-shrink: 0;
        margin-top: 2px;
    }}
    .advantage-heading {{
        font-weight: 700;
        margin-bottom: 4px;
    }}
    .advantage-desc {{
        font-size: 0.85rem;
        color: {INK};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="what_this_app_does"):
    intro_col, list_col = st.columns([1, 1.2], gap="large")
    with intro_col:
        st.markdown(
            """<div class="what-app-intro">
                <h3>What This App Does</h3>
                <p>BnB Invest analyses Airbnb listing performance, sale prices, and local
                amenities across London, Bristol, and Greater Manchester to help you find
                where a short-term rental is most likely to perform well &mdash; and why.</p>
            </div>""",
            unsafe_allow_html=True,
        )
    with list_col:
        st.markdown(advantages_rows_html, unsafe_allow_html=True)

# ── How it works (connected timeline — this content is a real sequence) ────────
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
    .st-key-how_it_works [data-testid="stHorizontalBlock"] {
        position: relative;
    }
    .st-key-how_it_works [data-testid="stHorizontalBlock"]::before {
        content: "";
        position: absolute;
        top: 16px;
        left: 12.5%;
        right: 12.5%;
        height: 2px;
        background: rgba(92,114,133,0.45);
        z-index: 0;
    }
    .st-key-how_it_works [data-testid="column"] {
        position: relative;
        z-index: 1;
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
                    background-color: #D92200; color: white;
                    font-size: 16px; font-weight: 700;
                '>{i}</div>""",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div style='font-weight:700;text-align:center;margin-bottom:4px;'>{heading}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:0.85rem;text-align:center;color:#333333;'>{description}</div>", unsafe_allow_html=True)

# ── Example listings: real top-scoring listings, one per city, linking out to
# the actual Airbnb listing (not fabricated placeholders).
@st.cache_data(ttl=600)
def load_example_listings(_session):
    return _session.sql(
        """
        SELECT CITY, NAME, PICTURE_URL, LISTING_URL, ADR, REVIEW_SCORES_RATING, BEDROOMS
        FROM (
            SELECT
                b.CITY,
                a.NAME,
                a.PICTURE_URL,
                a.LISTING_URL,
                a.ADR,
                a.REVIEW_SCORES_RATING,
                a.BEDROOMS,
                ROW_NUMBER() OVER (
                    PARTITION BY b.CITY
                    ORDER BY b.SCORE_YIELD_MAXIMISER DESC
                ) AS RN
            FROM AIRBNB_INVESTMENT_DB.GOLD.MART_LISTING_CANDIDATES a
            JOIN AIRBNB_INVESTMENT_DB.GOLD.INVESTMENT_SCORES b
                ON a.LISTING_ID = b.LISTING_ID
            WHERE a.PICTURE_URL IS NOT NULL
                AND a.LISTING_URL IS NOT NULL
                AND a.NAME IS NOT NULL
        )
        WHERE RN = 1
        ORDER BY CITY
        """
    ).to_pandas()

try:
    example_listings = load_example_listings(get_session())
except Exception:
    example_listings = None

st.markdown(
    f"""
    <style>
    .example-listings-title {{ text-align:center; margin: 48px 0 4px; }}
    .example-listings-sub {{ text-align:center; color:{INK}; margin-bottom:28px; }}
    .listing-card {{
        display: block;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 10px 24px rgba(0,0,0,0.10);
        background: #FFFAF0;
        border: 1px solid #F4EFEB;
        color: inherit;
        text-decoration: none;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .listing-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 14px 28px rgba(242,99,89,0.22);
    }}
    .listing-card .listing-photo {{
        position: relative;
        height: 170px;
    }}
    .listing-card .listing-photo img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }}
    .listing-card .listing-badge {{
        position: absolute;
        top: 10px;
        left: 10px;
        background: {CORAL};
        color: white;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 4px 10px;
        border-radius: 20px;
    }}
    .listing-card .listing-body {{
        padding: 14px 16px 18px;
    }}
    .listing-card .listing-name {{
        font-weight: 700;
        margin-bottom: 2px;
    }}
    .listing-card .listing-city {{
        font-size: 0.8rem;
        color: #6b6b6b;
        margin-bottom: 10px;
    }}
    .listing-card .listing-stats {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid #F4EFEB;
        padding-top: 10px;
    }}
    .listing-card .listing-price {{
        font-weight: 700;
        color: {CORAL};
    }}
    .listing-card .listing-metric {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.78rem;
        color: {STEEL};
    }}
    </style>
    <h3 class="example-listings-title">See it in action</h3>
    <p class="example-listings-sub">Real top-scoring listings from our data, one per city &mdash; click through to the actual Airbnb listing.</p>
    """,
    unsafe_allow_html=True,
)

valid_listings = []
if example_listings is not None and not example_listings.empty:
    valid_listings = [
        row for _, row in example_listings.iterrows()
        if row.get("LISTING_URL") and row.get("PICTURE_URL")
    ]

if not valid_listings:
    st.markdown(
        f"""
        <div style="
            background: #FFFAF0;
            border: 1px solid #F4EFEB;
            border-radius: 16px;
            padding: 28px;
            text-align: center;
            color: {INK};
        ">
            <div style="font-weight: 700; margin-bottom: 4px;">Listing examples are temporarily unavailable</div>
            <div style="font-size: 0.85rem; color: #6b6b6b;">Check back soon &mdash; or explore live scoring yourself in Get Started.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    listing_cols = st.columns(len(valid_listings))
    for col, row in zip(listing_cols, valid_listings):
        with col:
            listing_url = row.get("LISTING_URL")
            picture_url = row.get("PICTURE_URL")
            name = row.get("NAME") or "Listing"
            city = row.get("CITY") or ""
            rating_val = row.get("REVIEW_SCORES_RATING")
            adr_val = row.get("ADR")
            bedrooms_val = row.get("BEDROOMS")
            rating = f"{rating_val:,.2f}★" if pd.notna(rating_val) else "N/A"
            adr = f"£{adr_val:,.0f}/night" if pd.notna(adr_val) else "N/A"
            bedrooms = f"{int(bedrooms_val)}-bed" if pd.notna(bedrooms_val) else ""
            st.markdown(
                f'''<a class="listing-card" href="{listing_url}" target="_blank" rel="noopener">
                    <div class="listing-photo">
                        <img src="{picture_url}" alt="{name}"/>
                        <div class="listing-badge">Top Pick</div>
                    </div>
                    <div class="listing-body">
                        <div class="listing-name">{name}</div>
                        <div class="listing-city">{bedrooms} &middot; {city}</div>
                        <div class="listing-stats">
                            <span class="listing-price">{adr}</span>
                            <span class="listing-metric">{rating}</span>
                        </div>
                    </div>
                </a>''',
                unsafe_allow_html=True,
            )

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
    font-family: 'Space Grotesk', sans-serif;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {CORAL};
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

FAQ_BG = ROSEWOOD  # "Dusk" — one consistent dark tone, not a rotating red
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
        margin-top: 0;
        overflow: visible !important;
        box-sizing: border-box;
    }}
    .st-key-faq_section h3 {{
        color: {FAQ_TEXT} !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] {{
        background-color: transparent !important;
        border-color: rgba(255,255,255,0.35) !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] summary {{
        background-color: rgba(0,0,0,0.15) !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] summary:hover {{
        background-color: rgba(0,0,0,0.25) !important;
    }}
    .st-key-faq_section [data-testid="stExpander"] details[open] summary {{
        background-color: rgba(0,0,0,0.15) !important;
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

# ── Closing CTA banner: the skyline returns, dawn-toned (resolution) ───────────
st.markdown(
    f"""
    <style>
    .st-key-dream_banner {{
        background:
            linear-gradient(rgba(255,250,240,0.86), rgba(255,250,240,0.86)),
            url('{HERO_SKYLINE_URI}') center 40% / cover no-repeat;
        padding: 48px 40px;
        margin-top: -32px;
        width: auto;
        max-width: 100vw !important;
        position: relative;
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        overflow: visible !important;
        box-sizing: border-box;
    }}
    .st-key-dream_banner [data-testid="stHorizontalBlock"] {{
        align-items: center !important;
    }}
    .dream-banner-heading {{
        font-size: 1.7rem;
        font-weight: 700;
        line-height: 1.25;
        margin: 0;
        color: {INK};
    }}
    .st-key-cta_dream div.stButton > button {{
        height: auto !important;
        padding: 16px 28px !important;
        background: linear-gradient(135deg, {CORAL}, {TANGELO}) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        box-shadow: 0 6px 18px rgba(242, 99, 89, 0.4) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .st-key-cta_dream div.stButton > button p {{
        color: white !important;
    }}
    .st-key-cta_dream div.stButton > button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 10px 24px rgba(242, 99, 89, 0.55) !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="dream_banner"):
    banner_col1, banner_col2 = st.columns([3, 1], vertical_alignment="center")
    with banner_col1:
        st.markdown(
            "<p class='dream-banner-heading'>Let's find the investment you've been dreaming about</p>",
            unsafe_allow_html=True,
        )
    with banner_col2:
        with st.container(key="cta_dream"):
            if st.button("Get Started →", type="primary", use_container_width=True, key="btn_cta_dream"):
                st.switch_page("pages/0_Get_Started.py")

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
FOOTER_BG = "#2E2E2E"

# Skyline image above the footer, from assets/footer_skyline.svg.
FOOTER_SKYLINE_URI = get_asset_uri("footer_skyline")

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
.footer-skyline {{
    display: block;
    width: auto;
    height: 600px;
    background-image: url('{FOOTER_SKYLINE_URI}');
    background-size: 100% 100%;
    background-repeat: no-repeat;
    background-position: center;
    position: relative;
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
    margin-top: -16px;
    margin-bottom: -210px;
}}
.app-footer {{
    padding: 20px;
    background-color: transparent;
    text-align: center;
    width: auto;
    position: relative;
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
}}
.app-footer .footer-label {{
    font-family: 'Space Grotesk', sans-serif;
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
<div class="footer-skyline"></div>
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

# ── Footer nav columns (sits at the very bottom of the page) ───────────────────
FOOTER_NAV_EXPLORE = [
    ("Get Started", "pages/0_Get_Started.py"),
    ("Area Overview", "pages/1_area_overview.py"),
    ("Property Types", "pages/2_property_types.py"),
    ("Listing Candidates", "pages/3_listing_candidates.py"),
    ("Live Listings", "pages/5_Live_Listings.py"),
]
FOOTER_NAV_COMPANY = [
    ("About Us", "pages/6_About_Us.py"),
    ("Documentation", "pages/4_Documentation.py"),
]

st.markdown(
    """
    <style>
    .st-key-footer_nav {
        background-color: #2E2E2E;
        padding: 40px 20px 56px;
        width: auto;
        max-width: 100vw !important;
        position: relative;
        margin-left: calc(-50vw + 50%);
        margin-right: calc(-50vw + 50%);
        margin-top: 0;
        overflow: visible !important;
        box-sizing: border-box;
    }
    .st-key-footer_nav [data-testid="stHorizontalBlock"] {
        max-width: 900px;
        margin: 0 auto !important;
    }
    .st-key-footer_nav .footer-nav-heading {
        font-family: 'Space Grotesk', sans-serif;
        color: #F2F2F2;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 14px;
    }
    .st-key-footer_nav .footer-nav-tagline {
        color: #B5B5B5;
        font-size: 0.85rem;
        max-width: 260px;
        line-height: 1.5;
    }
    .st-key-footer_nav [data-testid="stPageLink"] a {
        color: #B5B5B5 !important;
    }
    .st-key-footer_nav [data-testid="stPageLink"] a p {
        color: #B5B5B5 !important;
        font-size: 0.88rem !important;
        font-weight: 400 !important;
    }
    .st-key-footer_nav [data-testid="stPageLink"] a:hover,
    .st-key-footer_nav [data-testid="stPageLink"] a:hover p {
        color: #F26359 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="footer_nav"):
    fn_col1, fn_col2, fn_col3 = st.columns([1.3, 1, 1])
    with fn_col1:
        st.markdown('<div class="footer-nav-heading">BnB Invest</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="footer-nav-tagline">Data-driven Airbnb investment analysis '
            'across London, Bristol, and Greater Manchester.</div>',
            unsafe_allow_html=True,
        )
    with fn_col2:
        st.markdown('<div class="footer-nav-heading">Explore</div>', unsafe_allow_html=True)
        for label, target in FOOTER_NAV_EXPLORE:
            st.page_link(target, label=label)
    with fn_col3:
        st.markdown('<div class="footer-nav-heading">Company</div>', unsafe_allow_html=True)
        for label, target in FOOTER_NAV_COMPANY:
            st.page_link(target, label=label)
