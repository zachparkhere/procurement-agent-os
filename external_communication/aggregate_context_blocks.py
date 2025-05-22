# aggregate_context_blocks.py

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def find_best_matching_table(info_keyword):
    embedding = client.embeddings.create(
        model="text-embedding-ada-002",
        input=info_keyword
    ).data[0].embedding

    result = supabase.rpc("match_vector_schema", {
        "query_embedding": embedding,
        "match_count": 1
    }).execute()

    return result.data[0]["table_name"] if result.data else None

def find_most_relevant_record(table_name, query_text):
    embedding = client.embeddings.create(
        model="text-embedding-ada-002",
        input=query_text
    ).data[0].embedding

    result = supabase.rpc("match_vector_records", {
        "query_embedding": embedding,
        "match_count": 1,
        "match_table": table_name
    }).execute()

    if not result.data:
        return None
        
    record = result.data[0]
    return {
        "id": record["id"],
        "content": record["content"]
    }

def aggregate_context_blocks(info_needed, query_text):
    seen = set()
    contexts = []

    for keyword in info_needed:
        table = find_best_matching_table(keyword)
        if table and table not in seen:
            seen.add(table)
            record = find_most_relevant_record(table, query_text)
            if record:
                contexts.append((table, record["content"], record["id"]))

    return contexts 