# Live Gemini API helper reading credentials from st.secrets (for use outside Snowflake).
# Co-authored with CoCo
"""Live Gemini API helper.

Reads the API key from st.secrets["gemini"]["api_key"] and exposes a cached
model plus a simple generate() call. Intended for the app running outside
Snowflake (e.g. Streamlit Community Cloud), where live outbound calls are
allowed. The key is only ever read from secrets, never hard-coded.
"""
import streamlit as st
import google.generativeai as genai

DEFAULT_MODEL = "gemini 3.1 Flash lite"


@st.cache_resource
def _model():
    cfg = st.secrets["gemini"]  # KeyError -> caller surfaces a clear message
    genai.configure(api_key=cfg["api_key"])
    return genai.GenerativeModel(cfg.get("model", DEFAULT_MODEL))


def generate(prompt: str) -> str:
    return _model().generate_content(prompt).text
