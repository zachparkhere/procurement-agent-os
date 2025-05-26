import sys
import os
from datetime import datetime
from po_agent_os.supabase_client import supabase
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from external_communication.analyze_vendor_emails import analyze_email_content
from external_communication.aggregate_context_blocks import aggregate_context_blocks as get_context_blocks
from external_communication.generate_multi_context_reply import generate_multi_context_reply as generate_reply_draft
from utils.email_thread_utils import get_latest_thread_id_for_po

# Load Supabase
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

def handle_general_vendor_email():
    print("[📬 VENDOR AGENT] Scanning vendor replies...")
    # Step 1: 모든 이메일을 thread_id별로 최신순 정렬하여 가져옴
    response = supabase.table("email_logs") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute()
    emails = response.data

    # Step 2: thread_id별로 가장 최근 이메일만 추출
    latest_by_thread = {}
    for email in emails:
        thread_id = email.get("thread_id")
        if not thread_id:
            continue
        if thread_id not in latest_by_thread:
            latest_by_thread[thread_id] = email

    # Step 3: 각 thread의 최신 이메일만 검사
    for thread_id, email in latest_by_thread.items():
        try:
            # Step 3 조건: vendor inbound, status != processed
            if not (
                email.get("direction") == "inbound" and
                email.get("sender_role") == "vendor" and
                email.get("status") != "processed"
            ):
                continue

            email_subject = email.get("subject", "")
            email_body = email.get("body", "")
            vendor_email = email.get("sender_email", "")

            print(f"📨 Processing email from thread {thread_id}: Subject: {email_subject} | Received at: {email.get('sent_at')}")

            po_response = supabase.table("email_logs") \
                .select("po_number") \
                .eq("thread_id", thread_id) \
                .neq("po_number", None) \
                .limit(1) \
                .execute()

            if po_response.data:
                po_number = po_response.data[0]["po_number"]
                print(f"🔗 Found PO number {po_number} mapped to thread {thread_id}")
            else:
                po_number = "UNKNOWN"
                print("⚠️ Could not determine PO number — proceeding with placeholder.")

            full_input = f"{email_subject}\n\n{email_body}"
            info = analyze_email_content(email_subject, full_input, po_number)
            print("Raw LLM response for info needs:")
            print(info)

            if not info.get("reply_needed"):
                print("✅ No reply needed for this email.")
                continue

            info_needed = info.get("information_needed", [])
            query_text = email_body
            context_blocks = get_context_blocks(info_needed, query_text)

            for block in context_blocks:
                print("[🧩 CONTEXT BLOCK]", block)

            draft_body = generate_reply_draft(
                po_number=po_number,
                info=info,
                context_blocks=context_blocks,
                thread_id=thread_id,
                email_subject=email_subject,
                email_body=email_body
            )

            subject = f"Re: {email_subject}" if email_subject else "Regarding your recent update"
            
            # llm_draft에 초안 정보 저장
            supabase.table("llm_draft").insert({
                "email_log_id": email["id"],
                "draft_subject": subject,
                "recipient_email": vendor_email,
                "draft_body": draft_body,
                "auto_approve": False,
                "llm_analysis_result": None,
                "info_needed_to_reply": None,
                "suggested_reply_type": "general_reply",
                "reply_needed": True
            }).execute()

            # 해당 이메일 status를 processed로 업데이트
            supabase.table("email_logs").update({"status": "processed"}).eq("id", email["id"]).execute()

            print(f"[✅ VENDOR AGENT] Draft created and saved for PO {po_number}")

        except Exception as e:
            print(f"[❌ VENDOR REPLY AGENT ERROR] {e}")
