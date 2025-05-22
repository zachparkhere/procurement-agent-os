import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from config import settings, supabase
from email_draft_confirm import get_gmail_service, send_email_reply

AUTO_SEND_ENABLED = False  # safe mode

async def handle_draft_send_message(payload: dict):
    print("[📨 DRAFT AGENT] Checking for auto-approved drafts...")

    try:
        response = supabase.table("email_logs") \
            .select("*, llm_draft(*)") \
            .eq("status", "draft") \
            .eq("llm_draft.auto_approve", True) \
            .eq("email_type", "follow_up_eta_present") \
            .is_("sent_at", "null") \
            .execute()

        drafts = response.data
        if not drafts:
            print("[ℹ️ DRAFT AGENT] No eligible drafts to send.")
            return

        if not AUTO_SEND_ENABLED:
            print(f"[🛑 DRAFT AGENT] AUTO_SEND_ENABLED = False → Skipping {len(drafts)} draft(s)")
            return

        for draft in drafts:
            to_email = draft["recipient_email"]
            subject = draft["subject"]
            body = draft["llm_draft"]["draft_body"]

            # (예시) user_row = supabase.table("users").select("*").eq("email", to_email).single().execute().data
            # service = get_gmail_service(user_row)
            # thread_id = send_email_reply(service, to_email, subject, body, thread_id)

            thread_id = send_email_reply(to_email, subject, body)
            now = datetime.utcnow().isoformat()

            supabase.table("email_logs").update({
                "thread_id": thread_id,
                "status": "sent",
                "sent_at": now
            }).eq("id", draft["id"]).execute()

            if draft.get("po_number"):
                supabase.table("purchase_orders").update({
                    "submitted_at": now
                }).eq("po_number", draft["po_number"]).execute()

            print(f"[✅ DRAFT AGENT] Sent draft {draft['id']} to {to_email}")

    except Exception as e:
        print(f"[❌ DRAFT AGENT ERROR] {e}")