# handle_general_vendor_email.py

import json
import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from llm_extract_info_needs import llm_extract_info_needs
from aggregate_context_blocks import aggregate_context_blocks
from generate_multi_context_reply import generate_multi_context_reply
from email_context_utils import get_last_conversation_by_request_form

# Load environment variables and initialize Supabase client
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# # Predefined simple acknowledgment body (Removed)
# SIMPLE_ACK_BODY = "Thank you for the update. We appreciate the confirmation."

def handle_general_vendor_email():
    # Get today's start in UTC for filtering
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    print("🔍 Step 1: Fetching the latest vendor email received today...")
    response = supabase.table("email_logs") \
        .select("*") \
        .eq("sender_role", "vendor") \
        .in_("direction", ["inbound", "incoming"]) \
        .is_("draft_body", "null") \
        .gt("received_at", today_start) \
        .order("received_at", desc=True) \
        .limit(1) \
        .execute()

    if not response.data:
        print("❌ No eligible vendor emails found today.")
        return None

    email = response.data[0]  # Get the latest email
    email_subject = email["subject"]
    email_body = email["body"]
    request_form_id = email.get("request_form_id")  # optional

    print(f"\n📨 Processing latest email:")
    print(f"Subject: {email_subject}")
    print(f"Received at: {email['received_at']}")
    print(f"Request Form ID: {request_form_id}")
    print(f"Body: {email_body[:200]}...")

    try:
        raw = llm_extract_info_needs(email_subject, email_body)
        print(f"Raw LLM response for info needs:\n{raw}") # Print raw response for debugging
        # Attempt to find JSON within potentially messy LLM output
        try:
            start = raw.index('{')
            end = raw.rindex('}') + 1
            json_str = raw[start:end]
            info = json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            print("❌ Error: Could not parse JSON from LLM response.")
            print(f"Raw response was: {raw}")
            return None

    except Exception as e:
        print(f"❌ Error calling llm_extract_info_needs: {e}")
        return None

    # Check if reply is needed
    reply_needed = info.get("reply_needed")
    suggested_reply_type = info.get("suggested_reply_type", "no_reply") # Keep this info

    if not reply_needed or suggested_reply_type == "no_reply":
        print("ℹ️ No reply needed according to LLM or suggested type is no_reply.")
        return None

    # Always use the info_needed identified by the LLM
    info_needed = info.get("information_needed", [])
    print(f"📌 Info needed identified by LLM: {info_needed}")

    # 🔄 Load recent conversation context for this request_form_id
    email_thread_context = ""
    if request_form_id:
        print(f"\n📬 Previous emails for request_form_id {request_form_id}:")
        email_thread_context_rows = get_last_conversation_by_request_form(request_form_id, n=3)
        
        # Filter emails: only sent/received status and non-null body
        email_thread_context_rows = [
            row for row in email_thread_context_rows 
            if row.get('status') in ['sent', 'received'] 
            and row.get('body') is not None
        ]
        
        if email_thread_context_rows:
            print(f"Found {len(email_thread_context_rows)} previous emails:")
            for i, row in enumerate(email_thread_context_rows, 1):
                print(f"\n--- Email {i} ---")
                print(f"Time: {row['created_at']}")
                print(f"Role: {row['sender_role']}")
                print(f"Direction: {row['direction']}")
                print(f"Subject: {row['subject']}")
                print(f"Body: {row['body'][:200]}...")
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
        context_blocks = [] # Ensure context_blocks is empty on error

    # Step 3: Generate Reply using context, passing the suggestion type
    print(f"\n✍️ Step 3: Generating reply (LLM suggested type: {suggested_reply_type})...")
    reply = ""
    try:
        reply = generate_multi_context_reply(
            email_subject=email_subject,
            email_body=email_body,
            context_blocks=[(table, desc) for table, desc, _ in context_blocks],  # Remove ID for reply generation
            suggested_reply_type=suggested_reply_type,
            email_thread_context=email_thread_context
        )
        print("✅ Reply generated successfully.")
    except Exception as e:
        print(f"❌ Error during generate_multi_context_reply: {e}")
        return None

    return {
        "intent": info.get("intent"),
        "suggested_reply_type": suggested_reply_type,
        "info_needed": info_needed,
        "context_blocks": [(table, desc, schema_id) for table, desc, schema_id in context_blocks],  # Include IDs in return
        "draft_body": reply,
        "email": email  # Include the original email for reference
    }

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
    
    # Extract actual email body from the draft
    draft_body = result["draft_body"]
    if "---" in draft_body:
        # Remove LLM analysis and keep only the actual email content
        draft_body = draft_body.split("---")[-1].strip()
    
    # Remove "Body:" prefix if present
    if draft_body.startswith("Body:"):
        draft_body = draft_body[5:].strip()
    
    # Get vendor email from the original email or request form
    vendor_email = None
    if original_email.get("sender_email"):
        vendor_email = original_email["sender_email"]
    elif original_email.get("request_form_id"):
        # Fetch vendor email from request form
        try:
            request_form = supabase.table("request_form") \
                .select("vendor_id(email)") \
                .eq("id", original_email["request_form_id"]) \
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
        # Save to email_logs with thread_id from original email
        draft_data = {
            "request_form_id": original_email.get("request_form_id"),
            "subject": original_email['subject'],  # Use original subject without Re: prefix
            "draft_body": draft_body,  # Use cleaned draft body
            "body": None,  # Drafts have null body
            "recipient_email": vendor_email,
            "sender_email": "system@purchaseorder.com",  # System email
            "status": "draft",
            "trigger_reason": "vendor_reply",
            "email_type": result.get("suggested_reply_type", "general_reply"),
            "sender_role": "system",
            "direction": "outgoing",
            "thread_id": "",
            "has_attachment": None,  # Set to null for potential future attachment logic
            "attachment_types": [],
            "created_at": current_time
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