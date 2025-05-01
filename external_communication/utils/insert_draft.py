def insert_po_email_draft(supabase, po_context, draft_body, po_number):
    po = po_context["po"]

    result = supabase.table("email_logs").insert({
        "sender_role": "admin",
        "direction": "outgoing",
        "sent_at": None,
        "subject": f"PO Confirmation - {po['po_number']}",
        "draft_body": draft_body,
        "recipient_email": po["vendor_email"],
        "status": "draft",
        "trigger_reason": "po_issued",
        "summary": "Initial PO draft created for vendor confirmation.",
        "po_number": po_number,
    }).execute()

    print(f"📩 Draft inserted into email_logs for PO: {po['po_number']}") 