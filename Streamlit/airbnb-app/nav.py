# Shared top-navigation breadcrumb helpers for the Airbnb investment app.
"""Reusable breadcrumb navigation.

Renders a consistent, professional top navigation bar across pages:
- A progressive breadcrumb trail (earlier flow steps as links, the current
  step emphasised) followed by a right-aligned Documentation page-link.
- The chevron separators are flex-centred so they sit on the same line as the
  link text (fixes the misaligned-chevron issue caused by st.page_link's
  taller component box).
"""
import base64
import mimetypes
import os

import streamlit as st

# Absolute path to the bundled logo, resolved from this file's location so it
# works from both the app root and pages/ scripts, in Snowsight and deployed.
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "bnb_logo_original_cropped.png")
_LOGO_SIZE = 50  # px, square

# Main linear flow (the logo itself links back to landing, so it isn't repeated
# here): (key, label, page target)
FLOW = [
    ("get_started", "Get Started", "pages/0_Get_Started.py"),
    ("area_overview", "Area Overview", "pages/1_area_overview.py"),
    ("property_types", "Property Types", "pages/2_property_types.py"),
    ("listing_candidates", "Listing Candidates", "pages/3_listing_candidates.py"),
    ("live_listings", "Live Listings", "pages/5_Live_Listings.py"),
]

_DOC_PAGE = "pages/4_Documentation.py"
_ABOUT_PAGE = "pages/6_About_Us.py"

_CSS = f"""
<style>
/* Full-bleed navbar background */
.st-key-app_navbar {{
    background-color: #F5F5F5;
    padding: 8px 20px;
    margin-top: -48px;
    width: auto;
    max-width: 100vw !important;
    position: relative;
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
    overflow: visible !important;
    box-sizing: border-box;
}}

.st-key-app_navbar [data-testid="stHorizontalBlock"] {{
    align-items: center !important;
    min-height: 66px !important;
}}

/* Breadcrumb page-links rendered as plain text */
[data-testid="stPageLink"] {{
    margin: 0 !important;
    padding: 0 !important;
}}

[data-testid="stPageLink"] a {{
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    margin: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
    color: #333333 !important;
    text-decoration: none !important;
    line-height: 1.2 !important;
    white-space: nowrap !important;
}}

[data-testid="stPageLink"] a p {{
    font-size: 1.15rem !important;
    font-weight: 500 !important;
    margin: 0 !important;
}}

[data-testid="stPageLink"] a:hover,
[data-testid="stPageLink"] a:hover p {{
    color: #F26359 !important;
    text-decoration: none !important;
}}

/* Current page crumb */
.breadcrumb-current {{
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 1.4rem;
    color: #F26359;
    font-size: 1.15rem;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
    text-decoration: underline;
    text-underline-offset: 4px;
}}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _logo_css() -> None:
    st.markdown(
        """
        <style>
        /* Pull page content flush to the top (removes space above logo) */
        .block-container,
        [data-testid="stMainBlockContainer"] {
            padding-top: 0rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _logo_data_uri() -> str | None:
    if not os.path.exists(_LOGO_PATH):
        return None
    mime = mimetypes.guess_type(_LOGO_PATH)[0] or "application/octet-stream"
    with open(_LOGO_PATH, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _render_logo_image() -> None:
    """Renders the logo as a real (JS-routed) page-link to landing.py, so
    clicking the logo itself navigates home."""
    uri = _logo_data_uri()
    if uri is None:
        return

    with st.container(key="nav_logo_link"):
        st.markdown(
            f"""
            <style>
            .st-key-nav_logo_link [data-testid="stPageLink"] a {{
                padding: 12px !important;
                min-height: {_LOGO_SIZE}px !important;
                height: {_LOGO_SIZE}px !important;
                width: {_LOGO_SIZE}px !important;
                background-image: url('{uri}') !important;
                background-size: contain !important;
                background-repeat: no-repeat !important;
                background-position: center !important;
            }}
            .st-key-nav_logo_link [data-testid="stPageLink"] a p {{
                opacity: 0 !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("landing.py", label="Home")


def render_logo() -> None:
    """Render the BnB Invest logo top-left, flush to the top of the page."""
    _logo_css()
    _render_logo_image()


def render_breadcrumb(current: str) -> None:
    """Progressive breadcrumb trail up to ``current`` + a Documentation link.

    ``current`` is one of the FLOW keys. Earlier steps render as links, the
    current step is emphasised; later steps are omitted (progressive trail).
    """
    _logo_css()
    _inject_css()

    keys = [k for k, _, _ in FLOW]
    current_index = keys.index(current)
    trail = FLOW[: current_index + 1]

    # Logo, a leading spacer, one slot per crumb, a trailing spacer, then
    # Change Persona + About Us + Documentation links. Equal leading/trailing
    # spacers centre the crumb trail between the logo and the persistent links.
    persistent_ratio = 2.0 + 1.6 + 1.8
    trail_ratio = 2.2 * len(trail)
    spacer = max(1.0, (18 - 0.7 - trail_ratio - persistent_ratio) / 2)
    ratios = [0.7, spacer] + [2.2 for _ in trail] + [spacer, 2.0, 1.6, 1.8]

    with st.container(key="app_navbar"):
        cols = st.columns(ratios, vertical_alignment="center")

        with cols[0]:
            _render_logo_image()

        for i, (key, label, target) in enumerate(trail):
            with cols[i + 2]:
                if key == current:
                    st.markdown(
                        f"<span class='breadcrumb-current'>{label}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.page_link(target, label=label)

        # Right-aligned Change Persona + About Us + Documentation links (last three columns).
        with cols[-3]:
            st.page_link("pages/0_Get_Started.py", label="Change Persona")
        with cols[-2]:
            st.page_link(_ABOUT_PAGE, label="About Us")
        with cols[-1]:
            st.page_link(_DOC_PAGE, label="Documentation")


def render_nav_links() -> None:
    """Full navigation bar: logo + every main-flow page + About Us + Documentation link."""
    _logo_css()
    _inject_css()

    persistent_ratio = 1.6 + 1.8
    flow_ratio = 2.2 * len(FLOW)
    spacer = max(1.0, (16 - 0.7 - flow_ratio - persistent_ratio) / 2)
    ratios = [0.7, spacer] + [2.2 for _ in FLOW] + [spacer, 1.6, 1.8]

    with st.container(key="app_navbar"):
        cols = st.columns(ratios, vertical_alignment="center")

        with cols[0]:
            _render_logo_image()

        for i, (_, label, target) in enumerate(FLOW):
            with cols[i + 2]:
                st.page_link(target, label=label)

        with cols[-2]:
            st.page_link(_ABOUT_PAGE, label="About Us")
        with cols[-1]:
            st.page_link(_DOC_PAGE, label="Documentation")
