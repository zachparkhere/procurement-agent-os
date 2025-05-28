import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import streamlit as st
st.set_page_config(layout="wide")

from streamlit_ui.api.supabase import supabase

# 로그아웃 처리
if st.session_state.get("user"):
    st.success(f"✅ Logged in as {st.session_state.user.email}")
    if st.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.access_token = None
        st.rerun()
else:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pw")
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = res.user
                st.session_state["access_token"] = res.session.access_token
                st.session_state["refresh_token"] = res.session.refresh_token
                st.session_state["user_id"] = res.user.id
                st.session_state["user_email"] = res.user.email
                st.success("✅ Login successful!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Login failed: {e}")
    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_pw")
        if st.button("Sign Up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                st.success("🎉 Sign up successful! Please check your email to verify your account.")
            except Exception as e:
                st.error(f"❌ Sign up failed: {e}")
