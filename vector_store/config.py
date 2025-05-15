from pydantic_settings import BaseSettings
import os
from typing import Optional
from pathlib import Path

class VectorStoreSettings(BaseSettings):
    # 프로젝트 루트 경로 설정
    BASE_DIR: Path = Path(__file__).parent.parent

    # Supabase 설정
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # OpenAI 설정
    OPENAI_API_KEY: str

    # 벡터 스토어 설정
    CLEANUP_INTERVAL: int = 3600  # 1시간
    UPDATE_INTERVAL: int = 300    # 5분
    MAX_CHARS: int = 4000        # 임베딩 최대 문자 수
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# 전역 설정 객체 생성
settings = VectorStoreSettings() 