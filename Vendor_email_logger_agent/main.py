import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from Vendor_email_logger_agent.config import settings, AgentSettings
import openai
from google.auth.transport.requests import Request
from dateutil import parser
import traceback

from Vendor_email_logger_agent.src.gmail.gmail_watcher import GmailWatcher
from Vendor_email_logger_agent.src.gmail.email_collector import EmailCollector
from Vendor_email_logger_agent.src.utils.text_processor import TextProcessor
from Vendor_email_logger_agent.src.processors.email_processor import EmailProcessor
from Vendor_email_logger_agent.src.processors.attachment_processor import AttachmentProcessor
from Vendor_email_logger_agent.src.services.mcp_service import MCPService
from Vendor_email_logger_agent.src.services.supabase_service import SupabaseService
from Vendor_email_logger_agent.src.gmail.message_filter import VendorEmailManager, is_vendor_email, extract_email_address
from Vendor_email_logger_agent.src.gmail.watcher_manager import watcher_manager
from external_communication.utils.email_utils import get_gmail_service

# Load settings
settings = AgentSettings()

# Initialize OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

# 로그 디렉토리 생성
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 로깅 설정
log_file = os.path.join(log_dir, f'email_logger_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')

# SupabaseService 인스턴스 생성
supabase_service = SupabaseService()

def authenticate_gmail():
    """Gmail API 인증"""
    creds = None
    credentials_path = CREDENTIALS_PATH
    token_path = os.path.join(os.path.dirname(__file__), 'credentials', 'token.json')
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, settings.GMAIL_SCOPES)
    else:
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"credentials.json file not found at {credentials_path}")
            
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_path, 
            settings.GMAIL_SCOPES
        )
        creds = flow.run_local_server(port=8002)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

async def process_email(service, msg, email_processor: EmailProcessor, mcp_service: MCPService, vendor_manager: VendorEmailManager, user_id):
    """이메일 처리"""
    try:
        msg_id = msg['id']
        
        # 이미 처리된 이메일인지 확인
        existing_email = await email_processor.check_existing_email(msg_id)
        if existing_email:
            logger.info(f"이미 처리된 이메일입니다: {msg_id}")
            return
            
        # 이메일 내용 및 메타데이터 추출
        email_data, attachments = email_processor.get_message_content(msg_id)
        if not email_data:
            logger.error(f"이메일 내용 추출 실패: {msg_id}")
            return

        # 이메일 방향 결정
        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='metadata',
            metadataHeaders=['Subject', 'From', 'Date', 'To']
        ).execute()
        direction = "outbound" if 'SENT' in message.get('labelIds', []) else "inbound"
        logger.info(f"[DB저장전] direction: {direction}, msg_id: {msg_id}, from: {email_data['sender_email']}, to: {email_data['recipient_email']}")

        # 이메일 데이터 구성
        parsed_message = {
            **email_data,  # 기존 email_data의 모든 필드 포함
            "direction": direction,
            "user_id": user_id,
            "status": "processed",
            "sender_role": "vendor" if direction == "inbound" else "admin"
        }
        
        try:
            # Supabase에 이메일 로그 저장
            await email_processor.save_email_log(parsed_message)
            logger.info(f"이메일 로그 저장 성공: {msg_id}")
            
            # MCP 서비스로 메시지 전송
            await mcp_service.send_message(parsed_message)
            logger.info(f"MCP 서비스로 메시지 전송 성공: {msg_id}")
        except Exception as e:
            logger.error(f"Error saving email log: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            # 실패한 이메일 ID 저장
            await email_processor.save_failed_email(msg_id, str(e))
            raise
            
    except Exception as e:
        logger.error(f"Error processing email {msg['id']}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        # 실패한 이메일 ID 저장
        await email_processor.save_failed_email(msg['id'], str(e))
        raise

async def collect_historical_emails(service, email_processor: EmailProcessor, mcp_service: MCPService, vendor_manager: VendorEmailManager, user_row: dict, months_back=1):
    """과거 이메일 수집"""
    try:
        # 검색 쿼리 생성 (보낸 이메일과 받은 이메일 모두 포함)
        query = f'after:{(datetime.utcnow() - timedelta(days=14)).strftime("%Y/%m/%d")}'
        logger.info(f"Searching emails with query: {query}")
        
        # 받은 이메일 검색
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            q=query,
            maxResults=1200
        ).execute()
        
        messages = results.get('messages', [])
        logger.info(f"INBOX에서 가져온 메시지 수: {len(messages)}")
        
        # 보낸 이메일 검색
        sent_results = service.users().messages().list(
            userId='me',
            labelIds=['SENT'],
            q=query,
            maxResults=1200
        ).execute()
        
        sent_messages = sent_results.get('messages', [])
        
        # 받은 메일 + 보낸 메일
        all_messages = messages + sent_messages
        total_emails = len(all_messages)
        processed = 0
        
        # 메시지를 날짜 기준으로 정렬
        def clean_date_str(date_str):
            import re
            date_str = re.sub(r"([+-][0-9]{4}) ?\([^)]+\)", r"\1", date_str)
            date_str = re.sub(r"([+-][0-9]{4}) ?([+-][0-9]{4})", r"\2", date_str)
            date_str = re.sub(r" ?\([^)]+\)", "", date_str)
            date_str = re.sub(r" +", " ", date_str).strip()
            logger.debug(f"[clean_date_str] after clean: '{date_str}'")
            return date_str

        def get_msg_date(msg):
            try:
                message = service.users().messages().get(
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
                    dt = dt.astimezone(__import__('datetime').timezone.utc)
                    return dt
                except Exception as e:
                    logger.warning(f"Failed to parse date for msg {msg['id']}: {e}")
                    from datetime import timezone
                    return datetime.max.replace(tzinfo=timezone.utc)
            except Exception as e:
                logger.warning(f"Failed to parse date for msg {msg['id']}: {e}")
                from datetime import timezone
                return datetime.max.replace(tzinfo=timezone.utc)

        all_messages.sort(key=get_msg_date)

        for msg in all_messages:
            try:
                processed += 1
                if processed % 100 == 0:
                    logger.info(f"진행률: {processed}/{total_emails} ({(processed/total_emails)*100:.1f}%)")
                    
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                
                headers = message.get("payload", {}).get("headers", [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
                to_email = next((h['value'] for h in headers if h['name'] == 'To'), '')
                logger.info(f"Processing message: {msg['id']}, from: {from_email}, to: {to_email}")
                logger.info(f"벤더 이메일 리스트: {vendor_manager.vendor_emails}")
                result = is_vendor_email(message, vendor_manager)
                logger.info(f"is_vendor_email 결과: {result}")
                if result:
                    await process_email(service, msg, email_processor, mcp_service, vendor_manager, user_row["id"])
            except Exception as e:
                logger.error(f"Error processing message {msg['id']}: {e}")
                # 실패한 이메일 ID 저장
                await email_processor.save_failed_email(msg['id'], str(e))
                continue
            
    except Exception as e:
        logger.error(f"Error collecting historical emails: {e}")
        # 전체 실패 로깅
        await email_processor.log_collection_failure(str(e))

async def watch_new_vendor_emails(service, email_processor, mcp_service, vendor_manager, user_row):
    """10분마다 현재 유저의 purchase_orders에서 vendor_email 조회해 새로운 이메일 있으면 수집"""
    while True:
        try:
            # ✅ 현재 user_id 기준으로 필터링하여 자신의 PO만 가져옴
            result = supabase_service.client.from_("purchase_orders") \
                .select("vendor_email,user_id") \
                .eq("user_id", user_row["id"]) \
                .not_.is_("vendor_email", "null") \
                .execute()
            
            # vendor_email만 추출
            vendor_email_to_user_id = {
                row["vendor_email"].strip().lower(): row["user_id"]
                for row in result.data if row.get("vendor_email")
            }
            db_emails = set(vendor_email_to_user_id.keys())

            # 현재 감시 중인 이메일과 비교해 새로운 이메일 발견
            new_emails = db_emails - vendor_manager.vendor_emails
            if new_emails:
                for email in new_emails:
                    print(f"[NEW VENDOR EMAIL] {email} 발견! 히스토리 수집 시작...")
                    vendor_manager.vendor_emails.add(email)
                    await collect_historical_emails_for_vendor(
                        service, email_processor, mcp_service,
                        vendor_manager, email, user_row["id"]  # ✅ 현재 user_row["id"] 사용
                    )

            await asyncio.sleep(600)  # 10분 주기
        except Exception as e:
            print(f"[watch_new_vendor_emails] Error: {e}")
            await asyncio.sleep(60)

async def collect_historical_emails_for_vendor(service, email_processor, mcp_service, vendor_manager, vendor_email, user_id):
    """특정 벤더 이메일에 대한 과거 이메일만 수집"""
    # Gmail API에서 해당 벤더 이메일과 관련된 과거 이메일만 검색
    query = f'from:{vendor_email} OR to:{vendor_email}'
    print(f"[HISTORY] {vendor_email} 과거 이메일 수집 쿼리: {query}")
    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=300
        ).execute()
        messages = results.get('messages', [])
        for msg in messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                if is_vendor_email(message, vendor_manager):
                    await process_email(service, msg, email_processor, mcp_service, vendor_manager, user_id)  # user_id 전달
            except Exception as e:
                print(f"[HISTORY] Error processing message for {vendor_email}: {e}")
    except Exception as e:
        print(f"[HISTORY] Error collecting historical emails for {vendor_email}: {e}")

async def fetch_and_save_user_inbox(user_row, email_processor):
    try:
        service = get_gmail_service(user_row)
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=100).execute()
        messages = results.get('messages', [])
        for msg in messages:
            try:
                message = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject', 'From', 'Date', 'To']).execute()
                headers = message.get("payload", {}).get("headers", [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
                to_email = next((h['value'] for h in headers if h['name'] == 'To'), '')
                sent_at = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                direction = "inbound"
                content = email_processor.get_message_content(msg['id'])
                parsed_message = {
                    "thread_id": message.get("threadId"),
                    "message_id": msg['id'],
                    "subject": subject,
                    "from": from_email,
                    "to": to_email,
                    "sent_at": sent_at,
                    "body_text": content["body_text"],
                    "direction": direction,
                    "attachments": content["attachments"]
                }
                await email_processor.save_email_log(parsed_message)
            except Exception as e:
                logger.error(f"[{user_row['email']}] Error processing message {msg['id']}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"[{user_row['email']}] Gmail token invalid or expired: {e}", exc_info=True)

async def run_for_user(user_row):
    """
    특정 사용자의 이메일을 감시하는 함수
    """
    try:
        user_email = user_row.get('email')
        if not user_email:
            logger.error("사용자 이메일이 없습니다")
            return

        logger.info(f"[Watcher] 사용자 {user_email}의 이메일 감시 시작")
        
        # Gmail 서비스 가져오기
        service = get_gmail_service(user_row)
        if not service:
            logger.error(f"[Watcher] 사용자 {user_email}의 Gmail 서비스를 초기화할 수 없음")
            return
        
        # VendorManager 생성
        vendor_manager = VendorEmailManager()
        
        # DB에서 사용자의 timezone 가져오기
        user_data = supabase_service.client.from_("users").select("timezone").eq("email", user_email).single().execute()
        timezone = user_data.data.get("timezone", "UTC") if user_data.data else "UTC"
        
        # 이메일 프로세서와 MCP 서비스 생성
        text_processor = TextProcessor()
        user_supabase_service = SupabaseService()  # 각 사용자별 SupabaseService 인스턴스 생성
        email_processor = EmailProcessor(service, text_processor, user_supabase_service)
        mcp_service = MCPService()
        
        # 벤더 이메일 목록 가져오기
        result = supabase_service.client.from_("purchase_orders") \
            .select("vendor_email,user_id") \
            .eq("user_id", user_row["id"]) \
            .not_.is_("vendor_email", "null") \
            .execute()
        
        # vendor_email만 추출하여 VendorManager에 추가
        vendor_emails = {
            row["vendor_email"].strip().lower()
            for row in result.data if row.get("vendor_email")
        }
        vendor_manager.vendor_emails.update(vendor_emails)
        logger.info(f"벤더 이메일 목록: {vendor_manager.vendor_emails}")
        
        # 히스토리 이메일 수집
        logger.info(f"[Watcher] 사용자 {user_email}의 히스토리 이메일 수집 시작")
        await collect_historical_emails(service, email_processor, mcp_service, vendor_manager, user_row, months_back=1)
        logger.info(f"[Watcher] 사용자 {user_email}의 히스토리 이메일 수집 완료")
        
        # 새로운 벤더 이메일 감시 시작
        watch_task = asyncio.create_task(
            watch_new_vendor_emails(service, email_processor, mcp_service, vendor_manager, user_row)
        )
        
        # WatcherManager를 통해 이메일 감시 시작
        watcher_manager.add_watcher(user_email, service, vendor_manager, timezone)
        
        # watch_task 완료 대기
        await watch_task
        
    except Exception as e:
        logger.error(f"[{user_email}] Error in run_for_user: {e}")
        logger.error(traceback.format_exc())

async def main():
    # Supabase에서 email_access_token이 있는 모든 유저 조회
    users = supabase_service.get_users_with_email_access()
    
    if not users:
        logger.error("No users found with email access")
        return
        
    # 각 유저에 대해 병렬 실행 태스크 생성
    tasks = []
    for user in users:
        tasks.append(run_for_user(user))
    
    # 모든 태스크 병렬 실행
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())