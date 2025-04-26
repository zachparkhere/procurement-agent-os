# utils/embedding_utils.py

import os
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI
import numpy as np

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize clients
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

# Cosine similarity function
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Embedding generator
def get_embedding(text: str):
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

# Main function to find top-k similar emails
def find_similar_emails(query: str, top_k=3):
    query_embedding = get_embedding(query)

    # Fetch all email_logs with non-null embedding
    response = supabase.table("email_logs") \
        .select("id, subject, embedding") \
        .not_.is_("embedding", "null") \
        .execute()

    if not response.data:
        print("❌ No embedded emails found.")
        return []

    scores = []
    for row in response.data:
        embedding = row["embedding"]
        similarity = cosine_similarity(query_embedding, embedding)
        scores.append({
            "id": row["id"],
            "subject": row["subject"],
            "similarity": similarity
        })

    # Sort by similarity descending
    sorted_results = sorted(scores, key=lambda x: x["similarity"], reverse=True)
    return sorted_results[:top_k]

# Function to find latest vendor reply for a PO
def find_latest_related_reply(po_number: str, top_k=1):
    query = f"RE: PO Confirmation - {po_number}"  # Assuming this is the reply subject pattern
    query_embedding = get_embedding(query)

    # Fetch all email_logs that might be vendor replies
    response = supabase.table("email_logs") \
        .select("id, subject, embedding, sent_at") \
        .not_.is_("embedding", "null") \
        .eq("direction", "incoming") \
        .order("sent_at", desc=True) \
        .execute()

    if not response.data:
        return []

    scores = []
    for row in response.data:
        embedding = row["embedding"]
        similarity = cosine_similarity(query_embedding, embedding)
        scores.append({
            "id": row["id"],
            "subject": row["subject"],
            "similarity": similarity,
            "sent_at": row["sent_at"]
        })

    # Sort by similarity descending
    sorted_results = sorted(scores, key=lambda x: x["similarity"], reverse=True)
    return sorted_results[:top_k] 