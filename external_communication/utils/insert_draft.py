def insert_po_email_draft(supabase, po_context, draft_body, po_number):
    """
    This function is disabled in MVP phase.
    PO auto-email functionality will be implemented in future versions.
    """
    print("ℹ️ PO auto-email is disabled in MVP phase")
    return None
    
    po = po_context["po"]
    
    # llm_draft에 초안 정보 저장
    supabase.table("llm_draft").insert({
        "email_log_id": po_context["email_log_id"],
        "draft_subject": f"PO Confirmation - {po['po_number']}",
        "recipient_email": po["vendor_email"],
        "draft_body": draft_body,
        "auto_approve": False,
        "llm_analysis_result": None,
        "info_needed_to_reply": None,
        "suggested_reply_type": "po_confirmation",
        "reply_needed": True
    }).execute()
    
    print(f"📩 Draft inserted for PO: {po['po_number']}") 