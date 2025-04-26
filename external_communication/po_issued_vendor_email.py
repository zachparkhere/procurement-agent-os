# po_issued_vendor_email.py

import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
from po_templates.generate_po_draft import generate_po_email_draft
from utils.insert_draft import insert_po_email_draft

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_po_to_email():
    # Step 1: Find all POs that are confirmed and not sent yet
    pending_pos = supabase.table("purchase_orders") \
        .select("*") \
        .eq("human_confirmed", True) \
        .is_("email_sent_to_vendor_at", "null") \
        .execute().data

    if not pending_pos:
        print("✅ No pending POs to email.")
        return None

    # Step 2: Filter out POs that already have a drafted email
    for po in pending_pos:
        po_id = po["id"]
        existing_draft = supabase.table("email_logs") \
            .select("id") \
            .eq("request_form_id", po["request_form_id"]) \
            .eq("status", "draft") \
            .eq("sender_role", "system") \
            .execute().data

        if not existing_draft:
            return po  # only return first PO without draft

    print("✅ All pending POs already have a draft.")
    return None

# Step 2: Fetch all related data for context
def fetch_po_context(po_id):
    # Fetch PO itself
    po = supabase.table("purchase_orders").select("*").eq("id", po_id).single().execute().data

    # Fetch request_form
    form = supabase.table("request_form").select("*").eq("id", po["request_form_id"]).single().execute().data

    # Fetch vendor
    vendor = supabase.table("vendors").select("*").eq("id", form["vendor_id"]).single().execute().data

    # Fetch requester
    requester = supabase.table("users").select("*").eq("id", form["requester_id"]).single().execute().data

    # Fetch request_items
    items = supabase.table("request_items").select("*").eq("request_form_id", form["id"]).execute().data

    return {
        "po": po,
        "form": form,
        "vendor": vendor,
        "requester": requester,
        "items": items
    }

# Step 3: Create and save email draft
def create_and_save_draft(context):
    # Step 3-1: Generate email draft
    draft = generate_po_email_draft(context)
    
    # Step 3-2: Save to email_logs
    insert_po_email_draft(supabase, context, draft["body"])
    
    return draft

# Test
po = fetch_po_to_email()
if po:
    print("📦 Fetched PO:", po)
    context = fetch_po_context(po["id"])
    print("📦 Full PO Context:")
    print(context)
    
    # Create and save draft
    draft = create_and_save_draft(context)
    print("\n📧 Generated Email Draft:")
    print("Subject:", draft["subject"])
    print("\nBody:")
    print(draft["body"]) 