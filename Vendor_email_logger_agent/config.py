from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv
from supabase import create_client

# .env 파일을 절대 경로로 로드
env_path = os.path.expanduser("~/procurement-agent-os/.env")
load_dotenv(env_path)

class AgentSettings(BaseSettings):
    # Gmail API 설정
    GMAIL_CREDENTIALS_FILE: str = 'credentials.json'
    GMAIL_TOKEN_FILE: str = 'token.json'
    GMAIL_SCOPES: list[str] = ['https://mail.google.com/']
    
    # MCP 서버 설정
    MCP_SERVER_URL: str = os.getenv('MCP_SERVER_URL', 'http://localhost:8000')
    
    # Supabase 설정
    SUPABASE_URL: str = os.getenv('SUPABASE_URL', '')
    SUPABASE_ANON_KEY: str = os.getenv('SUPABASE_ANON_KEY', '')
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
    
    # OpenAI 설정
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # OpenAI API 키
    
    # 벤더 설정
    VENDOR_CSV_PATH: str = os.getenv("VENDOR_CSV_PATH", "")  # 벤더 이메일 CSV 파일 경로
    
    # 에이전트 설정
    POLL_INTERVAL: int = 60  # 이메일 확인 간격 (초)
    
    # 상태 타입
    STATUS_TYPES: list[str] = ['unread', 'read', 'processing', 'completed', 'error']
    
    # Google OAuth 설정
    GOOGLE_CLIENT_ID: str = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET: str = os.getenv('GOOGLE_CLIENT_SECRET', '')
    PYTHONPATH: str = os.getenv('PYTHONPATH', '')
    
    class Config:
        env_file = env_path
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "allow"

settings = AgentSettings()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY) 