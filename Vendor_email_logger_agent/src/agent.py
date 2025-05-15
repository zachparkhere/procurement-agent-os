# vendor_email_logger_agent/agent.py

from typing import Dict, List, Optional
import json
from datetime import datetime
from gmail.gmail_watcher import poll_emails
from gmail.message_filter import is_vendor_email
from services.mcp_service import MCPService
from utils.text_processor import TextProcessor

class VendorEmailLoggerAgent:
    def __init__(self):
        self.vendor_mapping = {}  # email -> vendor_id mapping
        self.email_threads = {}   # thread_id -> email list mapping
        self.status_history = {}  # vendor_id -> status history mapping
        self.mcp_service = MCPService()
        self.text_processor = TextProcessor()

    def get_thread_context(self, thread_id: str) -> List[Dict]:
        """
        특정 thread의 이전 이메일들을 시간순으로 가져옵니다.
        """
        return self.email_threads.get(thread_id, [])

    def extract_po_number(self, email_data: Dict) -> Optional[str]:
        """
        이메일에서 PO 번호를 추출합니다.
        1. 기존 정규식 패턴으로 시도
        2. 실패 시 LLM으로 시도
        """
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        thread_id = email_data.get('threadId', '')
        
        # 1. 먼저 기존 thread에서 PO 번호 찾기
        thread_context = self.get_thread_context(thread_id)
        for email in thread_context:
            if email.get('po_number'):
                return email['po_number']
        
        # 2. text_processor로 PO 번호 추출 시도
        po_number = self.text_processor.extract_po_number(
            email_content=body,
            attachments=email_data.get('attachments', None)
        )
        
        if po_number:
            print(f"✅ LLM이 PO 번호를 추출했습니다: {po_number}")
            return po_number
            
        print("⚠️ PO 번호를 찾을 수 없습니다.")
        return None

    def process_email(self, email_data: Dict):
        """Process a single email and update relevant records"""
        # Extract basic information
        sender = email_data.get('from', '')
        subject = email_data.get('subject', '')
        thread_id = email_data.get('threadId', '')
        body = email_data.get('body', '')
        
        # PO 번호 추출
        po_number = self.extract_po_number(email_data)
        if po_number:
            email_data['po_number'] = po_number
        
        # Map to vendor if possible
        vendor_id = self.map_to_vendor(sender)
        
        # Update thread tracking
        if thread_id not in self.email_threads:
            self.email_threads[thread_id] = []
        self.email_threads[thread_id].append(email_data)
        
        # Determine status
        status = self.determine_status(email_data)
        
        # Update status history
        if vendor_id:
            if vendor_id not in self.status_history:
                self.status_history[vendor_id] = []
            self.status_history[vendor_id].append({
                'status': status,
                'timestamp': datetime.utcnow().isoformat(),
                'email_id': email_data.get('id', ''),
                'po_number': po_number
            })
        
        # Send to MCP for further processing
        self.send_to_mcp(email_data, vendor_id, status, po_number)

    def map_to_vendor(self, email: str) -> str:
        """Map email address to vendor_id"""
        # TODO: Implement vendor mapping logic
        return self.vendor_mapping.get(email, '')

    def determine_status(self, email_data: Dict) -> str:
        """Determine the status of the email communication"""
        # TODO: Implement status determination logic
        return 'pending'

    async def send_to_mcp(self, email_data: Dict, vendor_id: str, status: str, po_number: Optional[str] = None):
        """Send processed email data to MCP"""
        message = {
            'message_id': email_data.get('id', ''),
            'thread_id': email_data.get('threadId', ''),
            'direction': 'inbound',
            'from': email_data.get('from', ''),
            'to': email_data.get('to', ''),
            'subject': email_data.get('subject', ''),
            'date': email_data.get('date', ''),
            'body_text': email_data.get('body', ''),
            'attachments': email_data.get('attachments', None),
            'status': status,
            'vendor_id': vendor_id,
            'po_number': po_number
        }
        await self.mcp_service.send_message(message)

    async def start_monitoring(self, interval: int = 15):
        """Start monitoring emails"""
        try:
            await poll_emails(interval=interval)
        finally:
            await self.mcp_service.close()
