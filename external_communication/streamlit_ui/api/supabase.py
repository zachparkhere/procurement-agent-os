import os
from supabase import create_client

SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env file.")

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY) 