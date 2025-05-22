from streamlit_ui.api.supabase import supabase

def fetch_po_items(po_number: str):
    return (
        supabase
        .table("po_items")
        .select("*")
        .eq("po_number", po_number)
        .order("item_no")
        .execute()
        .data
    )
