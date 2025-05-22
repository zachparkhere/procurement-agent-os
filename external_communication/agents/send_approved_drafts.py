import os
import base64
import time
from datetime import datetime
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from external_communication.utils.email_utils import get_gmail_service
from config import supabase

# ✅ Create MIME message
def create_message(to_email, subject, body_text):
    message = MIMEText(body_text, "plain")
    message["to"] = to_email
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw_message}

# ✅ Main draft sender logic (runs every few seconds)
def send_approved_drafts():
    """Find all send_approved drafts that haven't been sent yet and send them via Gmail API."""
    drafts = supabase.table("llm_draft").select("*").eq("send_approved", True).is_("sent_at", "null").execute().data

    for draft in drafts:
        email_log_res = supabase.table("email_logs").select("*").eq("id", draft["email_log_id"]).execute()
        if not email_log_res.data:
            continue

        email_log = email_log_res.data[0]
        user_id = email_log.get("user_id")
        if not user_id:
            print(f"❌ No user_id linked to email_log {email_log['id']}")
            continue

        user_res = supabase.table("users").select("*").eq("id", user_id).limit(1).execute()
        if not user_res.data:
            print(f"❌ No user found for user_id {user_id}")
            continue
        user = user_res.data[0]

        # ✅ Get authenticated Gmail service for the user
        try:
            service = get_gmail_service(user)
        except Exception as e:
            print(f"❌ Failed to create Gmail service for user {user_id}: {e}")
            continue

        to_email = email_log.get("sender_email")
        subject = email_log.get("subject")
        thread_id = email_log.get("thread_id")
        body = draft.get("sent_body") or draft.get("draft_body")

        if not (to_email and subject and body):
            print(f"⚠️ Missing to_email/subject/body for draft {draft['draft_id']}")
            continue

        try:
            message = create_message(to_email, subject, body)
            if thread_id:
                message["threadId"] = thread_id

            sent_message = service.users().messages().send(userId="me", body=message).execute()
            thread_id_sent = sent_message.get("threadId")

            now = datetime.utcnow().isoformat()

            # ✅ Update llm_draft
            supabase.table("llm_draft").update({
                "sent_at": now,
                "thread_id": thread_id_sent
            }).eq("draft_id", draft["draft_id"]).execute()

            # ✅ Update email_log
            supabase.table("email_logs").update({
                "thread_id": thread_id_sent,
                "sent_at": now,
                "status": "sent"
            }).eq("id", email_log["id"]).execute()

            print(f"✅ Sent email for draft_id={draft['draft_id']}")

        except Exception as e:
            print(f"❌ Failed to send email for draft_id={draft['draft_id']}: {e}")

# ✅ Loop runner
if __name__ == "__main__":
    print("[✅ 워커 시작] send_approved_drafts를 5초마다 실행합니다.")
    while True:
        send_approved_drafts()
        time.sleep(5)
