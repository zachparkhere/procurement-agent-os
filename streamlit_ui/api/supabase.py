import os
from dotenv import load_dotenv
from supabase import create_client

# ✅ Load environment variables from .env in project root
load_dotenv()

# ✅ Fetch Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ✅ Validate credentials
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing SUPABASE_URL or SUPABASE_KEY in .env file.")

# ✅ Create Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
