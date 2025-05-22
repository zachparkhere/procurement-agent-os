import os
from dotenv import load_dotenv
from supabase import create_client

# ✅ .env 로드
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ✅ 클라이언트 객체 생성
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
