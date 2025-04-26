# external_communication/send_email.py

import os
from datetime import datetime
from supabase import create_client
from dotenv import load_dotenv

# Load env variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def send_email_and_update(po_id: int, email_subject: str, email_body: str, recipient_email: str):
    # ✅ Step 1: Simulate sending
    print(f"📤 Sending email to {recipient_email}...")
    print(f"Subject: {email_subject}")
    print(f"Body:\n{email_body}")

    # ✅ Step 2: Update DB with send timestamp
    now = datetime.utcnow().isoformat()
    response = supabase.table("purchase_orders").update({
        "email_sent_to_vendor_at": now
    }).eq("id", po_id).execute()

    if response.data:
        print(f"✅ Email sent and DB updated for PO ID: {po_id}")
    else:
        print("❌ Failed to update the DB")

# Example usage (you can later call this from another script)
if __name__ == "__main__":
    # Dummy test
    send_email_and_update(
        po_id=1,
        email_subject="Purchase Order REQ-1001: Please confirm delivery",
        email_body="Dear Vendor,\n\nPlease find the attached PO for your confirmation.\n\nBest regards,\nProcurement Team",
        recipient_email="sales@globalelec.com"
    ) 