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

# 프로젝트 루트(=po_agent_os) 경로
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Vendor_email_logger_agent'))
from config import supabase

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']

# credentials.json, token.json 경로를 po_agent_os 폴더 기준으로 설정
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'credentials.json')
TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'token.json')

def authenticate_gmail():
    """Authenticate and return a Gmail API service."""
    creds = None
    credentials_path = CREDENTIALS_PATH
    token_path = TOKEN_PATH
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message(to_email, subject, body_text):
    """Create a MIME email message."""
    message = MIMEText(body_text, "plain")
    message["to"] = to_email
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw_message}

def send_email(service, to_email, subject, body):
    """Send an email using the Gmail API."""
    message = create_message(to_email, subject, body)
    sent_message = service.users().messages().send(userId="me", body=message).execute()
    return sent_message.get("threadId")

def main():
    """Display drafts for human confirmation and send emails upon approval."""
    service = authenticate_gmail()

    response = supabase.table("email_logs").select("*").eq("status", "draft").is_("sent_at", "null").execute()
    drafts = response.data

    if not drafts:
        print("No drafts available for confirmation.")
        return

    for draft in drafts:
        print("\n--- Draft Preview ---")
        print(f"ID: {draft['id']}")
        print(f"Recipient: {draft['recipient_email']}")
        print(f"Subject: {draft['subject']}")
        print(f"Body:\n{draft['draft_body']}")
        print("----------------------")

        decision = input("Send this email? (y/n): ").strip().lower()

        if 