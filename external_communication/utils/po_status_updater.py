import os
from openai import OpenAI
from dotenv import load_dotenv
from config import supabase

# Load env
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VALID_STATUSES = {
    "issued": "PO has been issued (sent via email or recorded in system)",
    "acknowledged": "Vendor has acknowledged or replied to the PO (OK, received, etc.)",
    "eta_pending": "Vendor has acknowledged but hasn't provided delivery date (ETA)",
    "scheduled": "Vendor has provided ETA (delivery date confirmed)",
    "in_transit": "Vendor has shipped the items (in transit)",
    "delivered": "Items have arrived (receipt confirmed)",
    "partial_delivered": "Only some items have arrived",
    "cancelled": "PO or some items have been cancelled",
    "delayed": "Delivery will be later than ETA or confirmed delay",
    "done": "Delivery complete and internal inspection/processing finished"
}

SYSTEM_PROMPT = f"""You are a procurement status analyzer. Your job is to analyze email history and determine the current status of a purchase order.

You MUST choose EXACTLY ONE of these statuses:
{chr(10).join([f"- {status}: {desc}" for status, desc in VALID_STATUSES.items()])}

Return ONLY the status code that best matches the current situation. Do not add any explanation or additional text."""

def validate_status(status: str) -> str:
    """Validates the status and returns a default value if invalid"""
    status = status.strip().lower()
    if status in VALID_STATUSES:
        return status
    print(f"⚠️ Invalid status '{status}' received from LLM, defaulting to 'issued'")
    return "issued"

def analyze_po_status(po_number: str) -> str:
    """Analyzes email history and determines the current status of a PO"""
    try:
        # 1. Get the latest email log for this PO
        email_log = supabase.table("email_logs") \
            .select("body") \
            .eq("po_number", po_number) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if not email_log.data:
            return "issued"  # Default to issued if no email logs exist
        
        # 2. Analyze status using LLM
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Email history for PO {po_number}:\n{email_log.data[0]['body']}"}
            ],
            temperature=0
        )
        
        # 3. Validate status
        status = validate_status(response.choices[0].message.content)
        
        # 4. Update status
        supabase.table("purchase_orders") \
            .update({"status": status}) \
            .eq("po_number", po_number) \
            .execute()
        
        print(f"[✅ PO Status] Updated status for PO {po_number} to {status}")
        return status
        
    except Exception as e:
        print(f"[❌ PO Status Error] Failed to update status for PO {po_number}: {e}")
        return None

def update_all_po_statuses():
    """Updates status for all POs"""
    try:
        # 1. Get all POs
        pos = supabase.table("purchase_orders") \
            .select("po_number") \
            .execute()
        
        if not pos.data:
            print("[ℹ️ PO Status] No POs found to update")
            return
        
        # 2. Update status for each PO
        for po in pos.data:
            analyze_po_status(po["po_number"])
            
        print(f"[✅ PO Status] Updated status for {len(pos.data)} POs")
        
    except Exception as e:
        print(f"[❌ PO Status Error] Failed to update PO statuses: {e}")

if __name__ == "__main__":
    update_all_po_statuses() 