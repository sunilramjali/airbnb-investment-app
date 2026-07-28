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
    justify-content: center !important;
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
    font-size: 1.15rem !important;
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
    justify-content: center;
    height: 100%;
    min-height: 1.4rem;
    color: #F26359;
    font-size: 1.15rem;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
}
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

    # Logo slot, one slot per crumb, a flexible spacer, then the Documentation link.
    ratios = [0.7] + [1.4 for _ in trail]
    ratios.append(max(1.0, 8 - sum(ratios)))  # spacer
    ratios.append(1.4)                         # doc link

    cols = st.columns(ratios, vertical_alignment="center")

    with cols[0]:
        _render_logo_image()

    for i, (key, label, target) in enumerate(trail):
        with cols[i + 1]:
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
    """Full navigation bar: logo + every main-flow page + Documentation link."""
    _logo_css()
    _inject_css()

    ratios = [0.7] + [1.4 for _ in FLOW]
    ratios.append(max(1.0, 8 - sum(ratios)))  # spacer
    ratios.append(1.4)                         # doc link
    cols = st.columns(ratios, vertical_alignment="center")

    with cols[0]:
        _render_logo_image()

    for i, (_, label, target) in enumerate(FLOW):
        with cols[i + 1]:
            st.page_link(target, label=label)

    with cols[-1]:
        st.page_link(_DOC_PAGE, label="Documentation")
