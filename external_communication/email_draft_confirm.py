# email_draft_confirm.py

import os
import sys
import base64
from datetime import datetime
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from utils.email_utils import get_gmail_service, send_email_reply

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from external_communication.config import settings

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']

# credentials.json, token.json 경로를 po_agent_os 폴더 기준으로 설정
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'token.json')

def confirm_and_send_drafts():
    """Display drafts for human confirmation and send emails upon approval."""
    service = get_gmail_service()

    # email_logs와 llm_draft 조인하여 조회
    response = supabase.table("email_logs") \
        .select("*, llm_draft(*)") \
        .eq("status", "draft") \
        .is_("sent_at", "null") \
        .execute()
    
    drafts = response.data
    if not drafts:
        print("No drafts available for confirmation.")
        return

    for draft in drafts:
        print("\n--- Draft Preview ---")
        print(f"ID: {draft['id']}")
        print(f"Recipient: {draft['recipient_email']}")
        print(f"Subject: {draft['subject']}")
        print(f"Body:\n{draft['llm_draft']['draft_body']}")
        print("----------------------")

        decision = input("Send this email? (y/n): ").strip().lower()

        if decision == 'y':
            try:
                # Step 1: Send the email
                thread_id = send_email_reply(
                    service,
                    to_email=draft["recipient_email"],
                    subject=draft["subject"],
                    body=draft["llm_draft"]["draft_body"]
                )

                # Step 2: Update email_logs
                now = datetime.utcnow().isoformat()
                supabase.table("email_logs").update({
                    "thread_id": thread_id,
                    "status": "sent",
                    "sent_at": now
                }).eq("id", draft["id"]).execute()

                # Step 3: Update purchase_orders if applicable
                if draft.get("po_number"):
                    supabase.table("purchase_orders").update({
                        "submitted_at": now
                    }).eq("po_number", draft["po_number"]).execute()

                print(f"✅ Successfully sent and updated draft ID: {draft['id']} (thread ID: {thread_id})")

            except Exception as e:
                print(f"❌ Failed to send email for draft ID {draft['id']}: {e}")

        elif decision == 'n':
            print(f"Skipping draft ID: {draft['id']}.")

        else:
            print("Invalid input. Skipping draft.")

def authenticate_gmail():
    creds = None
    credentials_path = CREDENTIALS_PATH
    token_path = TOKEN_PATH
    # ... 기존 코드 ...

if __name__ == "__main__":
    confirm_and_send_drafts() 