import os
from datetime import datetime
from dotenv import load_dotenv
from po_agent_os.supabase_client import supabase
from openai import OpenAI

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = supabase
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_item_summary(item: dict) -> str:
    return (
        f"Item No: {item.get('item_no', 'N/A')}, Description: {item.get('description', 'N/A')}, "
        f"Quantity: {item.get('quantity', 'N/A')}, Unit Price: ${item.get('unit_price', 'N/A')}, "
        f"Subtotal: ${item.get('subtotal', 'N/A')}, Tax: ${item.get('tax', 'N/A')}, "
        f"Shipping Fee: ${item.get('shipping_fee', 'N/A')}, Other Fee: ${item.get('other_fee', 'N/A')}, "
        f"Total: ${item.get('total', 'N/A')}, Category: {item.get('category', 'N/A')}"
    )

def embed_po_item_rows():
    print("📦 Embedding po_items rows...")
    response = supabase.table("po_items").select("*").limit(100).execute()
    rows = response.data

    for item in rows:
        record_id = item["id"]
        record_ref = f"po_items:{record_id}"
        content = generate_item_summary(item)

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
                print(f"🔄 Updated embedding for PO Item ID {record_id}")
            else:
                # Insert new record
                supabase.table("schema_embeddings").insert({
                    "table_name": "po_items",
                    "field_name": "__row__",
                    "record_id": record_id,
                    "record_ref": record_ref,
                    "content": content,
                    "embedding": embedding,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                print(f"✅ Created embedding for PO Item ID {record_id}")

        except Exception as e:
            print(f"❌ Error embedding PO Item ID {record_id}: {e}")

if __name__ == "__main__":
    embed_po_item_rows() 