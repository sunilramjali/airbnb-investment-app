# Shared top-navigation breadcrumb helpers for the Airbnb investment app.
"""Reusable breadcrumb navigation.

Renders a consistent, professional top navigation bar across pages:
- A progressive breadcrumb trail (earlier flow steps as links, the current
  step emphasised) followed by a right-aligned Documentation page-link.
- The chevron separators are flex-centred so they sit on the same line as the
  link text (fixes the misaligned-chevron issue caused by st.page_link's
  taller component box).
"""
import os

import streamlit as st

# Absolute path to the bundled logo, resolved from this file's location so it
# works from both the app root and pages/ scripts, in Snowsight and deployed.
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "bnb_logo_original.webp")

# Main linear flow: (key, label, page target)
FLOW = [
    ("landing", "Landing", "landing.py"),
    ("area_overview", "Area Overview", "pages/1_area_overview.py"),
    ("property_types", "Property Types", "pages/2_property_types.py"),
    ("listing_candidates", "Listing Candidates", "pages/3_listing_candidates.py"),
]

_DOC_PAGE = "pages/4_Documentation.py"

_CSS = """
<style>
/* Breadcrumb page-links rendered as plain text */
[data-testid="stPageLink"] {
    margin: 0 !important;
    padding: 0 !important;
}

[data-testid="stPageLink"] a {
    display: flex !important;
    align-items: center !important;
    padding: 0 !important;
    margin: 0 !important;
    min-height: 0 !important;
    background: transparent !important;
    color: #6B6B6B !important;
    text-decoration: none !important;
    line-height: 1.2 !important;
    white-space: nowrap !important;
}

[data-testid="stPageLink"] a p {
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    margin: 0 !important;
}

[data-testid="stPageLink"] a:hover,
[data-testid="stPageLink"] a:hover p {
    color: #F26359 !important;
    text-decoration: none !important;
}

/* Current page crumb */
.breadcrumb-current {
    display: flex;
    align-items: center;
    height: 100%;
    min-height: 1.4rem;
    color: #F26359;
    font-size: 0.95rem;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def render_logo() -> None:
    """Render the BnB Invest logo top-left, flush to the top of the page."""
    if os.path.exists(_LOGO_PATH):
        st.markdown(
            """
            <style>
            /* Pull page content flush to the top (removes space above logo) */
            .block-container,
            [data-testid="stMainBlockContainer"] {
                padding-top: 1rem !important;
            }
            /* Remove default margins around the logo image */
            [data-testid="stImage"],
            [data-testid="stImageContainer"] {
                margin: 0 !important;
            }
            [data-testid="stImage"] img,
            [data-testid="stImageContainer"] img {
                margin: 0 !important;
                display: block;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.image(_LOGO_PATH, width=150)


def render_doc_link() -> None:
    """Right-aligned Documentation page-link only (used on the landing page)."""
    render_logo()
    _inject_css()
    _, doc_col = st.columns([8, 1], vertical_alignment="center")
    with doc_col:
        st.page_link(_DOC_PAGE, label="Documentation")


def render_breadcrumb(current: str) -> None:
    """Progressive breadcrumb trail up to ``current`` + a Documentation link.

    ``current`` is one of the FLOW keys. Earlier steps render as links, the
    current step is emphasised; later steps are omitted (progressive trail).
    """
    render_logo()
    _inject_css()

    keys = [k for k, _, _ in FLOW]
    current_index = keys.index(current)
    trail = FLOW[: current_index + 1]

    # One slot per crumb, a flexible spacer, then the Documentation link.
    ratios = [1.4 for _ in trail]
    ratios.append(max(1.0, 8 - sum(ratios)))  # spacer
    ratios.append(1.4)                         # doc link

    cols = st.columns(ratios, vertical_alignment="center")

    for i, (key, label, target) in enumerate(trail):
        with cols[i]:
            if key == current:
                st.markdown(
                    f"<span class='breadcrumb-current'>{label}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(target, label=label)

    # Right-aligned Documentation link (last column).
    with cols[-1]:
        st.page_link(_DOC_PAGE, label="Documentation")


def render_nav_links() -> None:
    """All main-flow steps as page-links (used on the Documentation page)."""
    render_logo()
    _inject_css()

    ratios = [1.4 for _ in FLOW]
    ratios.append(max(1.0, 8 - sum(ratios)))  # trailing spacer
    cols = st.columns(ratios, vertical_alignment="center")

    for i, (_, label, target) in enumerate(FLOW):
        with cols[i]:
            st.page_link(target, label=label)
