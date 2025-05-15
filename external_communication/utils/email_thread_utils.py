from config import supabase

def get_latest_thread_id_for_po(po_number: str) -> str | None:
    response = supabase.table("email_logs").select("thread_id") \
        .eq("po_number", po_number) \
        .neq("thread_id", None) \
        .order("sent_at", desc=True) \
        .limit(1) \
        .execute()
    if response.data and response.data[0]["thread_id"]:
        return response.data[0]["thread_id"]
    return None