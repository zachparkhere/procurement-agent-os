import os
import json
from dotenv import load_dotenv
from po_agent_os.supabase_client import supabase
from po_agent_os.llm_extract_info_needs import enrich_email_with_llm

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = supabase

def strip_quoted_text(email_body: str) -> str:
    """
    Remove quoted previous emails (lines starting with '>' or common reply markers).
    """
    lines = email_body.splitlines()
    clean_lines = []
    for line in lines:
        if line.strip().startswith(">"):
            continue
        if line.strip().lower().startswith("on ") and "wrote:" in line.lower():
            break
        clean_lines.append(line)
    return "\n".join(clean_lines).strip()

def analyze_email_content(subject: str, body: str, po_number: str = None) -> dict:
    """
    Lightweight callable used by agents to analyze a single email via LLM.
    Applies body cleanup to avoid misclassification.
    """
    cleaned_body = strip_quoted_text(body)
    if not cleaned_body or len(cleaned_body) < 10:
        print("⚠️ Body seems empty or too short after cleanup.")
    result_json_str = enrich_email_with_llm(subject, cleaned_body)
    return json.loads(result_json_str)

def analyze_unprocessed_vendor_emails():
    print("🔍 Fetching unprocessed vendor emails...")

    response = supabase.table("email_logs") \
        .select("id, subject, body, direction, sender_role") \
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
        body = row.get("body") or ""

        try:
            result = analyze_email_content(subject, body)

            supabase.table("email_logs").update({
                "llm_analysis_result": json.dumps(result),
                "llm_intent": result.get("intent"),
                "suggested_reply_type": result.get("suggested_reply_type"),
                "reply_needed": result.get("reply_needed")
            }).eq("id", email_id).execute()

            print(f"✅ Email ID {email_id} analyzed and updated")

        except Exception as e:
            print(f"❌ Error processing email ID {email_id}: {e}")

if __name__ == "__main__":
    analyze_unprocessed_vendor_emails()
