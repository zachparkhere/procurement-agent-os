import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "utils"))

from handle_general_vendor_email import handle_general_vendor_email
from utils.attachment_parser import extract_text_from_attachments

async def handle_vendor_reply_message(payload: dict):
    """
    MCP 메시지 수신: type = 'vendor_reply'
    payload: {}
    """
    print("[📬 VENDOR REPLY AGENT] Running general reply handler...")
    try:
        handle_general_vendor_email()
    except Exception as e:
        print(f"[❌ VENDOR REPLY AGENT ERROR] {e}")