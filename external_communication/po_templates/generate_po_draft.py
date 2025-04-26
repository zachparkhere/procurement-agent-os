def generate_po_email_draft(po_context: dict) -> dict:
    po = po_context["po"]
    vendor = po_context["vendor"]
    requester = po_context["requester"]

    po_number = po["po_number"]
    delivery_date = po["delivery_date"]
    vendor_name = vendor["name"]
    requester_name = requester["name"]

    subject = f"Purchase Order {po_number}: Please confirm delivery"

    body = f"""Dear {vendor_name},

Please find the Purchase Order {po_number} issued by our team.

📅 Delivery date: {delivery_date}

Please confirm the delivery schedule at your earliest convenience.

Best regards,  
{requester_name}  
Procurement Team"""

    return {
        "subject": subject,
        "body": body
    } 