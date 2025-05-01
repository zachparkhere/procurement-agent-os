# handle_general_vendor_email.py

import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from llm_extract_info_needs import llm_extract_info_needs
from aggregate_context_blocks import aggregate_context_blocks
from generate_multi_context_reply import generate_multi_context_reply
from email_context_utils import get_last_conversation_by_request_form
from utils.summary_utils import summarize_text
import supabase

# Load environment variables and initialize Supabase client
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# # Predefined simple acknowledgment body (Removed)
# SIMPLE_ACK_BODY = "Thank you for the update. We appreciate the confirmation."

def extract_po_number(subject: str, body: str) -> str:
    """
    이메일 제목과 본문에서 PO 번호를 추출합니다.
    PO 번호 형식: PO-YYYY-XXX 또는 POYYYYXXX
    """
    # 정규식 패턴
    patterns = [
        r'PO-\d{4}-\d{3,}',  # PO-2024-001 형식
        r'PO\d{4}\d{3,}',    # PO2024001 형식
    ]
    
    # 제목에서 먼저 검색
    for pattern in patterns:
        match = re.search(pattern, subject)
        if match:
            return match.group(0)
    
    # 본문에서 검색
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return match.group(0)
    
    return None

def get_or_create_thread_id(po_number: str, email: dict) -> str:
    """
    PO 번호에 해당하는 thread_id를 가져오거나 새로 생성합니다.
    """
    if not po_number:
        return ""
        
    # 기존 thread_id 검색
    response = supabase.table("email_logs") \
        .select("thread_id") \
        .eq("po_number", po_number) \
        .not_.is_("thread_id", "null") \
        .not_.eq("thread_id", "") \
        .limit(1) \
        .execute()
        
    if response.data:
        return response.data[0]["thread_id"]
    
    return ""  # 새 thread는 이메일 발송 시 생성됨

def get_thread_po_mapping(thread_id: str) -> str:
    """
    Thread ID에 매핑된 PO 번호를 조회합니다.
    """
    if not thread_id:
        return None
        
    response = supabase.table("email_logs") \
        .select("po_number,created_at") \
        .eq("thread_id", thread_id) \
        .not_.is_("po_number", "null") \
        .order("created_at.asc") \
        .limit(1) \
        .execute()
        
    if response.data:
        return response.data[0]["po_number"]
    return None

def verify_po_number(po_number: str) -> bool:
    """
    PO 번호가 실제로 존재하는지 확인합니다.
    """
    if not po_number:
        return False
        
    response = supabase.table("purchase_orders") \
        .select("po_number") \
        .eq("po_number", po_number) \
        .execute()
        
    return bool(response.data)

def check_last_communication_is_admin(thread_id: str) -> bool:
    """
    해당 thread의 가장 최근 커뮤니케이션이 admin(우리 쪽)에서 발신한 것인지 확인합니다.
    """
    if not thread_id:
        return False
        
    response = supabase.table("email_logs") \
        .select("sender_role,created_at") \
        .eq("thread_id", thread_id) \
        .order("created_at.desc") \
        .limit(1) \
        .execute()
        
    if response.data:
        return response.data[0]["sender_role"] == "admin"
    return False

def handle_general_vendor_email():
    print("🔍 Step 1: Fetching the latest vendor emails for each unique thread...")
    
    # 1. 먼저 unique thread_id 목록을 가져옴
    threads_response = supabase.table("email_logs") \
        .select("thread_id") \
        .not_.is_("thread_id", "null") \
        .not_.eq("thread_id", "") \
        .execute()
    
    unique_threads = set(row["thread_id"] for row in threads_response.data if row["thread_id"])
    print(f"📌 Found {len(unique_threads)} unique thread(s)")
    
    results = []
    for thread_id in unique_threads:
        # 최신 커뮤니케이션이 admin 발신인지 확인
        if check_last_communication_is_admin(thread_id):
            print(f"\n📨 Thread {thread_id}: 최근 발신이 admin이므로 스킵")
            continue
            
        # 2. 각 thread의 최신 vendor 이메일 조회
        response = supabase.table("email_logs") \
            .select("*") \
            .eq("thread_id", thread_id) \
            .eq("sender_role", "vendor") \
            .in_("direction", ["inbound", "incoming"]) \
            .is_("draft_body", "null") \
            .order("created_at.desc") \
            .limit(1) \
            .execute()
            
        if not response.data:
            continue
            
        email = response.data[0]
        email_subject = email["subject"]
        email_body = email["body"]
        
        print(f"\n📨 Processing email from thread {thread_id}:")
        print(f"Subject: {email_subject}")
        print(f"Received at: {email['received_at']}")
        
        # 1. Thread ID에 매핑된 PO 번호 확인
        po_number = None
        if thread_id:
            po_number = get_thread_po_mapping(thread_id)
            if po_number:
                print(f"🔗 Found PO number {po_number} mapped to thread {thread_id}")
        
        # 2. 매핑된 PO 번호가 없는 경우, 이메일에서 추출 시도
        if not po_number:
            po_number = email.get("po_number")  # 이미 저장된 PO 번호 확인
            
            if not po_number:
                # 이메일 제목과 본문에서 PO 번호 추출 시도
                extracted_po = extract_po_number(email_subject, email_body)
                if extracted_po and verify_po_number(extracted_po):
                    po_number = extracted_po
                    print(f"📝 Extracted and verified PO number: {po_number}")
                else:
                    print("ℹ️ No valid PO number found in email content")
                    continue  # PO 번호를 찾을 수 없는 경우 스킵
        
        print(f"PO Number: {po_number}")
        print(f"Body: {email_body[:200]}...")

        try:
            raw = llm_extract_info_needs(email_subject, email_body)
            print(f"Raw LLM response for info needs:\n{raw}")
            
            try:
                start = raw.index('{')
                end = raw.rindex('}') + 1
                json_str = raw[start:end]
                info = json.loads(json_str)
                
            except (ValueError, json.JSONDecodeError):
                print("❌ Error: Could not parse JSON from LLM response.")
                print(f"Raw response was: {raw}")
                continue

        except Exception as e:
            print(f"❌ Error calling llm_extract_info_needs: {e}")
            continue

        # Check if reply is needed
        reply_needed = info.get("reply_needed")
        suggested_reply_type = info.get("suggested_reply_type", "no_reply")

        if not reply_needed or suggested_reply_type == "no_reply":
            print("ℹ️ No reply needed according to LLM or suggested type is no_reply.")
            continue

        # Always use the info_needed identified by the LLM
        info_needed = info.get("information_needed", [])
        print(f"📌 Info needed identified by LLM: {info_needed}")

        # Load recent conversation context for this po_number
        email_thread_context = ""
        if po_number:
            print(f"\n📬 Previous emails for po_number {po_number}:")
            email_thread_context_rows = get_last_conversation_by_request_form(po_number, n=3)
            
            email_thread_context_rows = [
                row for row in email_thread_context_rows 
                if row.get('status') in ['sent', 'received'] 
                and row.get('body') is not None
            ]
            
            if email_thread_context_rows:
                print(f"Found {len(email_thread_context_rows)} previous emails")
            else:
                print("No previous emails found.")
                
            email_thread_context = "\n\n".join(
                f"[{row['created_at']} | {row['sender_role']} | {row['direction']}]\nSubject: {row['subject']}\nBody: {row['body'][:500]}" 
                for row in reversed(email_thread_context_rows)
            )

        # Step 2: Always fetch context based on info_needed
        print("\n🔎 Step 2: Fetching context from vector DB...")
        context_blocks = []
        try:
            context_blocks = aggregate_context_blocks(info_needed, email_subject + "\n" + email_body)
            print(f"📚 Context blocks fetched: {len(context_blocks)}")
            if context_blocks:
                for i, (table, desc, schema_id) in enumerate(context_blocks):
                    print(f"  Context [{i+1}] From {table} (ID: {schema_id}): {desc[:100]}...")
        except Exception as e:
            print(f"❌ Error during aggregate_context_blocks: {e}")
            print("⚠️ Proceeding without context due to fetching error.")
            context_blocks = []

        # Step 3: Generate Reply using context
        print(f"\n✍️ Step 3: Generating reply (LLM suggested type: {suggested_reply_type})...")
        reply = ""
        try:
            reply = generate_multi_context_reply(
                email_subject=email_subject,
                email_body=email_body,
                context_blocks=[(table, desc) for table, desc, _ in context_blocks],
                suggested_reply_type=suggested_reply_type,
                email_thread_context=email_thread_context
            )
            print("✅ Reply generated successfully.")
        except Exception as e:
            print(f"❌ Error during generate_multi_context_reply: {e}")
            continue

        result = {
            "intent": info.get("intent"),
            "suggested_reply_type": suggested_reply_type,
            "info_needed": info_needed,
            "context_blocks": [(table, desc, schema_id) for table, desc, schema_id in context_blocks],
            "draft_body": reply,
            "email": email
        }
        results.append(result)
        
        # Save draft immediately
        if save_draft_to_email_logs(result):
            print(f"✅ Draft saved for thread {thread_id}")
        else:
            print(f"❌ Failed to save draft for thread {thread_id}")

    return results

# Example usage
def demo():
    subject = "RE: PO-2025-001 Delivery Date Confirmation"
    body = "We confirm that the goods will be delivered by May 2nd."
    result = handle_general_vendor_email(subject, body)
    if result:
        print("\n📝 Draft Email:\n" + result["draft_body"])
        print(f"\nℹ️ Suggested Reply Type: {result.get('suggested_reply_type')}")
        print(f"🔍 Context Used ({len(result.get('context_blocks', []))} blocks):")
        for i, (table, desc, schema_id) in enumerate(result.get('context_blocks', [])):
            print(f"  [{i+1}] From {table} (ID: {schema_id}): {desc[:100]}...") # Print first 100 chars

def save_draft_to_email_logs(result):
    """Save the generated draft to email_logs table"""
    if not result:
        print("❌ No result to save")
        return False

    original_email = result["email"]
    thread_id = original_email.get("thread_id", "")
    
    # 1. Thread ID에 매핑된 PO 번호 확인
    po_number = None
    if thread_id:
        po_number = get_thread_po_mapping(thread_id)
    
    # 2. 매핑된 PO 번호가 없는 경우
    if not po_number:
        # 원본 이메일의 PO 번호 확인
        po_number = original_email.get("po_number")
        
        # PO 번호가 없으면 추출 시도
        if not po_number:
            extracted_po = extract_po_number(original_email["subject"], original_email["body"])
            if extracted_po and verify_po_number(extracted_po):
                po_number = extracted_po
                print(f"📝 Using extracted PO number: {po_number}")
    
    # Extract actual email body from the draft
    draft_body = result["draft_body"]
    if "---" in draft_body:
        draft_body = draft_body.split("---")[-1].strip()
    
    if draft_body.startswith("Body:"):
        draft_body = draft_body[5:].strip()
    
    summary = summarize_text(draft_body)
    
    # Get vendor email
    vendor_email = original_email.get("sender_email")
    if not vendor_email and po_number:
        try:
            request_form = supabase.table("request_form") \
                .select("vendor_id(email)") \
                .eq("id", po_number) \
                .single() \
                .execute()
            if request_form.data and request_form.data["vendor_id"]:
                vendor_email = request_form.data["vendor_id"]["email"]
        except Exception as e:
            print(f"❌ Error fetching vendor email: {e}")
            return False

    if not vendor_email:
        print("❌ Could not find vendor email address")
        return False

    current_time = datetime.utcnow().isoformat()

    try:
        draft_data = {
            "po_number": po_number,
            "subject": original_email['subject'],
            "draft_body": draft_body,
            "summary": summary,
            "body": None,
            "recipient_email": vendor_email,
            "sender_email": "system@purchaseorder.com",
            "status": "draft",
            "trigger_reason": "vendor_reply",
            "email_type": result.get("suggested_reply_type", "general_reply"),
            "sender_role": "admin",
            "direction": "outgoing",
            "thread_id": thread_id,
            "has_attachment": None,
            "attachment_types": [],
            "created_at": current_time,
            "llm_analysis_result": json.dumps(result.get("intent", {})),
            "info_needed_to_reply": json.dumps(result.get("info_needed", [])),
            "suggested_reply_type": result.get("suggested_reply_type", "general_reply"),
            "reply_needed": True
        }
        
        print("\n📝 Attempting to save draft with data:")
        print(draft_data)
        
        response = supabase.table("email_logs").insert(draft_data).execute()
        
        if response.data:
            print("\n✅ Draft saved to email_logs! You can now review and send it using email_draft_confirm.py")
            return True
        else:
            print("\n❌ No data returned from insert operation")
            return False
            
    except Exception as e:
        print(f"\n❌ Error saving draft to email_logs: {e}")
        return False

if __name__ == "__main__":
    result = handle_general_vendor_email()
    if result:
        print("\n📝 Generated Draft Email:")
        print("-" * 50)
        print(result["draft_body"])
        print("-" * 50)
        print(f"\nℹ️ Suggested Reply Type: {result.get('suggested_reply_type')}")
        print(f"🔍 Context Used ({len(result.get('context_blocks', []))} blocks):")
        for i, (table, desc, schema_id) in enumerate(result.get('context_blocks', [])):
            print(f"  [{i+1}] From {table} (ID: {schema_id}): {desc[:100]}...")
        
        # Save the draft
        save_draft_to_email_logs(result) 