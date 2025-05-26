from supabase import create_client
import os
from dotenv import load_dotenv

# 현재 디렉토리 기준으로 .env 파일 로드
load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 환경 변수 확인
if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is not set")
if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is not set")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) 