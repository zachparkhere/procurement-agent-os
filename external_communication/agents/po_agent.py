import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from po_issued_vendor_email import fetch_po_context, create_and_save_draft

async def handle_po_message(payload: dict):
    try:
        po_id = payload.get("po_id")
        if not po_id:
            print("[⚠️ PO AGENT] No po_id provided in payload.")
            return

        print(f"[📦 PO AGENT] Fetching context for PO ID: {po_id}")
        context = fetch_po_context(po_id)

        print(f"[✏️ PO AGENT] Generating and saving email draft...")
        draft = create_and_save_draft(context)

        print(f"[✅ PO AGENT] Draft created for PO: {context['po']['po_number']}")
        print(f"Subject: {draft['subject']}")
        print(f"Body:\n{draft['body']}")

    except Exception as e:
        print(f"[❌ PO AGENT ERROR] {e}")