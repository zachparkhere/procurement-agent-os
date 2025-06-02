# gmail/gmail_watcher.py
from googleapiclient.discovery import build
from typing import Dict, List, Optional, Callable
import time
from datetime import datetime, timedelta, timezone
from Vendor_email_logger_agent.src.gmail.message_filter import is_vendor_email
import traceback
import logging
from googleapiclient.discovery import Resource
from pytz import timezone as pytz_timezone
from Vendor_email_logger_agent.src.services.vendor_manager import VendorManager
from Vendor_email_logger_agent.src.gmail.gmail_auth import get_gmail_service
from po_agent_os.supabase_client_anon import supabase
import asyncio
import re
from dateutil import parser

logger = logging.getLogger(__name__)

class GmailWatcher:
    def __init__(self, service, vendor_manager, user_email, user_timezone_str, email_processor=None, mcp_service=None, user_id=None, process_callback=None):
        self.service = service
        self.vendor_manager = vendor_manager
        self.user_email = user_email
        self.user_timezone = pytz_timezone(user_timezone_str)
        now_utc = datetime.now(timezone.utc)
        now_user_tz = now_utc.astimezone(self.user_timezone)
        self.now_user_tz = now_user_tz
        self.prev_user_tz = now_user_tz - timedelta(seconds=60)
        self.last_timezone_check = now_utc
        self.email_processor = email_processor
        self.mcp_service = mcp_service
        self.user_id = user_id
        self.process_callback = process_callback  # async 콜백 함수
        logger.debug(f"[DEBUG] {self.user_email} 기준시(유저 현지): {self.now_user_tz}")

    async def poll_emails(self):
        # 1. 폴링 구간(1분) 계산
        logger.debug(f"[DEBUG] {self.user_email} 폴링 시작: prev_user_tz={self.prev_user_tz}, now_user_tz={self.now_user_tz}")
        after_utc = self.prev_user_tz.astimezone(timezone.utc)
        before_utc = self.now_user_tz.astimezone(timezone.utc)
        after_timestamp = int(after_utc.timestamp())
        before_timestamp = int(before_utc.timestamp())
        logger.debug(f"[DEBUG] {self.user_email} 폴링 구간(UTC): {after_utc} ~ {before_utc} (timestamp: {after_timestamp} ~ {before_timestamp})")

        # 2. INBOX(받은 메일) 쿼리
        results_inbox = self.service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            q=f"after:{after_timestamp} before:{before_timestamp}",
            maxResults=10
        ).execute()
        messages_inbox = results_inbox.get('messages', [])
        logger.debug(f"[DEBUG] {self.user_email} INBOX 메시지 수: {len(messages_inbox)}")

        # 3. SENT(보낸 메일) 쿼리
        results_sent = self.service.users().messages().list(
            userId='me',
            labelIds=['SENT'],
            q=f"after:{after_timestamp} before:{before_timestamp}",
            maxResults=10
        ).execute()
        messages_sent = results_sent.get('messages', [])
        logger.debug(f"[DEBUG] {self.user_email} SENT 메시지 수: {len(messages_sent)}")

        # 4. 합치기 (중복 제거)
        all_messages = {msg['id']: msg for msg in messages_inbox + messages_sent}.values()
        logger.debug(f"[DEBUG] {self.user_email} 합쳐진 메시지 수(중복제거): {len(list(all_messages))}")

        def clean_date_str(date_str):
            date_str = re.sub(r"([+-][0-9]{4}) ?\([^)]+\)", r"\1", date_str)
            date_str = re.sub(r"([+-][0-9]{4}) ?([+-][0-9]{4})", r"\2", date_str)
            date_str = re.sub(r" ?\([^)]+\)", "", date_str)
            date_str = re.sub(r" +", " ", date_str).strip()
            logger.debug(f"[clean_date_str] after clean: '{date_str}'")
            return date_str

        def get_msg_date(msg):
            try:
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Date']
                ).execute()
                headers = message.get("payload", {}).get("headers", [])
                date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                date_str = clean_date_str(date_str)
                logger.debug(f"[get_msg_date] final date_str: '{date_str}'")
                try:
                    dt = parser.parse(date_str)
                    dt = dt.astimezone(timezone.utc)
                    return dt
                except Exception as e:
                    logger.warning(f"Failed to parse date for msg {msg['id']}: {e}")
                    from datetime import timezone as dt_tz
                    return datetime.max.replace(tzinfo=dt_tz.utc)
            except Exception as e:
                logger.warning(f"Failed to parse date for msg {msg['id']}: {e}")
                from datetime import timezone as dt_tz
                return datetime.max.replace(tzinfo=dt_tz.utc)

        # 5. 정렬
        all_messages = sorted(all_messages, key=get_msg_date)
        logger.debug(f"[DEBUG] {self.user_email} 정렬된 메시지 수: {len(all_messages)}")

        for msg in all_messages:
            msg_id = msg['id']
            # 6. 중복 체크
            exists = supabase.from_("email_logs").select("message_id").eq("message_id", msg_id).execute().data
            logger.debug(f"[DEBUG] {self.user_email} 메시지 {msg_id} DB 중복 여부: {bool(exists)}")
            if not exists:
                # 7. 벤더 이메일 필터
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                is_vendor = is_vendor_email(message, self.vendor_manager)
                logger.debug(f"[DEBUG] {self.user_email} 메시지 {msg_id} is_vendor_email: {is_vendor}")
                if is_vendor:
                    # 8. robust한 콜백 처리
                    msg_full = self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='full'
                    ).execute()
                    logger.debug(f"[DEBUG] {self.user_email} 메시지 {msg_id} process_callback 호출")
                    if self.process_callback:
                        await self.process_callback(self.service, msg_full, self.email_processor, self.mcp_service, self.vendor_manager, self.user_id)
                    else:
                        raise RuntimeError("process_callback이 설정되어 있지 않습니다. main.py의 process_email을 넘기세요.")

        # 9. 폴링 구간 갱신
        logger.debug(f"[DEBUG] {self.user_email} 폴링 구간 갱신: prev_user_tz <- {self.now_user_tz}, now_user_tz <- 현재시각")
        self.prev_user_tz = self.now_user_tz
        self.now_user_tz = datetime.now(timezone.utc).astimezone(self.user_timezone)

    def process_email(self, msg):
        headers = msg.get("payload", {}).get("headers", [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        # 이메일 수신 시간을 사용자의 시간대로 변환
        try:
            from email.utils import parsedate_to_datetime
            received_time = parsedate_to_datetime(date)
            received_time_user_tz = received_time.astimezone(self.user_timezone)
            print(f"[Watcher] 메시지 확인: ID={msg['id']}, 제목={subject}, 발신자={from_email}, 수신시간(유저 현지): {received_time_user_tz}")
        except Exception as e:
            print(f"[Watcher] 시간 파싱 실패: {date}, 에러: {e}")

    def check_timezone(self, new_timezone_str):
        # 3. 30분마다 타임존 체크
        if new_timezone_str != str(self.user_timezone):
            self.user_timezone = pytz_timezone(new_timezone_str)
            now_utc = datetime.now(timezone.utc)
            self.now_user_tz = now_utc.astimezone(self.user_timezone)
            self.prev_user_tz = self.now_user_tz - timedelta(seconds=60)
            print(f"[DEBUG] {self.user_email} 타임존 변경: {new_timezone_str}, 기준시각 재설정: {self.now_user_tz}")

    async def run(self):
        try:
            while True:
                now_utc = datetime.now(timezone.utc)
                # 30분마다 타임존 체크
                if (now_utc - self.last_timezone_check) > timedelta(minutes=30):
                    new_timezone_str = self.get_timezone_from_db()
                    self.check_timezone(new_timezone_str)
                    self.last_timezone_check = now_utc
                await self.poll_emails()
                await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[Watcher] run() 예외 발생: {e}", exc_info=True)

    def get_timezone_from_db(self):
        # Supabase에서 self.user_email의 timezone 컬럼(varchar, 예: 'Asia/Seoul')을 읽어옴
        try:
            response = supabase.from_("users").select("timezone").eq("email", self.user_email).single().execute()
            if response.data and response.data.get("timezone"):
                tz = response.data["timezone"]
                logger.debug(f"[DEBUG] {self.user_email}의 timezone을 DB에서 읽어옴: {tz}")
                return tz
            else:
                logger.error(f"[ERROR] {self.user_email}의 timezone을 DB에서 찾을 수 없음. response: {response.data}")
                return None
        except Exception as e:
            logger.error(f"[ERROR] DB에서 timezone 조회 실패: {e}")
            return None

# 기존 GmailWatcher는 이름을 바꿔 임시로 보관
class LegacyGmailWatcher:
    def __init__(self, service, vendor_manager, user_email: str, user_timezone='UTC'):
        self.service = service
        self.vendor_manager = vendor_manager
        self.user_timezone = timezone(user_timezone)
        self.user_email = user_email
        self.error_count = 0
        self.max_errors = 3
        self.callback = None
        self.supabase = supabase  # supabase 클라이언트 추가

    def set_callback(self, callback):
        """Set callback function for new emails"""
        self.callback = callback

    def update_timezone(self, new_timezone: str):
        """Update timezone"""
        self.user_timezone = timezone(new_timezone)
        logger.info(f"[Watcher-{self.user_email}] timezone 업데이트됨: {new_timezone}")

    def get_new_emails(self):
        """Get recent emails"""
        try:
            # 최근 메시지 가져오기 (INBOX와 SENT만)
            results = self.service.users().messages().list(
                userId='me',
                maxResults=5,  # 최근 50개 메시지로 증가
                labelIds=['INBOX', 'SENT']  # INBOX와 SENT만 포함
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"[Watcher-{self.user_email}] 검색된 메시지 수: {len(messages)}")
            
            new_emails = []
            for message in messages:
                msg_id = message['id']
                # DB에서 중복 체크
                exists = self.supabase.from_("email_logs") \
                    .select("message_id") \
                    .eq("message_id", msg_id) \
                    .execute().data
                
                if not exists:  # DB에 없으면 처리
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='full'
                    ).execute()
                    
                    email_data = self._process_message(msg)
                    if email_data:
                        new_emails.append(email_data)
            
            logger.info(f"[Watcher-{self.user_email}] 새 메시지 {len(new_emails)}건 발견")
            return new_emails
            
        except Exception as e:
            logger.error(f"[Watcher-{self.user_email}] 이메일 검색 중 오류 발생: {e}")
            logger.error(traceback.format_exc())  # 스택 트레이스 추가
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
        
        # DB에서 사용자 정보 가져오기
        user_data = supabase.table("users").select("*").eq("email", user_email).single().execute()
        if not user_data.data:
            logger.error(f"[Watcher] 사용자 {user_email}의 정보를 찾을 수 없음")
            return
        
        # Gmail 서비스 가져오기
        service = get_gmail_service(user_data.data)  # user_email 대신 user_data.data 전달
        if not service:
            logger.error(f"[Watcher] 사용자 {user_email}의 Gmail 서비스를 초기화할 수 없음")
            return
        
        # VendorManager 생성
        vendor_manager = VendorManager()
        
        # DB에서 사용자의 timezone 가져오기
        timezone = user_data.data.get("timezone", "UTC")
        
        # GmailWatcher 생성 및 시작
        watcher = LegacyGmailWatcher(service, vendor_manager, user_email, timezone)
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
        users = supabase.table("users").select("*").execute()
        
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
                service = get_gmail_service(user)  # user_email 대신 user 전달
                if not service:
                    logger.error(f"[Watcher] 사용자 {user_email}의 Gmail 서비스를 초기화할 수 없음")
                    continue
                
                # VendorManager 생성
                vendor_manager = VendorManager()
                
                # GmailWatcher 생성 및 시작
                watcher = LegacyGmailWatcher(service, vendor_manager, user_email, timezone)
                watcher.watch(lambda email: process_gmail_message(email, user_email))
            except Exception as e:
                logger.error(f"[{user_email}] Error in poll_emails: {e}")
                logger.error(traceback.format_exc())
                continue
        
    except Exception as e:
        logger.error(f"Error in poll_emails: {e}")
        logger.error(traceback.format_exc())

# 예시 실행 코드 (테스트용)
if __name__ == "__main__":
    # service, vendor_manager는 실제 환경에 맞게 전달 필요
    async def dummy_callback(service, msg, email_processor, mcp_service, vendor_manager, user_id):
        print(f"[CALLBACK] 처리: {msg['id']}")
    watcher = GmailWatcher(service=None, vendor_manager=None, user_email="test@example.com", user_timezone_str="Asia/Seoul", process_callback=dummy_callback)
    asyncio.run(watcher.run())
