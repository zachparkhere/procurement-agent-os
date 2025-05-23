# gmail/email_collector.py
import logging
from typing import Dict, List, Optional
from googleapiclient.discovery import Resource
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from Vendor_email_logger_agent.src.gmail.message_filter import is_vendor_email, get_email_type

logger = logging.getLogger(__name__)

class EmailCollector:
    def __init__(self, service):
        self.service = service
        logger.info("EmailCollector initialized")

    def collect_emails(self, 
                      days_back: int = 30, # 30일 전 이메일만 수집
                      max_results: int = 100,
                      email_type: Optional[str] = None) -> List[Dict]:
        """
        기존 이메일 수집
        
        Args:
            days_back: 몇 일 전까지의 이메일을 수집할지
            max_results: 최대 수집할 이메일 수
            email_type: 특정 유형의 이메일만 수집 (purchase_request, purchase_order, vendor_communication)
        """
        try:
            # 검색 쿼리 생성
            query = f'after:{(datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")}'
            logger.info(f"Searching emails with query: {query}")
            
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} messages")
            
            collected_emails = []
            
            for msg in messages:
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                
                # 벤더 이메일 필터링
                if is_vendor_email(message):
                    # 특정 유형의 이메일만 수집
                    if email_type:
                        if get_email_type(message) == email_type:
                            collected_emails.append(message)
                            logger.info(f"Collected email: {message.get('id')} - Type: {email_type}")
                    else:
                        collected_emails.append(message)
                        logger.info(f"Collected email: {message.get('id')}")
            
            logger.info(f"Total collected emails: {len(collected_emails)}")
            return collected_emails
            
        except Exception as e:
            logger.error(f"Error collecting emails: {e}")
            return []

    def collect_by_thread(self, thread_id: str) -> List[Dict]:
        """
        특정 스레드의 모든 이메일 수집
        """
        try:
            logger.info(f"Collecting emails from thread: {thread_id}")
            
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()
            
            messages = thread.get('messages', [])
            logger.info(f"Found {len(messages)} messages in thread")
            
            collected_emails = []
            
            for msg in messages:
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                
                if is_vendor_email(message):
                    collected_emails.append(message)
                    logger.info(f"Collected email from thread: {msg['id']}")
            
            logger.info(f"Total collected emails from thread: {len(collected_emails)}")
            return collected_emails
            
        except Exception as e:
            logger.error(f"Error collecting thread emails: {e}")
            return [] 