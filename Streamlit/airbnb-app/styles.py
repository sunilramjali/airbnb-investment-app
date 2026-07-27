# Shared page theme: one CSS source of truth instead of a copy-pasted block per page.
import streamlit as st

# Brand palette used throughout the custom CSS below.
CORAL = "#f26359"
CORAL_LIGHT = "#f8d9d3"
CREAM = "#FFFAF0"
CREAM_BORDER = "#F4EFEB"
ALERT_BG = "#FCEDEA"
TEXT_DARK = "#7A2E2A"

BASE_CSS = f"""
<style>
/* Main app */
.stApp {{
    background-color: white !important;
}}

[data-testid="stFullScreenFrame"] {{
    background-color: white !important;
}}

[data-testid="stBottomBlockContainer"] {{
    background-color: white !important;
}}

[data-testid="stExpander"] summary {{
    background-color: {CORAL_LIGHT} !important;
}}

[data-testid="stExpander"] summary:hover {{
    background-color: {CORAL} !important;
}}

[data-testid="stExpander"] details[open] summary {{
    background-color: {CORAL_LIGHT} !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    display: none !important;
}}

[data-testid="collapsedControl"] {{
    display: none !important;
}}

section[data-testid="stSidebar"] {{
    background-color: white !important;
    display: none !important;
}}

[data-testid="stSelectbox"] input {{
    background-color: {CORAL_LIGHT} !important;
    color: {CORAL} !important;
    -webkit-text-fill-color: #000000 !important;
}}

[data-testid="stSelectbox"] button {{
    background-color: {CORAL_LIGHT} !important;
}}

/* Big headings */
h1, h2 {{
    color: {CORAL} !important;
}}

/* Smaller headings */
h3, h4, h5, h6 {{
    color: #000000 !important;
}}

/* Normal markdown text */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {{
    color: #000000 !important;
}}

/* Captions */
[data-testid="stCaptionContainer"] {{
    color: #000000 !important;
}}

div[data-testid="stAlert"] {{
    background-color: {ALERT_BG} !important;
    color: {TEXT_DARK} !important;
    border: 1px solid {CORAL} !important;
    border-left: 6px solid {CORAL} !important;
    border-radius: 12px !important;
}}

div[data-testid="stAlert"] p,
div[data-testid="stAlert"] div {{
    color: {TEXT_DARK} !important;
}}

/* Metrics */
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {{
    color: #000000 !important;
}}

/* Buttons */
div.stButton > button[kind="secondary"] {{
    background-color: {CREAM} !important;
    width: 100% !important;
    height: 90px !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    color: {TEXT_DARK} !important;
    border: 2px solid {CREAM_BORDER} !important;
    border-radius: 12px !important;
}}

div.stButton > button[kind="secondary"]:hover {{
    background-color: {CORAL_LIGHT} !important;
    width: 100% !important;
    height: 90px !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    color: {TEXT_DARK} !important;
    border: 2px solid {CREAM_BORDER} !important;
}}

div.stButton > button[kind="primary"] {{
    background-color: {CORAL_LIGHT} !important;
    width: 100% !important;
    height: 90px !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    color: {TEXT_DARK} !important;
    border: 2px solid {CORAL} !important;
    border-radius: 12px !important;
}}

div.stButton > button p {{
    white-space: pre-line !important;
    text-align: center !important;
    line-height: 1.3 !important;
}}

[data-testid="stLinkButton"] a {{
    background-color: {CREAM} !important;
    width: 100% !important;
    height: 90px !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    color: {TEXT_DARK} !important;
    border: 2px solid {CREAM_BORDER} !important;
    border-radius: 12px !important;
}}

[data-testid="stLinkButton"] a:hover {{
    background-color: {CORAL_LIGHT} !important;
    width: 100% !important;
    height: 90px !important;
    font-size: 20px !important;
    font-weight: 600 !important;
    color: {TEXT_DARK} !important;
    border: 2px solid {CREAM_BORDER} !important;
}}

 /* Multiselect outer box */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    background-color: {CORAL_LIGHT} !important;
}}

/* Text typed inside the multiselect */
[data-testid="stMultiSelect"] input {{
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}}

/* Placeholder text */
[data-testid="stMultiSelect"] input::placeholder {{
    color: {TEXT_DARK} !important;
    opacity: 1 !important;
}}

/* Selected option boxes / tags */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
    background-color: {CORAL} !important;
    color: #ffffff !important;
    border-radius: 8px !important;
}}

/* Text inside selected tags */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {{
    color: #ffffff !important;
}}

/* Remove icon inside selected tags */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {{
    fill: #ffffff !important;
    color: #ffffff !important;
}}

/* Dropdown menu background */
div[data-baseweb="popover"] ul {{
    background-color: #ffffff !important;
}}

/* Dropdown options */
div[data-baseweb="popover"] li {{
    background-color: #ffffff !important;
    color: #000000 !important;
}}

/* Dropdown option hover */
div[data-baseweb="popover"] li:hover {{
    background-color: {CORAL_LIGHT} !important;
    color: #000000 !important;
}}
</style>
"""

# Pins the AI-summary panel to the bottom of the viewport (used by pages with an
# `st.bottom` narrative section: landing, area overview, property types, listing candidates).
BOTTOM_PANEL_CSS = f"""
<style>
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{
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
}}

[data-testid="stBottomBlockContainer"] > div {{
    margin-left: 0px !important;
    margin-right: auto !important;
    width: 100% !important;
    max-width: 950px !important;
    background-color: white !important;
    border: 1px solid {CORAL} !important;
    border-radius: 12px !important;
    padding: 16px !important;
    pointer-events: auto !important;
    max-height: 42vh !important;
    overflow-y: auto !important;
}}
[data-testid="stBottomBlockContainer"] [data-testid="stVerticalBlock"] {{
    margin-left: 0px !important;
    margin-right: auto !important;
    width: 100% !important;
}}

[data-testid="stBottomBlockContainer"] [data-testid="stElementContainer"] {{
    margin-left: 0px !important;
    margin-right: auto !important;
}}
</style>
"""

# Print stylesheet for the comparison pages (area & property-type comparisons):
# forces a white A4-landscape printout with one section per page.
PRINT_CSS = """
<style>
@media print {

@page {
    size: A4 landscape;
    margin: 12mm;
}

/* Force the whole page to print in white */
html,
body,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
.block-container {
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #000000 !important;
}

/* Force all text to black */
h1,
h2,
h3,
h4,
h5,
h6,
p,
span,
div,
label,
li,
[data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"],
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
}

/* Hide Streamlit chrome */
header,
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stSidebar"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* Hide Streamlit buttons */
div.stButton,
[data-testid="stButton"] {
    display: none !important;
}

/* Hide the custom print-button iframe */
iframe {
    display: none !important;
}

/* Remove unnecessary app padding */
.block-container,
[data-testid="stMainBlockContainer"] {
    max-width: 100% !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Bordered containers: white background, keep each section together. */
[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border-color: #b0b0b0 !important;
    box-shadow: none !important;
    display: block !important;
}

/* Keep the ST-vs-LT charts side-by-side (both on page 1); just stop the
   columns from overflowing the page width. */
[data-testid="column"] {
    min-width: 0 !important;
}

/* Force each print section onto its own page:
   Page 1 = ST vs LT, Page 2 = Seasonal trend, Page 3 = AI summary. */
.st-key-print_seasonal,
.st-key-print_ai {
    break-before: page !important;
    page-break-before: always !important;
}

.st-key-print_strategy,
.st-key-print_seasonal,
.st-key-print_ai {
    break-inside: avoid !important;
    page-break-inside: avoid !important;
}

/* Marker-div fallback page break (works regardless of container-key support). */
.pagebreak {
    break-before: page !important;
    page-break-before: always !important;
    height: 0 !important;
    display: block !important;
}

/* Make Altair chart wrappers printable */
[data-testid="stVegaLiteChart"] {
    background: #ffffff !important;
    background-color: #ffffff !important;
    width: 100% !important;
    max-width: 100% !important;
    overflow: visible !important;
    break-inside: avoid !important;
    page-break-inside: avoid !important;
}

[data-testid="stVegaLiteChart"] > div,
[data-testid="stVegaLiteChart"] canvas,
[data-testid="stVegaLiteChart"] svg {
    background: #ffffff !important;
    background-color: #ffffff !important;
    max-width: 100% !important;
}

/* Remove dark fills from generic Streamlit blocks */
[data-testid="stVerticalBlock"],
[data-testid="stElementContainer"] {
    background: transparent !important;
}

/* Hide the logo, buttons and the auto-print iframe when printing.
   Print mode already re-renders only the charts + their titles,
   so no fragile :has() reveal rules are needed here. */
[data-testid="stImage"],
div.stButton,
[data-testid="stButton"],
iframe {
    display: none !important;
}
}
</style>
"""


def apply_theme(bottom_panel: bool = False, print_css: bool = False) -> None:
    """Injects the shared page CSS. Call once near the top of each page.

    bottom_panel: include the pinned-bottom AI-summary panel override
                  (pages that use `st.bottom` for a narrative section).
    print_css:    include the print stylesheet (comparison pages with a
                  "print to PDF" button).
    """
    css = BASE_CSS
    if bottom_panel:
        css += BOTTOM_PANEL_CSS
    if print_css:
        css += PRINT_CSS
    st.markdown(css, unsafe_allow_html=True)
