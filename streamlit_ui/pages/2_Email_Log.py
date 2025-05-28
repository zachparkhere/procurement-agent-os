import streamlit as st
st.set_page_config(layout="wide")

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from po_agent_os.supabase_client_anon import supabase
from datetime import datetime
import html

supabase = supabase

# 로그인된 유저 정보 (세션에서 가져옴)
user_id = st.session_state.get("user_id")  # UUID
user_email = st.session_state.get("user_email")  # 이메일 주소

# 로그인 체크
if not user_id or not user_email:
    st.warning("You must be logged in to view your inbox.")
    st.stop()

# 이메일 조건: user_id 또는 sender/recipient_email 매칭
email_res = supabase.table("email_logs").select(
    "id, message_id, thread_id, po_number, sender_email, recipient_email, subject, body, created_at, direction, read, sent_at, received_at"
).or_(
    f"user_id.eq.{user_id}," +
    f"sender_email.ilike.%{user_email}%," +
    f"recipient_email.ilike.%{user_email}%"
).order("created_at", desc=True).execute()

emails = email_res.data or []


# 📌 스레드별로 마지막 이메일만 (inbound인 것만)
latest_inbound_per_thread = {}
for email in emails:
    thread_id = email.get("thread_id")
    if email.get("direction") == "inbound" and thread_id not in latest_inbound_per_thread:
        latest_inbound_per_thread[thread_id] = email

# 📌 선택된 스레드
selected_thread_id = st.session_state.get("selected_thread_id", None)

# 📍 왼쪽 + 오른쪽 레이아웃 구성
if selected_thread_id:
    col1, col2 = st.columns([1, 1])  # Inbox | Thread View
else:
    col1 = st.container()
    col2 = None  # Thread 없음

# =========================
# ✅ LEFT: Inbox Table
# =========================
with col1:
    st.subheader("📂 Email Inbox")

    # 테이블 헤더
    header_cols = st.columns([2, 1.5, 2, 3, 1, 1])
    header_cols[0].markdown("**Sender**")
    header_cols[1].markdown("**PO #**")
    header_cols[2].markdown("**Subject**")
    header_cols[3].markdown("**Preview**")
    header_cols[4].markdown("**Date**")
    header_cols[5].markdown("**Action**")

    # 행 렌더링
    for thread_id, email in latest_inbound_per_thread.items():
        sender = html.escape(email.get("sender_email", ""))
        po = html.escape(email.get("po_number") or "N/A")
        subject = html.escape(email.get("subject", ""))
        preview = html.escape(email.get("body", "")[:50] + "...")
        # Date: sent_at(발신) 또는 received_at(수신) 우선순위로 표시
        date_val = email.get("sent_at") if email.get("direction") == "outbound" else email.get("received_at")
        if not date_val:
            date_val = email.get("created_at", "")
        date_str = html.escape(str(date_val)[:10])

        row_cols = st.columns([2, 1.5, 2, 3, 1, 1])
        row_cols[0].markdown(sender)
        row_cols[1].markdown(po)
        row_cols[2].markdown(subject)
        row_cols[3].markdown(preview)
        row_cols[4].markdown(date_str)

        if row_cols[5].button("Check", key=f"check_{thread_id}"):
            st.session_state["selected_thread_id"] = thread_id
            st.rerun()

# =========================
# ✅ RIGHT: Thread Viewer (Only last inbound email body)
# =========================
if selected_thread_id and col2:
    with col2:
        st.subheader("📖 Email Thread")

        if st.button("Close"):
            del st.session_state["selected_thread_id"]
            st.rerun()

        # 해당 스레드의 가장 마지막 inbound 이메일 하나만 추출
        thread_emails = [
            e for e in emails if e["thread_id"] == selected_thread_id and e["direction"] == "inbound"
        ]

        if thread_emails:
            latest_email = sorted(thread_emails, key=lambda x: x["created_at"], reverse=True)[0]
            sender = latest_email.get("sender_email", "")
            if latest_email.get("direction") == "outbound":
                date_val = latest_email.get("sent_at")
            else:
                date_val = latest_email.get("received_at")
            if not date_val:
                date_val = latest_email.get("created_at", "")
            created_at = date_val
            subject = latest_email.get("subject", "")
            body = latest_email.get("body", "")

            st.markdown("---")
            st.markdown(f"**From:** {sender}")
            st.markdown(f"**Date:** {created_at}")
            st.markdown(f"**Subject:** {subject}")
            st.markdown(body)

            # ================================
            # ✅ REPLY SECTION with LLM Draft
            # ================================
            st.markdown("### ✍️ Reply to Email")

            latest_email_id = latest_email.get("id")
            draft_body = ""
            draft_id = None
            draft_approved = False
            if latest_email_id:
                draft_res = supabase.table("llm_draft").select("draft_id, draft_body, draft_approved, send_approved").eq("email_log_id", latest_email_id).execute()
                if draft_res.data:
                    draft_body = draft_res.data[0]["draft_body"] or ""
                    draft_id = draft_res.data[0]["draft_id"]
                    draft_approved = draft_res.data[0].get("draft_approved", False)

            # Approve 버튼
            if draft_id is not None:
                if not draft_approved:
                    if st.button("Approve Draft"):
                        supabase.table("llm_draft").update({"draft_approved": True}).eq("draft_id", draft_id).execute()
                        st.success("Draft has been approved.")
                        st.rerun()
                else:
                    st.info("This draft has already been approved.")

            with st.form("reply_form"):
                reply_text = st.text_area("Your message", value=draft_body, height=200)
                cc = st.text_input("CC (optional)", placeholder="e.g., zach@shift.com")
                uploaded_file = st.file_uploader("Attach file", type=["pdf", "jpg", "png", "docx"])
                submitted = st.form_submit_button("Send Reply")
                if submitted:
                    now = datetime.utcnow().isoformat()
                    if draft_id is not None:
                        # email_logs에서 정보 가져오기
                        email_log = supabase.table("email_logs").select("*").eq("id", latest_email_id).execute().data[0]
                        # 1. DB 업데이트만 수행 (메일 발송 X)
                        supabase.table("llm_draft").update({
                            "send_approved": True,
                            "sent_body": reply_text,
                            "sent_at": now
                        }).eq("draft_id", draft_id).execute()
                        supabase.table("email_logs").update({
                            "sent_at": now,
                            "status": "sent"
                        }).eq("id", latest_email_id).execute()
                    st.success("✅ Reply marked as ready to send (DB updated only, no email sent here).")
        else:
            st.info("No inbound email found in this thread.")