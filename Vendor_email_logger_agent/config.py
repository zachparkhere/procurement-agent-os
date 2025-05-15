from pydantic_settings import BaseSettings
from typing import List, ClassVar
import os
from dotenv import load_dotenv
from supabase import create_client

# .env 파일을 프로젝트 루트에서 명시적으로 로드
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

class AgentSettings(BaseSettings):
    # Gmail API 설정
    GMAIL_CREDENTIALS_FILE: str = 'credentials.json'
    GMAIL_TOKEN_FILE: str = 'token.json'
    GMAIL_SCOPES: ClassVar[List[str]] = [
        'https://mail.google.com/'
    ]
    
    # MCP 서버 설정
    MCP_SERVER_URL: str = os.getenv('MCP_SERVER_URL', 'http://localhost:8000')
    
    # Supabase 설정
    SUPABASE_URL: str = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY: str = os.getenv('SUPABASE_KEY', '')
    
    # OpenAI 설정
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # OpenAI API 키
    
    # 벤더 설정
    VENDOR_CSV_PATH: str = os.getenv("VENDOR_CSV_PATH", "")  # 벤더 이메일 CSV 파일 경로
    
    # 에이전트 설정
    POLL_INTERVAL: int = 60  # 이메일 확인 간격 (초)
    
    # 상태 타입
    STATUS_TYPES: ClassVar[List[str]] = [
        'unread',
        'read',
        'processing',
        'completed',
        'error'
    ]
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True

settings = AgentSettings()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY) 