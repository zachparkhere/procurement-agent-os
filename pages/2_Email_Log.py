# 이메일 로그 조회
email_res = supabase.table("email_logs").select(
    "id, message_id, thread_id, po_number, sender_email, recipient_email, subject, body, created_at, direction, read, sent_at, received_at"
).or_(
    f"user_id.eq.{user_id}," +
    f"sender_email.ilike.%{user_email}%," +
    f"recipient_email.ilike.%{user_email}%"
).order("created_at", desc=True).execute()

# 이메일 로그 데이터프레임 생성
email_logs_df = pd.DataFrame(email_res.data) 