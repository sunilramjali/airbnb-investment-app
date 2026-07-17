"""Shared Snowflake connection for running the app outside Snowflake.

Builds a Snowpark Session from the service-user key-pair credentials in
st.secrets["connections"]["snowflake"]. Supports the private key supplied
either inline as PEM text (private_key) or as a file path (private_key_file),
so the same code works on Streamlit Community Cloud and self-hosted setups.
"""
import streamlit as st
from snowflake.snowpark import Session
from cryptography.hazmat.primitives import serialization


@st.cache_resource
def get_session() -> Session:
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
