from api.supabase import supabase

def fetch_po_items(po_number: str, user_id=None):
    query = (
        supabase
        .table("po_items")
        .select("*")
        .eq("po_number", po_number)
        .order("item_no", desc=False)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()
    return result.data if result.data else []
