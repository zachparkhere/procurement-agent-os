# gmail/gmail_watcher.py
from googleapiclient.discovery import build
from typing import Dict, List, Optional
import time
from datetime import datetime, timedelta
from .message_filter import is_vendor_email

class GmailWatcher:
    def __init__(self, service, vendor_manager):
        self.service = service
        self.vendor_manager = vendor_manager
        self.last_check_time = datetime.utcnow()
        self.processed_message_ids = set()

    def get_new_emails(self) -> List[Dict]:
        """
        새로운 이메일만 가져오기
        """
        try:
            # 최근 1분 동안의 읽지 않은 이메일만 검색
            query = f'is:unread after:{(datetime.utcnow() - timedelta(minutes=1)).strftime("%Y/%m/%d")}'
            
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                q=query,
                maxResults=10
            ).execute()
            
            messages = results.get('messages', [])
            new_messages = []
            
            for msg in messages:
                msg_id = msg['id']
                
                # 이미 처리한 메시지는 건너뛰기
                if msg_id in self.processed_message_ids:
                    continue
                
                # 메시지 상세 정보 가져오기
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                
                # 벤더 이메일 필터링
                if is_vendor_email(message, self.vendor_manager):
                    new_messages.append(message)
                    self.processed_message_ids.add(msg_id)
                    
                    # 메시지를 읽음으로 표시
                    self.service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['UNREAD']}
                    ).execute()
            
            return new_messages
            
        except Exception as e:
            print(f"Error getting new emails: {e}")
            return []

    def watch(self, callback):
        """
        실시간 이메일 감시
        """
        while True:
            try:
                new_emails = self.get_new_emails()
                if new_emails:
                    for email in new_emails:
                        callback(email)
                
                time.sleep(60)  # 60초마다 체크
                
            except Exception as e:
                print(f"Error in watch loop: {e}")
                time.sleep(30)  # 에러 발생시 30초 대기
