# send_po_email_and_update_thread.py

import os
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

from config import supabase

# Gmail API 범위 설정
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']

# credentials.json, token.json 경로를 po_agent_os 폴더 기준으로 설정
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')

def authenticate_gmail():
    """Gmail API 인증"""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        # 인증 후 token 저장
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message(to_email, subject, body):
    """Gmail API용 메시지 포맷 생성"""
    message = MIMEText(body, "plain")
    message["to"] = to_email
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw_message}

def send_email(service, to_email, subject, body):
    """Gmail API를 이용한 이메일 발송"""
    message = create_message(to_email, subject, body)
    sent_message = service.users().messages().send(userId="me", body=message).execute()
    return sent_message.get("threadId")

def send_po_email_and_update_thread(po_number):
    # llm_draft에서 초안 가져오기
    draft = supabase.table("llm_draft") \
        .select("*") \
        .eq("po_number", po_number) \
        .eq("suggested_reply_type", "po_confirmation") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    
    if not draft.data:
        print(f"❌ No draft found for PO {po_number}")
        return None
    
    draft = draft.data[0]
    
    # 이메일 전송
    service = authenticate_gmail()
    thread_id = send_email(
        service,
        to_email=draft["recipient_email"],
        subject=draft["subject"],
        body=draft["draft_body"]
    )
    
    # PO 업데이트
    now = datetime.utcnow().isoformat()
    supabase.table("purchase_orders").update({
        "submitted_at": now
    }).eq("po_number", po_number).execute()
    
    print(f"✅ Email sent for PO {po_number} (thread ID: {thread_id})")
    return thread_id

if __name__ == "__main__":
    send_po_emails_and_update_threads() 