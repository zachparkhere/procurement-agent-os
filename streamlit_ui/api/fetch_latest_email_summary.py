from api.supabase import supabase

def fetch_latest_email_summary(po_number: str, user_id=None):
    query = (
        supabase
        .table("email_logs")
        .select("summary, created_at")
        .eq("po_number", po_number)  # 실제 필드명에 따라 수정
        .order("created_at", desc=True)
        .limit(1)
    )
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.execute()

    rows = result.data
    if rows and rows[0]["summary"]:
        return rows[0]["summary"], rows[0]["created_at"]
    else:
        return None, None
