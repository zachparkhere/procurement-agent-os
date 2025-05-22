import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# PO auto-email is disabled in MVP phase
# from po_issued_vendor_email import fetch_po_context, create_and_save_draft

async def handle_po_message(payload: dict):
    try:
        po_id = payload.get("po_id")
        if not po_id:
            print("[⚠️ PO AGENT] No po_id provided in payload.")
            return

        print("[ℹ️ PO AGENT] PO auto-email is disabled in MVP phase")
        return

    except Exception as e:
        print(f"[❌ PO AGENT ERROR] {e}")