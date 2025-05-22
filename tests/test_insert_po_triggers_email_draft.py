import os
import sys
import time
import subprocess
from datetime import datetime

# Fix import path to vendor_email_logger_agent/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_PATH = os.path.join(BASE_DIR, "vendor_email_logger_agent")
if AGENT_PATH not in sys.path:
    sys.path.append(AGENT_PATH)

# Now safe to import
from config import supabase

def create_test_data():
    # Create test vendor
    vendor_response = supabase.table("vendors").insert({
        "name": "Test Vendor",
        "email": "mario904@snu.ac.kr"
    }).execute()
    vendor_id = vendor_response.data[0]["id"]

    # Create test user
    user_response = supabase.table("users").insert({
        "name": "Test User",
        "email": "test.user@example.com"
    }).execute()
    user_id = user_response.data[0]["id"]

    # Create test request form
    form_response = supabase.table("request_form").insert({
        "vendor_id": vendor_id,
        "requester_id": user_id,
        "status": "approved"
    }).execute()
    form_id = form_response.data[0]["id"]

    # Create test request items
    supabase.table("request_items").insert({
        "request_form_id": form_id,
        "item_name": "Test Item",
        "quantity": 1,
        "unit_price": 100,
        "currency": "USD"
    }).execute()

    return form_id

def clean_test_data():
    # Clean up all test data
    supabase.table("po_items").delete().neq("po_number", "").execute()
    supabase.table("purchase_orders").delete().neq("po_number", "").execute()
    supabase.table("email_logs").delete().neq("po_number", "").execute()

def insert_test_po(po_number):
    # Delete existing test data
    supabase.table("po_items").delete().eq("po_number", po_number).execute()
    supabase.table("purchase_orders").delete().eq("po_number", po_number).execute()
    
    # Insert new test PO
    supabase.table("purchase_orders").insert({
        "po_number": po_number,
        "issue_date": "2025-05-01",
        "currency": "USD",
        "human_confirmed": True,
        "vendor_email": "mario904@snu.ac.kr",
        "vendor_name": "Test Vendor",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }).execute()

    # Insert test PO items
    supabase.table("po_items").insert([
        {
            "po_number": po_number,
            "item_no": "LAP001",
            "description": "Dell XPS 13 Laptop, 16GB RAM, 512GB SSD",
            "quantity": 2,
            "unit_price": 1299.99,
            "subtotal": 2599.98,
            "tax": 260.00,
            "shipping_fee": 50.00,
            "other_fee": 25.00,
            "total": 2934.98,
            "category": "Electronics"
        },
        {
            "po_number": po_number,
            "item_no": "MON002",
            "description": "Dell 27-inch 4K Monitor, USB-C Hub",
            "quantity": 2,
            "unit_price": 499.99,
            "subtotal": 999.98,
            "tax": 100.00,
            "shipping_fee": 75.00,
            "other_fee": 0.00,
            "total": 1174.98,
            "category": "Computer Accessories"
        }
    ]).execute()

def test_po_triggers_draft_generation():
    clean_test_data()  # Clean up before test
    po_number = f"PO-TEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    insert_test_po(po_number)

    # Step 2: Run the actual poller script
    poller_path = "C:\\Users\\USER\\po_agent_os\\external_communication\\po_issued_vendor_email.py"
    subprocess.run(["python", poller_path], check=True)

    time.sleep(2)

    # Step 3: Check if draft email was created
    response = supabase.table("email_logs").select("*").eq("po_number", po_number).eq("status", "draft").limit(1).execute()
    assert len(response.data) == 1

    print(f"✅ Draft created for {po_number}")

if __name__ == "__main__":
    test_po_triggers_draft_generation() 