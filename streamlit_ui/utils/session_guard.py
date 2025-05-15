import streamlit as st
from utils.auth import restore_user_session

def require_login():
    if "user" not in st.session_state or st.session_state.get("user") is None:
        restore_user_session()

    if st.session_state.get("user") is None:
        st.warning("🔒 Please log in to access this page.")
        st.stop()
