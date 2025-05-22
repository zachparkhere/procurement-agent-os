# po_issued_vendor_email.py
# This feature is disabled in MVP phase
# PO auto-email functionality will be implemented in future versions

import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
from po_templates.generate_po_draft import generate_po_email_draft
from utils.insert_draft import insert_po_email_draft

# Load environment
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def fetch_po_to_email():
    print("ℹ️ PO auto-email is disabled in MVP phase")
    return None

# Step 2: Fetch all related data for context
def fetch_po_context(po_id):
    return None

# Step 3: Create and save email draft
def create_and_save_draft(context):
    return None

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