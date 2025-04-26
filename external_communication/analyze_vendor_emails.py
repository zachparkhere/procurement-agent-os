import os
import json
from dotenv import load_dotenv
from supabase import create_client
from llm_extract_info_needs import llm_extract_info_needs

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def analyze_unprocessed_vendor_emails():
    print("🔍 Fetching unprocessed vendor emails...")

    response = supabase.table("email_logs") \
        .select("id, subject, draft_body, direction, sender_role") \
        .eq("direction", "inbound") \
        .eq("sender_role", "vendor") \
        .eq("status", "received") \
        .is_("embedding", "not.null") \
        .is_("llm_analysis_result", "null") \
        .limit(10) \
        .execute()

    rows = response.data
    print(f"📬 {len(rows)} emails to analyze")

    for row in rows:
        email_id = row["id"]
        subject = row.get("subject") or "(no subject)"
        body = row.get("draft_body") or ""

        try:
            result_json_str = llm_extract_info_needs(subject, body)
            result = json.loads(result_json_str)

            supabase.table("email_logs").update({
                "llm_analysis_result": result_json_str,
                "llm_intent": result.get("intent"),
                "suggested_reply_type": result.get("suggested_reply_type"),
                "reply_needed": result.get("reply_needed")
            }).eq("id", email_id).execute()

            print(f"✅ Email ID {email_id} analyzed and updated")

        except Exception as e:
            print(f"❌ Error processing email ID {email_id}: {e}")

if __name__ == "__main__":
    analyze_unprocessed_vendor_emails() 