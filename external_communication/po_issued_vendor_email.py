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
        .eq("update_status", "issued") \
        .eq("human_confirmed", True) \
        .is_("submitted_at", "null") \
        .execute().data

    if not pending_pos:
        print("✅ No pending POs to email.")
        return None

    # Step 2: Filter out POs that already have a drafted email
    for po in pending_pos:
        po_id = po["id"]
        existing_draft = supabase.table("email_logs") \
            .select("id") \
            .eq("po_number", po["po_number"]) \
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
    
    # Fetch PO items using po_number
    items = supabase.table("po_items").select("*").eq("po_number", po["po_number"]).execute().data
    
    return {
        "po": po,
        "items": items
    }

# Step 3: Create and save email draft
def create_and_save_draft(context):
    # Step 3-1: Generate email draft
    draft = generate_po_email_draft(context)
    
    # Step 3-2: Save to email_logs
    insert_po_email_draft(supabase, context, draft["body"], context["po"]["po_number"])
    
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