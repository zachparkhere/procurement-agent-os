import os
import sys
from datetime import datetime
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILS_DIR = os.path.join(BASE_DIR, "utils")
sys.path.append(UTILS_DIR)
sys.path.append(BASE_DIR)

from config import supabase
from utils.email_thread_utils import get_latest_thread_id_for_po
from follow_up_vendor_email import generate_eta_reconfirmation_draft

def get_last_reminder_sent_at_from_tracking(po_number: str) -> Optional[datetime]:
    response = supabase.table("po_tracking").select("last_reminder_sent_at") \
        .eq("po_number", po_number) \
        .limit(1) \
        .execute()
    if response.data and response.data[0]["last_reminder_sent_at"]:
        return datetime.fromisoformat(response.data[0]["last_reminder_sent_at"])
    return None

def process_single_eta_followup(po_number: str):
    try:
        po_resp = supabase.table("purchase_orders").select("*").eq("po_number", po_number).limit(1).execute()
        if not po_resp.data:
            print(f"[❌ FOLLOW-UP AGENT] No PO found for {po_number}")
            return
        po = po_resp.data[0]

        vendor_email = po.get("vendor_email")
        vendor_name = po.get("vendor_name")
        if not vendor_email:
            print(f"[⚠️ FOLLOW-UP AGENT] No vendor email for PO: {po_number}")
            return

        eta = po.get("eta")
        if eta is None:
            print(f"[ℹ️ FOLLOW-UP AGENT] ETA is missing for PO: {po_number} — skipping.")
            return

        now = datetime.utcnow()
        last_sent_at = get_last_reminder_sent_at_from_tracking(po_number)
        if last_sent_at is None or (now - last_sent_at).days >= 2:
            thread_id = get_latest_thread_id_for_po(po_number)
            generate_eta_reconfirmation_draft(po, vendor_name, vendor_email, thread_id=thread_id)
            supabase.table("po_tracking").update({"last_reminder_sent_at": now.isoformat()}).eq("po_number", po_number).execute()
            print(f"[📨 FOLLOW-UP AGENT] Generated ETA reconfirmation draft for PO {po_number}")
        else:
            print(f"[ℹ️ FOLLOW-UP AGENT] Skipped PO {po_number} - recent reminder already sent")
    except Exception as e:
        print(f"[❌ FOLLOW-UP AGENT ERROR] {e}")

async def handle_followup_message(payload: dict = None):
    if payload and payload.get("po_number"):
        po_number = payload["po_number"]
        print(f"[🔎 FOLLOW-UP AGENT] Processing PO {po_number} for ETA follow-up...")
        process_single_eta_followup(po_number)
    else:
        print("[🔁 FOLLOW-UP AGENT] Checking POs for ETA follow-ups (full scan)...")
        from follow_up_vendor_email import process_all_eta_followups
        process_all_eta_followups()
