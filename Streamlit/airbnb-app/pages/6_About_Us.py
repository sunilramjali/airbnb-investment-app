# About Us page: mission, team, and data sources.
import streamlit as st
from styles import apply_theme, CORAL
from nav import render_nav_links

st.set_page_config(page_title="About Us - BnB Invest", page_icon="🏡", layout='wide')

apply_theme()

render_nav_links()

st.markdown(
    f"""
    <style>
    .about-link {{ transition: opacity 0.15s ease; }}
    .about-link:hover {{ opacity: 0.72; text-decoration: underline !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title('About Us')

st.write(
    "BnB Invest helps short-term rental investors cut through guesswork. We combine real "
    "Airbnb listing performance, HM Land Registry sale prices, ONS rental statistics, and "
    "Overture Maps points of interest into a single, persona-driven scoring system — so you "
    "can go from \"where should I invest?\" to a shortlist of real listings, backed by data "
    "and AI-generated analysis at every step."
)

st.divider()
st.subheader('Our Mission')
st.write(
    "Property investment decisions are often made on gut feeling or word of mouth. We built "
    "BnB Invest to close that gap for the UK short-term rental market — giving investors the "
    "same kind of data-driven insight that institutional buyers already have access to."
)

st.divider()
st.subheader('Data Sources')
st.write(
    "Every score and recommendation is grounded in real data: Inside Airbnb listing "
    "performance, HM Land Registry sale prices, ONS private rental statistics, and Overture "
    "Maps points of interest — covering London, Bristol, and Greater Manchester."
)

st.divider()
st.subheader('Made By')

LINKEDIN_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M22.23 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.46c.98 0 1.77-.77 1.77-1.72V1.72C24 .77 23.21 0 22.23 0zM7.06 20.45H3.56V9h3.5v11.45zM5.31 7.43c-1.12 0-2.03-.92-2.03-2.05 0-1.13.91-2.05 2.03-2.05 1.12 0 2.03.92 2.03 2.05 0 1.13-.91 2.05-2.03 2.05zM20.45 20.45h-3.5v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.44-2.13 2.94v5.67h-3.5V9h3.36v1.56h.05c.47-.89 1.62-1.85 3.34-1.85 3.57 0 4.23 2.35 4.23 5.41v6.33z"/></svg>'
GITHUB_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.57.11.78-.25.78-.55 0-.27-.01-1.16-.02-2.11-3.2.7-3.88-1.36-3.88-1.36-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.26-1.28-5.26-5.7 0-1.26.45-2.29 1.18-3.1-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.58.24 2.75.12 3.04.74.81 1.18 1.84 1.18 3.1 0 4.43-2.71 5.4-5.28 5.69.42.36.78 1.08.78 2.18 0 1.57-.01 2.84-.01 3.23 0 .31.21.67.79.55A10.51 10.51 0 0 0 23.5 12c0-6.27-5.23-11.5-11.5-11.5z"/></svg>'
EMAIL_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/></svg>'

TEAM = [
    ("Adam Choy",         "https://www.linkedin.com/in/adam-choy-b95715190/",              "agc.choy@gmail.com"),
    ("Sunil Ramjali",     "https://www.linkedin.com/in/sunilramjali/",                     "ramjs016.310@gmail.com"),
    ("Kanmani Vijay",     "https://www.linkedin.com/in/kanmani-vijay-8451a322b/",          "kanmanivj02@gmail.com"),
    ("Ayenorya Otsumah",  "https://www.linkedin.com/in/ayenorya-otsumah-140930330/",       "ayenor3@yahoo.com"),
]
GITHUB_URL = "https://github.com/sunilramjali/airbnb-investment-app"

team_cols = st.columns(len(TEAM))
for col, (name, url, email) in zip(team_cols, TEAM):
    with col:
        st.markdown(
            f"""
            <div style='text-align:center;'>
                <div style='font-weight:700; margin-bottom:6px;'>{name}</div>
                <a class="about-link" href="{url}" target="_blank" style="
                    color:{CORAL}; text-decoration:none;
                    display:inline-flex; align-items:center; gap:6px;
                ">{LINKEDIN_ICON} LinkedIn</a><br/>
                <a class="about-link" href="mailto:{email}" style="
                    color:{CORAL}; text-decoration:none;
                    display:inline-flex; align-items:center; gap:6px; margin-top:4px;
                ">{EMAIL_ICON} {email}</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown(
    f"""
    <div style='text-align:center; margin-top:16px;'>
        <a class="about-link" href="{GITHUB_URL}" target="_blank" style="
            color:{CORAL}; text-decoration:none; font-weight:700;
            display:inline-flex; align-items:center; gap:6px;
        ">{GITHUB_ICON} View on GitHub</a>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("For research purposes only — not financial advice.")
