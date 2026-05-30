import streamlit as st
st.set_page_config(page_title="Deprecated", page_icon="❌")
st.error("❌ **DEPRECATED**")
st.warning(
    "Please use `app_dashboard.py` instead. "
    "Running this file blocks the main thread."
)
st.stop()
