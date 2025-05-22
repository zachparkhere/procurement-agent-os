import os
from dotenv import load_dotenv
from po_agent_os.supabase_client_anon import supabase

# ✅ Load environment variables from .env in project root
load_dotenv()

# ✅ Fetch Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# ✅ Validate credentials
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env file.")

# ✅ Create Supabase client
supabase = supabase
