# email_draft_confirm.py

import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from send_email import send_email_and_update

# Load env and connect
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Fetch pending drafts
def fetch_pending_drafts():
    response = supabase.table("email_logs") \
        .select("id, request_form_id, subject, draft_body, recipient_email, sent_at, status, trigger_reason, summary") \
        .eq("status", "draft") \
        .is_("sent_at", "null") \
        .execute()
    return response.data

# 2. Display and confirm
def review_and_send():
    drafts = fetch_pending_drafts()
    if not drafts:
        print("✅ No pending drafts to review.")
        return

    for draft in drafts:
        print("\n==============================")
        print(f"📬 Draft ID: {draft['id']}")
        print(f"📨 To: {draft['recipient_email']}")
        print(f"📌 Reason: {draft.get('trigger_reason')} ({draft.get('summary', 'No summary')})")
        print(f"📝 Subject: {draft['subject']}")
        print(f"📄 Body:\n{draft['draft_body']}")
        print("==============================")

        confirm = input("✅ Send this email? (y/n): ").lower()
        if confirm == "y":
            # Send email
            send_email_and_update(
                po_id=draft['request_form_id'],
                email_subject=draft['subject'],
                email_body=draft['draft_body'],
                recipient_email=draft['recipient_email']
            )
            
            # Update email_logs with sent timestamp and status
            supabase.table("email_logs").update({
                "sent_at": datetime.utcnow().isoformat(),
                "status": "sent"
            }).eq("id", draft["id"]).execute()
            
            print(f"✅ Email sent and status updated for draft ID {draft['id']}")
        else:
            print(f"❌ Skipping and deleting draft ID {draft['id']}")
            # Delete skipped draft
            supabase.table("email_logs").delete().eq("id", draft["id"]).execute()
            print(f"✅ Draft ID {draft['id']} has been deleted")

if __name__ == "__main__":
    review_and_send() 