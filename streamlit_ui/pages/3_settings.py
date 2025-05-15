import streamlit as st
st.set_page_config(page_title="Settings", layout="centered")

import bcrypt
from api.supabase import supabase
from utils.auth import cookies

if not cookies.ready():
    st.info("Cookies are not ready yet. Please wait a moment and try again.")
    st.stop()

if cookies.ready():
    from utils.session_guard import require_login
    require_login()

    st.title("🔒 Change Password")

    # ✅ 로그인 확인
    if "user" not in st.session_state or st.session_state.user is None:
        st.warning("You must be logged in to access settings.")
        st.stop()

    # ✅ 현재 로그인된 유저 정보
    user_email = st.session_state.user["email"]
    st.markdown(f"Logged in as: `{user_email}`")

    st.markdown("---")
    st.subheader("Update your password")

    # ✅ 새 비밀번호 입력
    new_pw = st.text_input("🔑 New password", type="password")
    new_pw2 = st.text_input("🔁 Confirm new password", type="password")

    # ✅ 검증 및 업데이트
    if st.button("✅ Update Password"):
        if not new_pw or not new_pw2:
            st.error("Please fill in both fields.")
        elif new_pw != new_pw2:
            st.error("Passwords do not match.")
        elif len(new_pw) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            hashed_pw = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
            result = supabase.table("users").update(
                {"password_hash": hashed_pw}
            ).eq("id", st.session_state.user["id"]).execute()

            if result.data:
                st.success("🎉 Password successfully updated!")
            else:
                st.error("Something went wrong. Please try again.")
