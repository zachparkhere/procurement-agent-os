import streamlit as st
from utils.auth import restore_user_session

def require_login():
    user = st.session_state.get("user")
    if user is None:
        restore_user_session()
        user = st.session_state.get("user")
    if user is None:
        st.warning("🔒 Please log in to access this page.")
        st.stop()
