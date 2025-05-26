import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from external_communication.handle_general_vendor_email import handle_general_vendor_email
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