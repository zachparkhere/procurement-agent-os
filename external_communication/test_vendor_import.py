import sys
import os

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'vendor_email_logger_agent', 'src')
sys.path.insert(0, SRC_DIR)

from services.supabase_service import SupabaseService
from processors.email_processor import EmailProcessor
from gmail.gmail_service import get_gmail_service

print("✅ vendor_email_logger_agent/src 모듈 import 성공!") 