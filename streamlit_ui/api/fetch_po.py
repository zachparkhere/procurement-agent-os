from api.supabase import supabase

def get_po_list(user_id=None):
    query = (
        supabase
        .table("purchase_orders")
        .select("po_id, po_number, vendor_id, created_at, expected_delivery_date, submitted_at, ai_status, flag, status, comments, vendors(name)")
        .order("created_at", desc=True)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    return response.data
