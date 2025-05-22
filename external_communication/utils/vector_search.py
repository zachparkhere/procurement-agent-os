# utils/vector_search.py

import os
import ast  # Import ast for literal_eval
from dotenv import load_dotenv
from supabase import create_client
from openai import OpenAI
from numpy import dot
from numpy.linalg import norm
import numpy as np # Import numpy for array conversion
from datetime import datetime
from typing import Optional

# Load env
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)

# Cosine similarity
def cosine_similarity(a, b):
    # Ensure inputs are numpy arrays of floats
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return dot(a, b) / (norm(a) * norm(b))

# Get embedding for PO number or subject
def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

# Search vendor replies related to a PO
def find_latest_vendor_reply(po_number: str, threshold: float = 0.85) -> Optional[dict]:
    query_embedding = get_embedding(po_number)

    result = supabase.table("email_logs") \
        .select("id, subject, embedding, created_at, sender_role") \
        .eq("sender_role", "vendor") \
        .not_.is_("embedding", "null") \
        .order("created_at", desc=True) \
        .execute()

    best_match = None
    best_score = 0

    if not result.data:
        print("ℹ️ No vendor replies with embeddings found.")
        return None

    for row in result.data:
        db_embedding_str = row["embedding"]
        db_embedding = None
        try:
            # Attempt to parse the string representation of the list/vector
            db_embedding = ast.literal_eval(db_embedding_str)
            if not isinstance(db_embedding, list):
                raise ValueError("Parsed data is not a list")
            # Further check if elements are numbers if needed
            
        except (ValueError, SyntaxError, TypeError) as e:
            print(f"⚠️ Error parsing embedding for log ID {row['id']}: {e}. Embedding: {db_embedding_str[:100]}... Skipping.")
            continue
            
        # Check if query_embedding is valid (list of numbers)
        if not isinstance(query_embedding, list) or not all(isinstance(item, (int, float)) for item in query_embedding):
             print(f"⚠️ Invalid query embedding type: {type(query_embedding)}. Skipping comparison.")
             continue # Or handle error appropriately

        similarity = cosine_similarity(query_embedding, db_embedding)
        # print(f"  Comparing with reply ID {row['id']} (Similarity: {similarity:.4f})") # Debugging output
        if similarity > threshold and similarity > best_score:
            best_score = similarity
            best_match = row
            best_match['similarity'] = similarity # Store similarity score

    if best_match:
        print(f"✅ Best matching reply found: ID {best_match['id']} with score {best_match['similarity']:.4f}")
    else:
        print(f"ℹ️ No vendor replies found above similarity threshold {threshold}.")

    return best_match 

def find_last_eta_reply(request_form_id: int) -> Optional[datetime]:
    """Find the date of the last vendor email mentioning ETA for a specific PO."""
    if not request_form_id:
        return None
        
    try:
        result = supabase.table("email_logs") \
            .select("created_at") \
            .eq("request_form_id", request_form_id) \
            .eq("sender_role", "vendor") \
            .ilike("body", "%eta%") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()

        if result.data:
            last_eta_mention_str = result.data[0]["created_at"]
            # Convert string to datetime object
            last_eta_mention_dt = datetime.fromisoformat(last_eta_mention_str.replace("Z", ""))
            print(f"ℹ️ Last ETA mention found for request_form_id {request_form_id}: {last_eta_mention_dt}")
            return last_eta_mention_dt
        else:
            print(f"ℹ️ No vendor email mentioning ETA found for request_form_id {request_form_id}.")
            return None
    except Exception as e:
        print(f"❌ Error finding last ETA reply for request_form_id {request_form_id}: {e}")
        return None 