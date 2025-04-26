import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI
from textwrap import wrap

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize clients
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)


def generate_embedding(text: str):
    if not text:
        return None
    try:
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ Embedding error: {e}")
        return None


def embed_purchase_orders():
    print("📦 Embedding purchase_orders...")

    try:
        po_rows = supabase.table("purchase_orders") \
            .select("id, po_number, vendor_name, delivery_date, currency, shipping_terms, payment_terms, embedding") \
            .is_("embedding", "null") \
            .execute().data
    except Exception as e:
        print(f"❌ Error fetching purchase orders: {e}")
        return

    for po in po_rows:
        po_id = po.get("id")
        if not po_id:
            print("⚠️ Skipping PO row: Missing ID.")
            continue

        try:
            items_response = supabase.table("po_items") \
                .select("description, quantity, unit_price") \
                .eq("purchase_order_id", po_id) \
                .execute()
            items = items_response.data
        except Exception as e:
            print(f"❌ Error fetching items for PO ID {po_id}: {e}")
            continue # Skip this PO if items can't be fetched

        item_lines = []
        for item in items:
            description = item.get("description", "N/A")
            quantity = item.get("quantity", 0)
            unit_price = item.get("unit_price", 0.0)
            item_lines.append(f"- {description} (Quantity: {quantity}, Unit Price: {unit_price})")
        item_text = "\n".join(item_lines) if item_lines else "No items listed."

        content = f"""
        Purchase Order Number: {po.get('po_number')}
        Vendor Name: {po.get('vendor_name')}
        Delivery Date: {po.get('delivery_date')}
        Currency: {po.get('currency')}
        Shipping Terms: {po.get('shipping_terms')}
        Payment Terms: {po.get('payment_terms')}
        Ordered Items:
        {item_text}
        """.strip()

        embedding = generate_embedding(content)
        if embedding:
            try:
                supabase.table("purchase_orders") \
                    .update({"embedding": embedding}) \
                    .eq("id", po_id).execute()
                print(f"✅ Embedded PO ID: {po_id}")
            except Exception as e:
                print(f"❌ Error updating embedding for PO ID {po_id}: {e}")
        else:
            print(f"⚠️ Skipped PO ID: {po_id} due to embedding failure.")


def embed_request_forms():
    print("📄 Embedding request_form...")

    try:
        rows = supabase.table("request_form") \
            .select("id, request_id, request_date, due_date, category, approval_status, total_amount, priority, notes, requester_comm_status, vendor_comm_status, embedding") \
            .is_("embedding", "null") \
            .execute().data
    except Exception as e:
        print(f"❌ Error fetching request forms: {e}")
        return

    for row in rows:
        row_id = row.get("id") # Get the ID safely
        if not row_id:
            print("⚠️ Skipping request form row: Missing ID.")
            continue
            
        content = f"""
        Request ID: {row.get('request_id')}
        Request Date: {row.get('request_date')}
        Due Date: {row.get('due_date')}
        Category: {row.get('category')}
        Approval Status: {row.get('approval_status')}
        Priority: {row.get('priority')}
        Total Amount: {row.get('total_amount')}
        Requester Communication: {row.get('requester_comm_status', '')}
        Vendor Communication: {row.get('vendor_comm_status', '')}
        Notes: {row.get('notes', '')}
        """.strip() # Use strip() for cleaner content

        embedding = generate_embedding(content)
        if embedding:
            try:
                supabase.table("request_form") \
                    .update({"embedding": embedding}) \
                    .eq("id", row_id).execute()
                print(f"✅ Embedded request_form ID: {row_id}")
            except Exception as e:
                print(f"❌ Error updating embedding for request_form ID {row_id}: {e}")
        else:
            print(f"⚠️ Skipped request_form ID: {row_id} due to embedding failure.")


def embed_email_logs():
    print("📧 Embedding incoming email_logs...")

    MAX_CHARS = 4000  # roughly ~1000 tokens

    try:
        print("🔍 Fetching unembedded incoming email_logs...")
        response = supabase.table("email_logs") \
            .select("id, subject, body, request_form_id, created_at, sender_role, direction") \
            .or_("direction.eq.inbound,direction.eq.incoming") \
            .is_("embedding", "null") \
            .execute()
        rows = response.data
    except Exception as e:
        print(f"❌ Error fetching email logs: {e}")
        return

    for row in rows:
        row_id = row.get("id") # Get ID safely
        if not row_id:
            print("⚠️ Skipping email log row: Missing ID.")
            continue

        subject = row.get("subject", "") or ""
        body = row.get("body", "") or ""
        full_text = f"Subject: {subject}\n\nBody:\n{body.strip()}"

        if not full_text.strip():
            print(f"⚠️ Skipping empty content (ID: {row_id})")
            continue

        chunks = wrap(full_text, MAX_CHARS)
        chunk_to_embed = chunks[0]  # Just use the first chunk for now

        try:
            embedding = generate_embedding(chunk_to_embed)
        except Exception as e:
            print(f"❌ Failed to embed email_log ID: {row_id}, error: {e}")
            continue
            
        if not embedding:
            print(f"⚠️ Skipped email_log ID: {row_id} due to embedding generation failure.")
            continue

        try:
            supabase.table("email_logs").update({
                "embedding": embedding
            }).eq("id", row_id).execute()
            print(f"✅ Embedded email_log ID: {row_id} (chunked length: {len(chunk_to_embed)} chars)")
        except Exception as e:
            print(f"❌ Error updating embedding for email_log ID {row_id}: {e}")
            continue
            
        if row.get("sender_role") == "vendor" and row.get("request_form_id") and body:
            print(f"🔄 Analyzing vendor reply for ETA status (ID: {row_id})")
            try:
                created_at_str = row.get("created_at")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", ""))
                    
                    eta_status = infer_eta_status_from_reply(body, created_at)
                    if eta_status:
                        supabase.table("purchase_orders") \
                            .update({"inferred_eta_status": eta_status}) \
                            .eq("request_form_id", row["request_form_id"]) \
                            .execute()
                        print(f"✅ Updated PO with ETA status (request_form_id: {row['request_form_id']}) based on email {row_id}")
                    else:
                        print(f"ℹ️ No ETA status could be inferred from the reply (ID: {row_id})")
                else:
                     print(f"⚠️ Cannot infer ETA for email {row_id}: Missing created_at.")
            except ImportError:
                 print(f"❌ Cannot infer ETA: function 'infer_eta_status_from_reply' is not defined or imported.")
            except Exception as e:
                 print(f"❌ Error during ETA inference for email {row_id}: {e}")


if __name__ == "__main__":
    embed_purchase_orders()
    embed_request_forms()
    embed_email_logs()
    print("🎉 Structured embedding complete!") 