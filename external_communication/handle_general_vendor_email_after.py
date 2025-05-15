import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "utils"))

from config import supabase
from aggregate_context_blocks import aggregate_context_blocks as get_context_blocks
from analyze_vendor_emails import analyze_email_content as analyze_vendor_email_with_llm
from generate_multi_context_reply import generate_multi_context_reply as generate_reply_draft
from utils.attachment_parser import extract_text_from_attachments

def get_thread_po_mapping():
    resp = supabase.table("email_logs").select("thread_id", "po_number")\
        .neq("thread_id", None).neq("po_number", None).execute()
    mapping = {}
    for row in resp.data:
        mapping[row["thread_id"]] = row["po_number"]
    return mapping

def get_latest_po_by_vendor(vendor_email: str) -> str | None:
    resp = supabase.table("email_logs").select("po_number") \
        .eq("recipient_email", vendor_email) \
        .neq("po_number", None) \
        .order("created_at", desc=True) \
        .limit(1).execute()
    if resp.data:
        return resp.data[0]["po_number"]
    return None

def handle_general_vendor_email():
    print("[📬 VENDOR AGENT] Scanning vendor replies...")

    resp = supabase.table("email_logs").select("*")\
        .eq("direction", "inbound")\
        .eq("status", "received")\
        .order("received_at", desc=True).execute()
    emails = resp.data

    thread_to_po = get_thread_po_mapping()
    processed_threads = set()

    for email in emails:
        thread_id = email.get("thread_id")
        if thread_id in processed_threads:
            continue
        processed_threads.add(thread_id)

        email_body = email.get("body", "")
        email_subject = email.get("subject", "")
        received_at = email.get("received_at")
        vendor_email = email.get("sender_email")

        print(f"📨 Processing email from thread {thread_id}:\nSubject: {email_subject}\nReceived at: {received_at}")

        # Step 1: thread_id -> po_number
        po_number = thread_to_po.get(thread_id)
        if po_number:
            print(f"🔗 Found PO number {po_number} mapped to thread {thread_id}")
        else:
            po_number = get_latest_po_by_vendor(vendor_email)
            if po_number:
                print(f"🔎 Inferred PO number by vendor: {po_number}")
            else:
                print("⚠️ Could not determine PO number — proceeding with placeholder.")
                po_number = "UNKNOWN"

        attachments = email.get("attachments", [])
        attachment_text = extract_text_from_attachments(attachments)
        full_input = email_body + "\n\n" + attachment_text

        info = analyze_vendor_email_with_llm(full_input, po_number, email_subject)
        print("Raw LLM response for info needs:")
        print(info)

        if not info.get("reply_needed"):
            print("✅ No reply needed for this email.")
            continue

        info_needed = info.get("information_needed", [])
        query_text = email_body  # 또는 full_input 도 가능
        context_blocks = get_context_blocks(info_needed, query_text)

    try:
        generate_reply_draft(po_number, info, context_blocks, thread_id)
        print(f"[✅ VENDOR AGENT] Draft created for PO {po_number}")
    except Exception as e:
        print(f"[❌ DRAFT GENERATION ERROR for PO {po_number}] {e}")
