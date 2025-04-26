import os
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_po_summary(po: dict, items: list) -> str:
    po_number = po.get("po_number", "[Unknown PO number]")
    vendor = po.get("vendor_name") or po.get("vendor_email") or "Unknown Vendor"
    expected_delivery_date = po.get("expected_delivery_date") or "Expected delivery date not set"
    eta = po.get("eta") or "ETA not provided"
    confirmed_delivery_date = po.get("confirmed_delivery_date") or "Delivery date not confirmed"
    status = po.get("status") or "No status info"

    # Item summary and total
    item_list = []
    total_cost = 0.0
    for item in items:
        desc = item.get("description", "Unnamed item")
        qty = item.get("quantity", "?")
        try:
            qty = int(qty)
        except:
            qty = "?"
        item_list.append(f"{qty}x {desc}")
        try:
            total_cost += float(item.get("total", 0))
        except:
            pass

    item_summary = ", ".join(item_list) if item_list else "No items listed"
    total_cost_str = f"Estimated total: ${round(total_cost):,}" if total_cost > 0 else "Total not available"

    return (
        f"Purchase Order {po_number} is issued to vendor {vendor}. "
        f"Our expected delivery date is {expected_delivery_date}. "
        f"Vendor's estimated delivery date (ETA) is {eta}. "
        f"Vendor's confirmed delivery date is {confirmed_delivery_date}. "
        f"Items ordered: {item_summary}. {total_cost_str}. "
        f"Status: {status}."
    )

def embed_purchase_order_rows():
    print("📦 Embedding purchase_orders rows (row-level with item + total)...")
    response = supabase.table("purchase_orders").select("*").limit(50).execute()
    rows = response.data

    for po in rows:
        record_id = po["id"]
        record_ref = f"purchase_orders:{record_id}"

        try:
            items_response = supabase.table("po_items").select("*").eq("purchase_order_id", record_id).execute()
            items = items_response.data
        except Exception as e:
            print(f"⚠️ Could not fetch items for PO ID {record_id}: {e}")
            items = []

        content = generate_po_summary(po, items)

        try:
            embedding = openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=content
            ).data[0].embedding

            # Check if record_ref already exists
            existing = supabase.table("schema_embeddings") \
                .select("id") \
                .eq("record_ref", record_ref) \
                .execute()

            if existing.data:
                # Update existing record
                supabase.table("schema_embeddings") \
                    .update({
                        "content": content,
                        "embedding": embedding,
                        "updated_at": datetime.utcnow().isoformat()
                    }) \
                    .eq("record_ref", record_ref) \
                    .execute()
                print(f"🔄 Updated embedding for PO ID {record_id}")
            else:
                # Insert new record
                supabase.table("schema_embeddings").insert({
                    "table_name": "purchase_orders",
                    "field_name": "__row__",
                    "record_id": record_id,
                    "record_ref": record_ref,
                    "content": content,
                    "embedding": embedding,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                print(f"✅ Created embedding for PO ID {record_id}")

        except Exception as e:
            print(f"❌ Error embedding PO ID {record_id}: {e}")

if __name__ == "__main__":
    embed_purchase_order_rows() 