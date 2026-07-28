# Resolves files in assets/ to inline data: URIs, so they can be dropped into
# raw HTML (st.markdown(..., unsafe_allow_html=True)) where a plain file path
# wouldn't be servable by the browser.
import base64
import mimetypes
import os

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
_EXTENSIONS = (".png", ".webp", ".jpg", ".jpeg", ".svg")


def get_asset_uri(stem: str) -> str | None:
    """Returns a base64 data: URI for assets/<stem>.<ext>, or None if not found."""
    for ext in _EXTENSIONS:
        path = os.path.join(_ASSETS_DIR, stem + ext)
        if os.path.exists(path):
            mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
    return None
