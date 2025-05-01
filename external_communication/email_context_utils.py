from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_last_conversation_by_request_form(request_form_id, n=3):
    """Get the last n sent/received emails with non-null body for a request form, ordered by created_at desc."""
    response = supabase.table("email_logs") \
        .select("subject, body, sender_role, direction, created_at, status") \
        .eq("request_form_id", request_form_id) \
        .in_("status", ["sent", "received"]) \
        .filter("body", "not.is", "null") \
        .order("created_at", desc=True) \
        .limit(n) \
        .execute()
    return response.data or [] 