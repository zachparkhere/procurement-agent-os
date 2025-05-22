import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import streamlit as st
import bcrypt
from po_agent_os.supabase_client_anon import supabase
import requests


# 🔐 Login check
if "user" not in st.session_state:
    st.warning("Please log in to continue.")
    st.stop()

user_email = st.session_state.user.email
user_row = supabase.table("users").select("id").eq("email", user_email).single().execute().data
user_id = user_row["id"]

st.sidebar.markdown(f"**Logged in as:** {user_email}")

# ✅ DB에서 현재 사용자 정보 가져오기
user_res = supabase.table("users") \
    .select("eta_followup_interval_days, email_provider, email_address") \
    .eq("id", user_id) \
    .limit(1) \
    .execute()

user_data = user_res.data[0] if user_res.data else {}
current_interval = user_data.get("eta_followup_interval_days", 3)
current_provider = user_data.get("email_provider", None)
linked_email = user_data.get("email_address", None)

# 토큰을 session_state에서 직접 꺼내서 사용
access_token = st.session_state.get("access_token")
refresh_token = st.session_state.get("refresh_token")
if not access_token or not refresh_token:
    st.error("Missing tokens. Please log in again.")
    st.stop()

# ✅ Set Supabase auth session
try:
    supabase.auth.set_session(
        access_token,
        refresh_token
    )
except Exception as e:
    st.error("Authentication failed. Please log in again.")
    st.exception(e)
    st.stop()

# -----------------------
# 🔑 Password Section
# -----------------------
st.markdown("---")
st.subheader("🔒 Update Your Password")

new_pw = st.text_input("New password", type="password")
new_pw2 = st.text_input("Confirm new password", type="password")

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
        ).eq("id", user_id).execute()
        if result.data:
            st.success("🎉 Password successfully updated!")
        else:
            st.error("Something went wrong. Please try again.")

# -----------------------
# ⏱️ ETA Follow-up Interval
# -----------------------
st.markdown("---")
st.subheader("⏱️ ETA Follow-up Interval (days)")
st.caption("How often to remind vendors who haven't shared an ETA.")

new_interval = st.number_input("Change interval:", min_value=1, max_value=30, value=current_interval, step=1)

if st.button("✅ Save Interval"):
    result = supabase.table("users").update(
        {"eta_followup_interval_days": new_interval}
    ).eq("id", user_id).execute()
    if result.data:
        st.success(f"Interval updated to {new_interval} days.")
    else:
        st.error("Failed to update. Please try again.")

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
            r = requests.get("http://localhost:8000/auth/google", params={"user_id": user_id})
            if r.status_code == 200:
                auth_url = r.json().get("auth_url")
                if auth_url:
                    st.success("✅ Redirecting to Google login...")
                    st.components.v1.html(f"""<script>window.open("{auth_url}", "_blank")</script>""")
                else:
                    st.error("No auth_url received from server.")
            else:
                st.error(f"Server returned status {r.status_code}")
        except Exception as e:
            st.error(f"Exception: {e}")

elif provider == "Outlook":
    if st.button("🔗 Link Outlook Account"):
        r = requests.get("http://localhost:8000/auth/outlook", params={"user_id": user_id})
        auth_url = r.json().get("auth_url")
        if auth_url:
            st.markdown(f"[Click here to link Outlook account]({auth_url})")
