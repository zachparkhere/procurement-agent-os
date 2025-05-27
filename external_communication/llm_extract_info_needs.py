import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import json
from openai import OpenAI
from dotenv import load_dotenv
from po_agent_os.supabase_client import supabase
from datetime import datetime, timedelta
import dateparser

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a procurement email analyst. 
Your job is to extract structured fields from vendor emails that relate to purchase orders.
"""

USER_PROMPT_TEMPLATE = """
EMAIL:
Subject: {subject}
Body:
{body}

---
Return in JSON format:
{
  "delivery_date": "YYYY-MM-DD or null",
  "intent": "confirm | delay | eta_proposal | no_info",
  "reply_needed": true | false,
  "suggested_reply_type": "standard | acknowledgement | no_reply | follow_up"
}
"""

def enrich_email_with_llm(subject: str, body: str, po_number: str = None) -> dict:
    prompt = USER_PROMPT_TEMPLATE.format(subject=subject, body=body)
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        # delivery_date 필드가 없거나 잘못된 형식인 경우 None으로 설정
        if "delivery_date" not in parsed or not isinstance(parsed["delivery_date"], (str, type(None))):
            parsed["delivery_date"] = None
        elif parsed["delivery_date"] == "null":
            parsed["delivery_date"] = None
            
    except Exception as e:
        print("❌ LLM parsing failed:", e)
        parsed = {
            "delivery_date": None,
            "intent": "no_info",
            "reply_needed": False,
            "suggested_reply_type": "no_reply"
        }

    # Save full raw result as string
    parsed["llm_analysis_result"] = json.dumps(parsed)
    parsed["llm_intent"] = parsed.get("intent", "")
    parsed["reply_needed"] = parsed.get("reply_needed", False)
    parsed["suggested_reply_type"] = parsed.get("suggested_reply_type", "no_reply")
    parsed["parsed_delivery_date"] = parsed.get("delivery_date")

    # Optionally update PO if delivery date present
    if po_number and parsed["parsed_delivery_date"]:
        intent = parsed.get("intent", "")
        delivery_date = parsed["parsed_delivery_date"]

        # Fetch current ETA if needed
        current_po = supabase.table("purchase_orders").select("eta").eq("po_number", po_number).limit(1).execute()
        current_eta = None
        if current_po.data:
            current_eta = current_po.data[0].get("eta")

        if intent == "confirm":
            supabase.table("purchase_orders").update({
                "confirmed_delivery_date": delivery_date
            }).eq("po_number", po_number).execute()
        elif intent in ("delay", "eta_proposal"):
            if not current_eta or delivery_date != current_eta:
                supabase.table("purchase_orders").update({
                    "eta": delivery_date
                }).eq("po_number", po_number).execute()

    return parsed 