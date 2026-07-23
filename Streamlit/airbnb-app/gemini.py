# Live Gemini API helper reading credentials from st.secrets (for use outside Snowflake).
# Co-authored with CoCo
"""Live Gemini API helper — the single Gemini gateway for the app.

Owns the SDK, model name, key resolution and retry logic. By default the API
key is read from st.secrets["gemini"]["api_key"]; callers may pass an explicit
api_key to override. Intended for the app running outside Snowflake
(e.g. Streamlit Community Cloud), where live outbound calls are allowed.
The key is only ever read from secrets or passed in, never hard-coded.
"""
import time

import streamlit as st
import google.generativeai as genai

DEFAULT_MODEL = "gemini-3.1-flash-lite"


def _resolve_key(api_key):
    if api_key:
        return api_key
    # Prefer a Snowflake-managed secret (top-level key in container runtime),
    # then fall back to the nested [gemini] table from a local secrets.toml.
    try:
        return st.secrets["gemini_api_key"]
    except Exception:
        return st.secrets["gemini"]["api_key"]  # KeyError -> caller surfaces it


def _resolve_model_name():
    # Top-level managed secret first, then nested table, then the default.
    try:
        return st.secrets["gemini_model"]
    except Exception:
        return st.secrets.get("gemini", {}).get("model", DEFAULT_MODEL)


def generate(prompt: str, api_key: str = None, max_retries: int = 3) -> str:
    """Generate text from Gemini, retrying on rate limits.

    Raises on the final failed attempt; callers decide how to handle it.
    """
    genai.configure(api_key=_resolve_key(api_key))
    model = genai.GenerativeModel(_resolve_model_name())

    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt).text
        except Exception as e:
            if attempt >= max_retries - 1:
                raise
            time.sleep(15 * (attempt + 1) if "429" in str(e) else 5)
