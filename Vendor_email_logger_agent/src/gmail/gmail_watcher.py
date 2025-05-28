# gmail/gmail_watcher.py
from googleapiclient.discovery import build
from typing import Dict, List, Optional, Callable
import time
from datetime import datetime, timedelta
from Vendor_email_logger_agent.src.gmail.message_filter import is_vendor_email
import traceback
import logging
from googleapiclient.discovery import Resource
from pytz import timezone, UTC

logger = logging.getLogger(__name__)

class GmailWatcher:
    def __init__(self, service, vendor_manager, user_timezone='UTC'):
        self.service = service
        self.vendor_manager = vendor_manager
        self.user_timezone = timezone(user_timezone)
        self.last_check_time = datetime.now(self.user_timezone)
        self.processed_message_ids = set()
        self.error_count = 0
        self.max_errors = 3

    def update_timezone(self, new_timezone):
        """
        시간대 업데이트
        """
        try:
            self.user_timezone = timezone(new_timezone)
            # 마지막 체크 시간을 새로운 시간대로 변환
            self.last_check_time = datetime.now(self.user_timezone)
            logger.info(f"[Watcher] 시간대 업데이트: {new_timezone}")
        except Exception as e:
            logger.error(f"[Watcher] 시간대 업데이트 실패: {e}")

    def get_new_emails(self) -> List[Dict]:
        """
        새로운 이메일만 가져오기
        """
        try:
            # 사용자의 시간대 기준으로 현재 시간 계산
            user_now = datetime.now(self.user_timezone)
            # 5분 전부터 검색
            search_start = (user_now - timedelta(minutes=5))
            
            # UTC로 변환 (Gmail API는 UTC 사용)
            search_start_utc = search_start.astimezone(UTC)
            search_start_str = search_start_utc.strftime("%Y/%m/%d %H:%M:%S")
            
            query = f'after:{search_start_str}'
            logger.info(f"[Watcher] 검색 쿼리: {query}")
            logger.info(f"[Watcher] 사용자 시간대: {self.user_timezone}")
            logger.info(f"[Watcher] 사용자 현재 시간: {user_now}")
            logger.info(f"[Watcher] 검색 시작 시간 (UTC): {search_start_utc}")
            
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                q=query,
                maxResults=50
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"[Watcher] 검색된 메시지 수: {len(messages)}")
            
            new_messages = []
            
            for msg in messages:
                msg_id = msg['id']
                
                if msg_id in self.processed_message_ids:
                    logger.debug(f"[Watcher] 이미 처리된 메시지 건너뛰기: {msg_id}")
                    continue
                
                try:
                    message = self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='metadata',
                        metadataHeaders=['Subject', 'From', 'Date', 'To']
                    ).execute()
                    
                    headers = message.get("payload", {}).get("headers", [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                    from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
                    date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                    
                    # 이메일 수신 시간을 사용자의 시간대로 변환
                    try:
                        from email.utils import parsedate_to_datetime
                        received_time = parsedate_to_datetime(date)
                        received_time_user_tz = received_time.astimezone(self.user_timezone)
                        logger.info(f"[Watcher] 메시지 확인: ID={msg_id}, 제목={subject}, 발신자={from_email}, 수신시간(사용자 시간대)={received_time_user_tz}")
                    except Exception as e:
                        logger.warning(f"[Watcher] 시간 파싱 실패: {date}, 에러: {e}")
                        received_time_user_tz = None
                    
                    if is_vendor_email(message, self.vendor_manager):
                        logger.info(f"[Watcher] 벤더 이메일 발견: {from_email}")
                        new_messages.append(message)
                        self.processed_message_ids.add(msg_id)
                        
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
            
            # 마지막 체크 시간 업데이트 (사용자 시간대 기준)
            self.last_check_time = user_now
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
        logger.info(f"[Watcher] 실시간 감시 루프 시작 (사용자 시간대: {self.user_timezone})")
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
                
                self.error_count = 0
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
                    self.last_check_time = datetime.now(self.user_timezone)
                
                time.sleep(min(10 * self.error_count, 30))
