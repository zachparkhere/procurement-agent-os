def generate_po_email_draft(po_context: dict) -> dict:
    po = po_context["po"]
    items = po_context["items"]

    po_number = po["po_number"]
    vendor_name = po["vendor_name"]
    issue_date = po["issue_date"]
    currency = po["currency"]

    # Calculate totals
    total_amount = sum(item["total"] for item in items)
    
    # Generate items table
    items_lines = []
    for item in items:
        items_lines.append(f"- {item['item_no']}: {item['description']}")
        items_lines.append(f"  Quantity: {item['quantity']}, Unit Price: {currency} {item['unit_price']:.2f}, Total: {currency} {item['total']:.2f}")
    items_table = "\n".join(items_lines)

    subject = f"Purchase Order {po_number} from Our Company"

    body = f"""Dear {vendor_name},

We are pleased to submit our Purchase Order {po_number} dated {issue_date}.

Order Details:
{items_table}

Total Order Amount: {currency} {total_amount:.2f}

Please review the order details and confirm receipt of this purchase order. If you have any questions or concerns, please don't hesitate to contact us.

Best regards,
Procurement Team"""

    return {
        "subject": subject,
        "body": body
    } 