# gmail/gmail_watcher.py
from googleapiclient.discovery import build
from typing import Dict, List, Optional, Callable
import time
from datetime import datetime, timedelta
from Vendor_email_logger_agent.src.gmail.message_filter import is_vendor_email
import traceback
import logging
from googleapiclient.discovery import Resource

logger = logging.getLogger(__name__)

class GmailWatcher:
    def __init__(self, service, vendor_manager):
        self.service = service
        self.vendor_manager = vendor_manager
        self.last_check_time = datetime.utcnow()
        self.processed_message_ids = set()
        self.error_count = 0
        self.max_errors = 3

    def get_new_emails(self) -> List[Dict]:
        """
        새로운 이메일만 가져오기
        """
        try:
            # 마지막 체크 시간 이후의 모든 이메일 검색 (unread 조건 제거)
            query = f'after:{self.last_check_time.strftime("%Y/%m/%d %H:%M:%S")}'
            logger.info(f"[Watcher] 검색 쿼리: {query}")
            logger.info(f"[Watcher] 마지막 체크 시간: {self.last_check_time}")
            
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                q=query,
                maxResults=50  # 한 번에 더 많은 메시지 처리
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"[Watcher] 검색된 메시지 수: {len(messages)}")
            
            new_messages = []
            
            for msg in messages:
                msg_id = msg['id']
                
                # 이미 처리한 메시지는 건너뛰기
                if msg_id in self.processed_message_ids:
                    logger.debug(f"[Watcher] 이미 처리된 메시지 건너뛰기: {msg_id}")
                    continue
                
                try:
                    # 메시지 상세 정보 가져오기
                    message = self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['Subject', 'From', 'Date', 'To']
                    ).execute()
                    
                    # 메시지 정보 로깅
                    headers = message.get("payload", {}).get("headers", [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                    from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
                    logger.info(f"[Watcher] 메시지 확인: ID={msg_id}, 제목={subject}, 발신자={from_email}")
                    
                    # 벤더 이메일 필터링
                    if is_vendor_email(message, self.vendor_manager):
                        logger.info(f"[Watcher] 벤더 이메일 발견: {from_email}")
                        new_messages.append(message)
                        self.processed_message_ids.add(msg_id)
                        
                        # 메시지를 읽음으로 표시
                        self.service.users().messages().modify(
                            userId='me',
                            id=msg_id,
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                    else:
                        logger.debug(f"[Watcher] 벤더 이메일 아님: {from_email}")
                except Exception as e:
                    logger.error(f"[Watcher] 메시지 처리 중 에러 {msg_id}: {e}")
                    continue
            
            # 마지막 체크 시간 업데이트
            self.last_check_time = datetime.utcnow()
            logger.info(f"[Watcher] 새 메시지 {len(new_messages)}건 발견")
            return new_messages
            
        except Exception as e:
            logger.error(f"[Watcher] 이메일 검색 중 에러: {e}")
            self.error_count += 1
            return []

    def watch(self, callback):
        """
        실시간 이메일 감시
        """
        logger.info("[Watcher] 실시간 감시 루프 시작")
        while True:
            try:
                logger.debug("[Watcher] 새 메일 체크")
                new_emails = self.get_new_emails()
                
                if new_emails:
                    logger.info(f"[Watcher] {len(new_emails)}건의 새 메일 발견")
                    for email in new_emails:
                        try:
                            logger.debug(f"[Watcher] 콜백 호출: {email.get('id')}")
                            callback(email)
                        except Exception as e:
                            logger.error(f"[Watcher] 콜백 예외: {e}")
                            logger.error(traceback.format_exc())
                else:
                    logger.debug("[Watcher] 새 메일 없음")
                
                # 성공적으로 처리되면 에러 카운트 리셋
                self.error_count = 0
                
                # 에러 발생 시 대기 시간 조정
                wait_time = 10 if self.error_count > 0 else 60
                logger.debug(f"[Watcher] 다음 체크까지 {wait_time}초 대기")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"[Watcher] 루프 예외 발생: {e}")
                logger.error(traceback.format_exc())
                self.error_count += 1
                
                if self.error_count >= self.max_errors:
                    logger.error("최대 에러 횟수 도달. 감시 재시작")
                    self.error_count = 0
                    self.last_check_time = datetime.utcnow()  # 체크 시간 리셋
                
                time.sleep(min(10 * self.error_count, 30))  # 점진적으로 대기 시간 증가
