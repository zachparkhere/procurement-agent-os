import os
from supabase import create_client
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Connect to Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Step 1: Read all email_logs with no embedding
# Using is_null() instead of eq(None) for proper SQL NULL check
rows = supabase.table("email_logs").select("id, subject").is_("embedding", "null").execute()

if not rows.data:
    print("✅ No rows without embeddings found.")
    exit()

print(f"🔍 Found {len(rows.data)} rows to embed")

# Step 2: Loop through each subject and embed
for row in rows.data:
    subject = row["subject"]
    if not subject:
        continue

    response = client.embeddings.create(
        input=subject,
        model="text-embedding-ada-002"
    )
    embedding = response.data[0].embedding

    # Step 3: Update back into Supabase
    supabase.table("email_logs").update({"embedding": embedding}).eq("id", row["id"]).execute()
    print(f"✅ Embedded email_log id={row['id']}")

print("✅ All done.") 