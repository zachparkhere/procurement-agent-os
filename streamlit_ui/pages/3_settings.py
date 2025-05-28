import streamlit as st

import sys
import os
import logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import bcrypt
from po_agent_os.supabase_client_anon import supabase
import requests
from streamlit_ui.utils.logging_config import logging

# 로깅 설정
logger = logging.getLogger(__name__)

# 🔐 Login check
if "user" not in st.session_state:
    st.warning("Please log in to continue.")
    st.stop()

user_email = st.session_state.user.email
user_row = supabase.table("users").select("id").eq("email", user_email).single().execute().data
user_id = user_row["id"]

st.sidebar.markdown(f"**Logged in as:** {user_email}")

# ✅ DB에서 현재 사용자 정보 가져오기
try:
    user_res = supabase.table("users") \
        .select("eta_followup_interval_days, email_provider, email_address, timezone") \
        .eq("id", user_id) \
        .limit(1) \
        .execute()
    logger.info(f"Retrieved user settings for user_id: {user_id}")
except Exception as e:
    logger.error(f"Failed to retrieve user settings: {str(e)}")
    st.error("Failed to load user settings. Please try again.")
    st.stop()

user_data = user_res.data[0] if user_res.data else {}
current_interval = user_data.get("eta_followup_interval_days", 3)
current_provider = user_data.get("email_provider", None)
linked_email = user_data.get("email_address", None)
current_timezone = user_data.get("timezone", "UTC")

# 토큰을 session_state에서 직접 꺼내서 사용
access_token = st.session_state.get("access_token")
refresh_token = st.session_state.get("refresh_token")
if not access_token or not refresh_token:
    logger.warning(f"Missing tokens for user: {user_email}")
    st.error("Missing tokens. Please log in again.")
    st.stop()

# ✅ Set Supabase auth session
try:
    supabase.auth.set_session(
        access_token,
        refresh_token
    )
    logger.info(f"Successfully set Supabase auth session for user: {user_email}")
except Exception as e:
    logger.error(f"Authentication failed for user {user_email}: {str(e)}")
    st.error("Authentication failed. Please log in again.")
    st.exception(e)
    st.stop()

# -----------------------
# 🌍 Timezone Section
# -----------------------
st.markdown("---")
st.subheader("🌍 Timezone Settings")

def get_timezone_from_ip():
    try:
        response = requests.get('http://ip-api.com/json/')
        data = response.json()
        if data['status'] == 'success':
            return data['timezone']
    except Exception as e:
        logger.error(f"Failed to detect timezone: {e}")
    return 'UTC'

# 현재 시간대 표시
st.markdown(f"**Current Timezone**: {current_timezone}")

# 자동 감지 버튼
if st.button("🔄 Detect Timezone"):
    detected_timezone = get_timezone_from_ip()
    if detected_timezone != current_timezone:
        try:
            # DB 업데이트
            result = supabase.table("users").update(
                {"timezone": detected_timezone}
            ).eq("id", user_id).execute()
            
            if result.data:
                st.success(f"✅ Timezone updated to {detected_timezone}")
                st.rerun()
            else:
                st.error("Failed to update timezone")
        except Exception as e:
            logger.error(f"Error updating timezone: {e}")
            st.error("An error occurred while updating timezone")
    else:
        st.info("Timezone is already set correctly")

# 수동 선택 옵션
import pytz
all_timezones = pytz.all_timezones
selected_timezone = st.selectbox(
    "Or select timezone manually",
    all_timezones,
    index=all_timezones.index(current_timezone) if current_timezone in all_timezones else 0
)

if selected_timezone != current_timezone:
    if st.button("💾 Save Timezone"):
        try:
            result = supabase.table("users").update(
                {"timezone": selected_timezone}
            ).eq("id", user_id).execute()
            
            if result.data:
                st.success(f"✅ Timezone updated to {selected_timezone}")
                st.rerun()
            else:
                st.error("Failed to update timezone")
        except Exception as e:
            logger.error(f"Error updating timezone: {e}")
            st.error("An error occurred while updating timezone")

# -----------------------
# 🔑 Password Section
# -----------------------
st.markdown("---")
st.subheader("🔒 Update Your Password")

new_pw = st.text_input("New password", type="password")
new_pw2 = st.text_input("Confirm new password", type="password")

if st.button("✅ Update Password"):
    if not new_pw or not new_pw2:
        logger.warning("Password update attempted with empty fields")
        st.error("Please fill in both fields.")
    elif new_pw != new_pw2:
        logger.warning("Password update attempted with non-matching passwords")
        st.error("Passwords do not match.")
    elif len(new_pw) < 8:
        logger.warning("Password update attempted with password less than 8 characters")
        st.error("Password must be at least 8 characters.")
    else:
        try:
            hashed_pw = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
            result = supabase.table("users").update(
                {"password_hash": hashed_pw}
            ).eq("id", user_id).execute()
            if result.data:
                logger.info(f"Password successfully updated for user: {user_email}")
                st.success("🎉 Password successfully updated!")
            else:
                logger.error(f"Failed to update password for user: {user_email}")
                st.error("Something went wrong. Please try again.")
        except Exception as e:
            logger.error(f"Error updating password for user {user_email}: {str(e)}")
            st.error("An error occurred while updating password.")

# -----------------------
# ⏱️ ETA Follow-up Interval
# -----------------------
st.markdown("---")
st.subheader("⏱️ ETA Follow-up Interval (days)")
st.caption("How often to remind vendors who haven't shared an ETA.")

new_interval = st.number_input("Change interval:", min_value=1, max_value=30, value=current_interval, step=1)

if st.button("✅ Save Interval"):
    try:
        result = supabase.table("users").update(
            {"eta_followup_interval_days": new_interval}
        ).eq("id", user_id).execute()
        if result.data:
            logger.info(f"ETA follow-up interval updated to {new_interval} days for user: {user_email}")
            st.success(f"Interval updated to {new_interval} days.")
        else:
            logger.error(f"Failed to update ETA follow-up interval for user: {user_email}")
            st.error("Failed to update. Please try again.")
    except Exception as e:
        logger.error(f"Error updating ETA follow-up interval for user {user_email}: {str(e)}")
        st.error("An error occurred while updating interval.")

# -----------------------
# 📧 Email Integration Section
# -----------------------
st.markdown("---")
st.subheader("📨 Email Account Integration")

if current_provider and linked_email:
    st.success(f"✅ Connected to **{current_provider.upper()}**: `{linked_email}`")
else:
    st.warning("No email account linked.")

provider = st.selectbox("Choose email service to link", ["Gmail", "Outlook"])

if provider == "Gmail":
    if st.button("🔗 Link Google Account"):
        try:
            logger.info(f"Attempting to link Google account for user: {user_email}")
            r = requests.get("http://localhost:8000/auth/google", params={"user_id": user_id})
            if r.status_code == 200:
                auth_url = r.json().get("auth_url")
                if auth_url:
                    logger.info(f"Successfully generated Google auth URL for user: {user_email}")
                    st.success("✅ Redirecting to Google login...")
                    st.components.v1.html(f"""<script>window.open("{auth_url}", "_blank")</script>""")
                else:
                    logger.error(f"No auth_url received from server for user: {user_email}")
                    st.error("No auth_url received from server.")
            else:
                logger.error(f"Server returned status {r.status_code} for user: {user_email}")
                st.error(f"Server returned status {r.status_code}")
        except Exception as e:
            logger.error(f"Error linking Google account for user {user_email}: {str(e)}")
            st.error(f"Exception: {e}")

elif provider == "Outlook":
    if st.button("🔗 Link Outlook Account"):
        try:
            logger.info(f"Attempting to link Outlook account for user: {user_email}")
            r = requests.get("http://localhost:8000/auth/outlook", params={"user_id": user_id})
            auth_url = r.json().get("auth_url")
            if auth_url:
                logger.info(f"Successfully generated Outlook auth URL for user: {user_email}")
                st.markdown(f"[Click here to link Outlook account]({auth_url})")
            else:
                logger.error(f"No auth_url received from server for user: {user_email}")
                st.error("Failed to get authentication URL")
        except Exception as e:
            logger.error(f"Error linking Outlook account for user {user_email}: {str(e)}")
            st.error("An error occurred while linking Outlook account")
