# external_communication/config.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from pydantic_settings import BaseSettings
from typing import List, ClassVar
from dotenv import load_dotenv
from po_agent_os.supabase_client import supabase

# .env 로드
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

class AgentSettings(BaseSettings):
    # Gmail
    GMAIL_CREDENTIALS_FILE: str = '../credentials.json'
    GMAIL_TOKEN_FILE: str = 'token.json'
    GMAIL_SCOPES: ClassVar[List[str]] = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify'
    ]

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    PYTHONPATH: str = None

    # MCP
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

    # 기타 설정
    POLL_INTERVAL: int = 60  # 초

    # 추가: OpenAI 및 벤더 CSV 경로
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    VENDOR_CSV_PATH: str = os.getenv("VENDOR_CSV_PATH", "")

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "allow"

settings = AgentSettings()
