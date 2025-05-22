from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from po_agent_os.external_communication.config import supabase
from datetime import datetime
import os
import dateutil.parser  # ✅ 이거 pip install 필요함 (명령은 아래에)

def get_gmail_service(user_row: dict):
    """Returns a Gmail API service authenticated with the user's token"""
    expiry_raw = user_row["email_token_expiry"]
    expiry_dt = dateutil.parser.parse(expiry_raw) if isinstance(expiry_raw, str) else expiry_raw

    creds = Credentials(
        token=user_row["email_access_token"],
        refresh_token=user_row["email_refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        expiry=expiry_dt
    )

    # ✅ access token 만료 시 자동 갱신
    if not creds.valid and creds.expired and creds.refresh_token:
        print(f"♻️ Refreshing token for user {user_row['email']}")
        creds.refresh(Request())

        # Supabase 업데이트
        supabase.table("users").update({
            "email_access_token": creds.token,
            "email_token_expiry": creds.expiry.isoformat(),
            "email_token_json": creds.to_json()
        }).eq("id", user_row["id"]).execute()

    return build("gmail", "v1", credentials=creds)

def send_email_reply(service, to_email, subject, body, thread_id):
    from email.mime.text import MIMEText
    import base64
    message = MIMEText(body, "plain")
    message["to"] = to_email
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {"raw": raw_message, "threadId": thread_id}
    sent_message = service.users().messages().send(userId="me", body=message_body).execute()
    return sent_message.get("threadId")

def send_approved_drafts():
    """send_approved가 True이고 sent_at이 null인 llm_draft를 찾아 실제 이메일을 발송"""
    drafts = supabase.table("llm_draft").select("*").eq("send_approved", True).is_("sent_at", "null").execute().data
    print(f"🔄 Found {len(drafts)} approved drafts needing send.")

    for draft in drafts:
        email_log_data = supabase.table("email_logs").select("*").eq("id", draft["email_log_id"]).execute().data
        if not email_log_data:
            print(f"⚠️ No email log found for draft_id={draft['draft_id']}")
            continue
        email_log = email_log_data[0]

        user_data = supabase.table("users").select("*").eq("email", email_log["sender_email"]).execute().data
        if not user_data:
            print(f"❌ No user found for email {email_log['sender_email']}")
            continue
        user_row = user_data[0]
        print(f"🔑 Using token for user: {user_row['email']} | token exp: {user_row['email_token_expiry']}")

        try:
            service = get_gmail_service(user_row)

            to_email = email_log.get("sender_email")  # ✅ 답장이므로 sender_email = 수신자
            subject = email_log.get("subject")
            thread_id = email_log.get("thread_id")
            body = draft.get("sent_body") or draft.get("draft_body")

            print(f"✉️ Sending email: draft_id={draft['draft_id']} → to {to_email} | subject: {subject}")

            thread_id_sent = send_email_reply(service, to_email, subject, body, thread_id)
            now = datetime.utcnow().isoformat()

            supabase.table("llm_draft").update({
                "sent_at": now,
                "thread_id": thread_id_sent
            }).eq("draft_id", draft["draft_id"]).execute()

            supabase.table("email_logs").update({
                "thread_id": thread_id_sent,
                "sent_at": now,
                "status": "sent"
            }).eq("id", email_log["id"]).execute()

            print(f"✅ Sent email for draft_id={draft['draft_id']}")

        except Exception as e:
            print(f"❌ Failed to send email for draft_id={draft['draft_id']}: {e}")
