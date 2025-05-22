from streamlit_ui.api.supabase import supabase

def fetch_user_pos(user_id: str):
    return (
        supabase
        .table("purchase_orders")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
