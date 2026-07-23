# Shared Snowflake session helper that works inside Streamlit-in-Snowflake and outside it.
"""Shared Snowflake connection.

When running inside Snowflake (Streamlit in Snowflake / SPCS), the active
Snowpark Session is used directly — no credentials required.

When running outside Snowflake (e.g. Streamlit Community Cloud or self-hosted),
a Session is built from the service-user key-pair credentials in
st.secrets["connections"]["snowflake"]. The private key may be supplied either
inline as PEM text (private_key) or as a file path (private_key_file).
"""
import streamlit as st
from snowflake.snowpark import Session
from cryptography.hazmat.primitives import serialization


@st.cache_resource
def get_session() -> Session:
    # Prefer the active session when running inside Snowflake.
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()
    except Exception:
        pass

    # Fall back to key-pair credentials from secrets when running outside Snowflake.
    cfg = dict(st.secrets["connections"]["snowflake"])

    pem = cfg.pop("private_key", None)
    key_file = cfg.pop("private_key_file", None)

    if pem is None and key_file is not None:
        with open(key_file, "rb") as f:
            pem = f.read().decode()

    if pem is None:
        raise RuntimeError(
            "No private key found. Set 'private_key' (inline PEM) or "
            "'private_key_file' under [connections.snowflake] in secrets."
        )

    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    cfg["private_key"] = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return Session.builder.configs(cfg).create()
