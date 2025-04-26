def insert_po_email_draft(supabase, po_context, draft_body):
    po = po_context["po"]
    vendor = po_context["vendor"]
    form = po_context["form"]

    result = supabase.table("email_logs").insert({
        "request_form_id": form["id"],
        "sender_role": "system",
        "direction": "outgoing",
        "sent_at": None,
        "subject": f"PO Confirmation - {po['po_number']}",
        "draft_body": draft_body,
        "recipient_email": vendor["email"],
        "status": "draft",
        "trigger_reason": "po_issued",
        "summary": "Initial PO draft created for vendor confirmation."
    }).execute()

    print(f"📩 Draft inserted into email_logs for PO: {po['po_number']}") 