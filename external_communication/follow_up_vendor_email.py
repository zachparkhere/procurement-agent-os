# follow_up_vendor_email.py

import os
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
from utils.vector_search import find_latest_vendor_reply, find_last_eta_reply
from openai import OpenAI

# Load env
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SENDER_NAME = os.getenv("SENDER_NAME", "Procurement Team")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@yourcompany.com")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "Our Company")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def get_stale_pos(days_threshold=3):
    """Get POs that were sent more than X days ago"""
    cutoff_date = (datetime.utcnow() - timedelta(days=days_threshold)).isoformat()

    po_result = supabase.table("purchase_orders") \
        .select("*, request_form_id(id, vendor_id(*))") \
        .not_.is_("submitted_at", "null") \
        .lt("submitted_at", cutoff_date) \
        .execute()
    
    print(f"🔍 Found {len(po_result.data)} POs sent before {cutoff_date}")
    return po_result.data

def get_vendor_name(vendor_id):
    """Utility to fetch vendor name by ID"""
    try:
        vendor_result = supabase.table("vendors") \
            .select("name") \
            .eq("id", vendor_id) \
            .single() \
            .execute()
        if vendor_result.data:
            return vendor_result.data.get("name", "Valued Vendor")
        else:
            print(f"⚠️ Could not find vendor with ID: {vendor_id}")
            return "Valued Vendor"
    except Exception as e:
        print(f"❌ Error fetching vendor name for ID {vendor_id}: {e}")
        return "Valued Vendor"

def get_pos_with_vendor_reply_but_no_eta():
    """Extract POs that have vendor replies but no ETA"""
    response = supabase.table("email_logs") \
        .select("id, po_number, created_at") \
        .eq("sender_role", "vendor") \
        .order("created_at", desc=True) \
        .execute()

    pos = []
    seen = set()
    for row in response.data:
        po_number = row["po_number"]
        if po_number in seen:
            continue
        if not po_number or po_number == "None":
            log_id = row.get("id", "unknown")
            print(f"⚠️ Skipping email_log ID {log_id} because po_number is invalid (None or 'None').")
            continue
        seen.add(po_number)
        try:
            po = supabase.table("purchase_orders") \
                .select("*") \
                .eq("po_number", po_number) \
                .is_("eta", "null") \
                .single() \
                .execute()
        except Exception as e:
            log_id = row.get("id", "unknown")
            print(f"❌ Error querying purchase_orders for email_log ID {log_id} with po_number {po_number}: {e}")
            continue
        if po.data:
            pos.append(po.data)
    print(f"📌 [ETA Request] POs with vendor reply but no ETA: {len(pos)} found")
    return pos

def get_eta_reconfirmation_pos(days_since_eta_reply=2):
    """Find POs with ETA but no recent vendor response about ETA"""
    pos = []
    now = datetime.utcnow()

    # Find POs with existing ETA
    po_result = supabase.table("purchase_orders") \
        .select("*, request_form_id(id, vendor_id(*))") \
        .not_.is_("eta", "null") \
        .execute()

    for po in po_result.data:
        rf_id = po["request_form_id"]["id"]

        # Find vendor responses with ETA mentions for this request_form_id
        logs = supabase.table("email_logs") \
            .select("created_at, summary") \
            .eq("request_form_id", rf_id) \
            .eq("sender_role", "vendor") \
            .order("created_at", desc=True) \
            .execute()

        for log in logs.data:
            summary = (log.get("summary") or "").lower()
            if "eta" in summary:
                last_eta_date = datetime.fromisoformat(log["created_at"].replace("Z", ""))
                if (now - last_eta_date).days >= days_since_eta_reply:
                    pos.append(po)
                break  # Only check the most recent ETA mention
    print(f"📌 [ETA Reconfirmation] POs with ETA but no recent response: {len(pos)} found")
    return pos

def generate_initial_follow_up_draft(po_number: str, vendor_name: str, delivery_date: str, sender_name: str, sender_company: str) -> str:
    """Generate initial PO follow-up draft when no reply received"""
    prompt = f"""Write a professional follow-up email body to the vendor regarding the Purchase Order {po_number}.

Context:
- Vendor Name: {vendor_name}
- PO Number: {po_number}
- Expected Delivery Date (if available): {delivery_date}
- Sender Name: {sender_name}
- Sender Company: {sender_company}

Instructions:
- Mention the PO number.
- Politely ask for confirmation of receipt of the purchase order.
- Keep tone professional.
- Close with sender name and company.
- Return *only* the email body text.
"""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant drafting professional follow-up emails."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error generating initial draft for PO {po_number}: {e}")
        return None

def has_pending_draft(po_number: str, email_type: str) -> bool:
    """Check if there's already a pending draft for this PO and email type"""
    result = supabase.table("email_logs") \
        .select("id") \
        .eq("po_number", po_number) \
        .eq("email_type", email_type) \
        .eq("status", "draft") \
        .is_("sent_at", "null") \
        .execute()
    return bool(result.data)

def generate_eta_request_draft(po: dict, vendor_name: str, vendor_email: str) -> bool:
    """Generate ETA request draft when vendor replied but no ETA provided"""
    po_number = po["po_number"]
    # Check for existing draft
    if has_pending_draft(po_number, "follow_up_eta_missing"):
        print(f"⏭️ Skipping draft: Already pending for PO {po_number}, type: follow_up_eta_missing")
        return False
    issue_date = po.get("submitted_at", datetime.utcnow().isoformat())
    try:
        formatted_date = datetime.fromisoformat(issue_date.replace('Z', '')).strftime('%B %d, %Y')
    except:
        formatted_date = issue_date
    subject = f"Follow-up on PO {po_number} — Awaiting ETA"
    body = f"""Dear {vendor_name},\n\nThank you for your recent communication regarding Purchase Order {po_number} (sent on {formatted_date}).\n\nWe would greatly appreciate if you could provide us with the estimated delivery date (ETA) for this order.\n\nThank you for your cooperation.\n\nBest regards,\n{SENDER_NAME}\nProcurement Team"""
    try:
        supabase.table("email_logs").insert({
            "po_number": po_number,
            "subject": subject,
            "draft_body": body,
            "recipient_email": vendor_email,
            "status": "draft",
            "trigger_reason": "eta_missing",
            "email_type": "follow_up_eta_missing",
            "sender_role": "system",
            "direction": "outgoing"
        }).execute()
        print(f"📩 ETA request draft created for PO: {po_number}")
        return True
    except Exception as e:
        print(f"❌ Error creating ETA request draft for PO {po_number}: {e}")
        return False

def generate_eta_reconfirmation_draft(po, vendor_name, vendor_email, thread_id=None):
    po_number = po["po_number"]
    eta = po["eta"]
    
    subject = f"Re: PO {po_number} - ETA Reconfirmation"
    body = f"""Dear {vendor_name},

We are writing to reconfirm the ETA for PO {po_number}.
According to our records, the current ETA is {eta}.

Please let us know if there are any changes to this delivery date.

Thank you for your cooperation.

Best regards,
{SENDER_NAME}
Procurement Team"""

    # draft 저장 시 thread_id도 함께 저장
    supabase.table("email_logs").insert({
        "po_number": po["po_number"],
        "recipient_email": vendor_email,
        "subject": subject,
        "draft_body": body,
        "status": "draft",
        "email_type": "follow_up_eta_present",
        "thread_id": thread_id
    }).execute()

    print(f"[✅ DRAFT] Created ETA reconfirmation draft for PO {po_number}")

def send_follow_up_emails():
    print("🚀 Starting follow-up process...")

    # --- Generate ETA Request Emails ---
    print("\n📬 [Phase A] Generating emails for POs with vendor reply but no ETA...")
    eta_missing_replied_pos = get_pos_with_vendor_reply_but_no_eta()
    for po in eta_missing_replied_pos:
        vendor_data = po["request_form_id"]["vendor_id"]
        vendor_name = vendor_data.get("name") or get_vendor_name(vendor_data["id"])
        vendor_email = vendor_data.get("email")
        if vendor_email:
            generate_eta_request_draft(po, vendor_name, vendor_email)
        else:
            print(f"⚠️ Skipping PO {po['po_number']}: Vendor email is missing")

    # --- Generate ETA Reminder Emails ---
    print("\n📬 [Phase B] Generating emails for POs needing ETA reconfirmation...")
    eta_confirmed_pos = get_eta_reconfirmation_pos()
    for po in eta_confirmed_pos:
        vendor_data = po["request_form_id"]["vendor_id"]
        vendor_name = vendor_data.get("name") or get_vendor_name(vendor_data["id"])
        vendor_email = vendor_data.get("email")
        if vendor_email:
            generate_eta_reconfirmation_draft(po, vendor_name, vendor_email)
        else:
            print(f"⚠️ Skipping PO {po['po_number']}: Vendor email is missing")

    print("\n🎉 Follow-up process complete!") 