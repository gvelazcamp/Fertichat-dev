import os

def get_secret(key: str, default=None):
    # 1) Variables de entorno (Render / prod)
    val = os.getenv(key)
    if val:
        return val

    # 2) Streamlit secrets (solo si existen)
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default
