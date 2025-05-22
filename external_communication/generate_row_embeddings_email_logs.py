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

supabase = supabase(SUPABASE_URL, SUPABASE_ANON_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_email_summary(row: dict) -> str:
    subject = row.get("subject")
    body = row.get("body")  # Keep None as is
    sender = row.get("sender_email", "Unknown Sender")
    sent_at = row.get("sent_at")
    direction = row.get("direction")
    role = row.get("sender_role")
    
    # Handle attachments
    has_attachments = row.get("has_attachments", False)
    attachment_names = row.get("attachment_names")
    
    # Build the summary
    summary_parts = [
        f"Email from {sender}",
        f"Role: {role if role else 'None'}",
        f"Direction: {direction if direction else 'None'}",
        f"Sent at: {sent_at if sent_at else 'None'}",
        f"Subject: {subject if subject else 'None'}",
        f"Has attachments: {has_attachments}",
        f"Attachment names: {attachment_names if attachment_names else 'None'}"
    ]
    
    # Add body if exists
    if body:
        # Truncate body if it's too long
        body_text = str(body)[:1000] if len(str(body)) > 1000 else str(body)
        summary_parts.append(f"Body: {body_text}")
    else:
        summary_parts.append("Body: None")

    return "\n".join(summary_parts)

def embed_email_logs():
    print("📨 Embedding email_logs rows...")
    
    # Query only sent or received emails (exclude drafts)
    response = supabase.table("email_logs") \
        .select("*") \
        .neq("status", "draft") \
        .limit(100) \
        .execute()
    
    rows = response.data
    print(f"Found {len(rows)} sent/received emails to embed")

    for row in rows:
        record_id = row["id"]
        record_ref = f"email_logs:{record_id}"
        content = generate_email_summary(row)

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
                print(f"🔄 Updated embedding for email_log ID {record_id}")
            else:
                # Insert new record
                supabase.table("schema_embeddings").insert({
                    "table_name": "email_logs",
                    "field_name": "__row__",
                    "record_id": record_id,
                    "record_ref": record_ref,
                    "content": content,
                    "embedding": embedding,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                print(f"✅ Created embedding for email_log ID {record_id}")

        except Exception as e:
            print(f"❌ Error embedding email_log ID {record_id}: {e}")

if __name__ == "__main__":
    embed_email_logs() 