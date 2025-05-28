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

def analyze_po_status(po_number: str, new_email_body: str = None) -> str:
    """Analyzes email history and determines the current status of a PO"""
    try:
        # 새로운 이메일이 있을 때만 LLM 호출
        if new_email_body:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Email history for PO {po_number}:\n{new_email_body}"}
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
            
        return None  # 새로운 이메일이 없으면 LLM 호출하지 않음
        
    except Exception as e:
        print(f"[❌ PO Status Error] Failed to update status for PO {po_number}: {e}")
        return None

async def handle_new_email(po_number: str, email_body: str):
    """새로운 이메일이 들어왔을 때만 상태 업데이트"""
    status = analyze_po_status(po_number, email_body)
    if status:
        print(f"[✅ PO Status] Updated status for PO {po_number} to {status}")
    return status

# 기존의 update_all_po_statuses 함수는 제거 (더 이상 필요하지 않음) 