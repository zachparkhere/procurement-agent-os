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
from Vendor_email_logger_agent.src.services.vendor_manager import VendorManager
from Vendor_email_logger_agent.src.gmail.gmail_auth import get_gmail_service
from po_agent_os.supabase_client_anon import supabase

logger = logging.getLogger(__name__)

class GmailWatcher:
    def __init__(self, service, vendor_manager, user_email: str, user_timezone='UTC'):
        self.service = service
        self.vendor_manager = vendor_manager
        self.user_timezone = timezone(user_timezone)
        self.user_email = user_email
        self.last_check_time = datetime.now(self.user_timezone)
        self.processed_message_ids = set()
        self.error_count = 0
        self.max_errors = 3
        self.callback = None

    def set_callback(self, callback):
        """Set callback function for new emails"""
        self.callback = callback

    def update_timezone(self, new_timezone: str):
        """Update timezone and reset last check time"""
        self.user_timezone = timezone(new_timezone)
        self.last_check_time = datetime.now(self.user_timezone)
        logger.info(f"[Watcher-{self.user_email}] timezone 업데이트됨: {new_timezone}")

    def get_new_emails(self):
        """Get new emails since last check"""
        current_time = datetime.now(self.user_timezone)
        search_after = self.last_check_time.strftime('%Y/%m/%d %H:%M:%S')
        
        logger.info(f"[Watcher-{self.user_email}] 검색 쿼리: after:{search_after}")
        logger.info(f"[Watcher-{self.user_email}] 사용자 시간대: {self.user_timezone}")
        logger.info(f"[Watcher-{self.user_email}] 사용자 현재 시간: {current_time}")
        logger.info(f"[Watcher-{self.user_email}] 검색 시작 시간 (UTC): {self.last_check_time}")
        
        try:
            # 검색 쿼리 실행
            query = f'after:{search_after}'
            results = self.service.users().messages().list(
                userId='me',
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"[Watcher-{self.user_email}] 검색된 메시지 수: {len(messages)}")
            
            new_emails = []
            for message in messages:
                msg_id = message['id']
                if msg_id not in self.processed_message_ids:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='full'
                    ).execute()
                    
                    email_data = self._process_message(msg)
                    if email_data:
                        new_emails.append(email_data)
                        self.processed_message_ids.add(msg_id)
            
            logger.info(f"[Watcher-{self.user_email}] 새 메시지 {len(new_emails)}건 발견")
            self.last_check_time = current_time
            return new_emails
            
        except Exception as e:
            logger.error(f"[Watcher-{self.user_email}] 이메일 검색 중 오류 발생: {e}")
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

    def _process_message(self, message):
        headers = message.get("payload", {}).get("headers", [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # 이메일 수신 시간을 사용자의 시간대로 변환
        try:
            from email.utils import parsedate_to_datetime
            received_time = parsedate_to_datetime(date)
            received_time_user_tz = received_time.astimezone(self.user_timezone)
            logger.info(f"[Watcher] 메시지 확인: ID={message['id']}, 제목={subject}, 발신자={from_email}, 수신시간(사용자 시간대)={received_time_user_tz}")
        except Exception as e:
            logger.warning(f"[Watcher] 시간 파싱 실패: {date}, 에러: {e}")
            received_time_user_tz = None
        
        if is_vendor_email(message, self.vendor_manager):
            logger.info(f"[Watcher] 벤더 이메일 발견: {from_email}")
            return message
        else:
            logger.debug(f"[Watcher] 벤더 이메일 아님: {from_email}")
            return None

def process_gmail_message(email_data: Dict, user_email: str):
    """
    이메일 처리 함수
    """
    try:
        logger.info(f"[Watcher-{user_email}] 이메일 처리 시작: {email_data.get('id')}")
        # 이메일 처리 로직
        # TODO: 실제 이메일 처리 로직 구현
    except Exception as e:
        logger.error(f"[Watcher-{user_email}] 이메일 처리 중 오류 발생: {e}")
        logger.error(traceback.format_exc())

def run_for_user(user_email: str, interval: int = 15):
    """
    특정 사용자의 이메일을 감시하는 함수
    """
    try:
        logger.info(f"[Watcher] 사용자 {user_email}의 이메일 감시 시작")
        
        # Gmail 서비스 가져오기
        service = get_gmail_service(user_email)
        if not service:
            logger.error(f"[Watcher] 사용자 {user_email}의 Gmail 서비스를 초기화할 수 없음")
            return
        
        # VendorManager 생성
        vendor_manager = VendorManager()
        
        # DB에서 사용자의 timezone 가져오기
        user_data = supabase.table("users").select("timezone").eq("email", user_email).single().execute()
        timezone = user_data.data.get("timezone", "UTC") if user_data.data else "UTC"
        
        # GmailWatcher 생성 및 시작
        watcher = GmailWatcher(service, vendor_manager, user_email, timezone)
        watcher.watch(lambda email: process_gmail_message(email, user_email))
        
    except Exception as e:
        logger.error(f"[{user_email}] Error in run_for_user: {e}")
        logger.error(traceback.format_exc())

async def poll_emails(interval: int = 15):
    """
    이메일 폴링 함수
    """
    try:
        # DB에서 사용자 목록 가져오기
        users = supabase.table("users").select("email,timezone").execute()
        
        if not users.data:
            logger.error("사용자 정보를 가져올 수 없음")
            return
        
        # 각 사용자별로 이메일 감시 시작
        for user in users.data:
            user_email = user.get('email')
            timezone = user.get('timezone', 'UTC')
            
            if not user_email:
                continue
                
            try:
                # 각 사용자별로 Gmail 서비스 가져오기
                service = get_gmail_service(user_email)
                if not service:
                    logger.error(f"[Watcher] 사용자 {user_email}의 Gmail 서비스를 초기화할 수 없음")
                    continue
                
                # VendorManager 생성
                vendor_manager = VendorManager()
                
                # GmailWatcher 생성 및 시작
                watcher = GmailWatcher(service, vendor_manager, user_email, timezone)
                watcher.watch(lambda email: process_gmail_message(email, user_email))
            except Exception as e:
                logger.error(f"[{user_email}] Error in poll_emails: {e}")
                logger.error(traceback.format_exc())
                continue
        
    except Exception as e:
        logger.error(f"Error in poll_emails: {e}")
        logger.error(traceback.format_exc())
