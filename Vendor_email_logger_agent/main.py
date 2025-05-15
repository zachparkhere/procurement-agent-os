import os
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import settings, AgentSettings
import openai

from src.gmail.gmail_watcher import GmailWatcher
from src.gmail.email_collector import EmailCollector
from src.utils.text_processor import TextProcessor
from src.processors.email_processor import EmailProcessor
from src.processors.attachment_processor import AttachmentProcessor
from src.services.mcp_service import MCPService
from src.services.supabase_service import SupabaseService
from src.gmail.message_filter import VendorEmailManager, is_vendor_email

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

def authenticate_gmail():
    """Gmail API 인증"""
    creds = None
    credentials_path = os.path.join(os.path.dirname(__file__), 'credentials', 'credentials.json')
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

async def process_email(service, msg, email_processor: EmailProcessor, mcp_service: MCPService, vendor_manager: VendorEmailManager):
    """이메일 처리"""
    try:
        msg_id = msg['id']
        message = service.users().messages().get(
            userId='me',
            id=msg_id,
            format='metadata',
            metadataHeaders=['Subject', 'From', 'Date', 'To']
        ).execute()
        headers = message.get("payload", {}).get("headers", [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
        from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
        to_email = next((h['value'] for h in headers if h['name'] == 'To'), '')
        sent_at = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        direction = "outbound" if 'SENT' in message.get('labelIds', []) else "inbound"
        logger.info(f"[DB저장전] direction: {direction}, msg_id: {msg_id}, from: {from_email}, to: {to_email}")
        content = email_processor.get_message_content(msg_id)
        parsed_message = {
            "thread_id": message.get("threadId"),
            "message_id": msg_id,
            "subject": subject,
            "from": from_email,
            "to": to_email,
            "sent_at": sent_at,
            "body_text": content["body_text"],
            "direction": direction,
            "attachments": content["attachments"]
        }
        await email_processor.save_email_log(parsed_message)
        await mcp_service.send_message(parsed_message)
    except Exception as e:
        logger.error(f"Error processing email {msg['id']}: {str(e)}")
        raise

async def collect_historical_emails(service, email_processor: EmailProcessor, mcp_service: MCPService, vendor_manager: VendorEmailManager, months_back=3):
    """과거 이메일 수집"""
    try:
        # 검색 쿼리 생성 (보낸 이메일과 받은 이메일 모두 포함)
        query = f'after:{(datetime.utcnow() - timedelta(days=30*months_back)).strftime("%Y/%m/%d")}'
        logger.info(f"Searching emails with query: {query}")
        
        # 받은 이메일 검색
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            q=query,
            maxResults=100
        ).execute()
        
        messages = results.get('messages', [])
        logger.info(f"INBOX에서 가져온 메시지 수: {len(messages)}")
        for msg in messages:
            logger.info(f"INBOX 메시지 ID: {msg['id']}")
        
        # 보낸 이메일 검색
        sent_results = service.users().messages().list(
            userId='me',
            labelIds=['SENT'],
            q=query,
            maxResults=100
        ).execute()
        
        sent_messages = sent_results.get('messages', [])
        # logger.info(f"Found {len(sent_messages)} sent messages")
        
        # 받은 메일 + 보낸 메일
        all_messages = messages + sent_messages
        
        # 메시지를 날짜 기준으로 정렬
        def clean_date_str(date_str):
            import re
            # 1. +0000 (UTC) → +0000
            date_str = re.sub(r"([+-][0-9]{4}) ?\([^)]+\)", r"\1", date_str)
            # 2. +0000 +0000 → 마지막만 남기기
            date_str = re.sub(r"([+-][0-9]{4}) ?([+-][0-9]{4})", r"\2", date_str)
            # 3. 남은 괄호 및 앞 공백 제거
            date_str = re.sub(r" ?\([^)]+\)", "", date_str)
            # 4. 여러 공백 정리
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
                    dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                except ValueError:
                    try:
                        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
                        from datetime import timezone
                        dt = dt.replace(tzinfo=timezone.utc)
                    except Exception as e:
                        logger.warning(f"Failed to parse date for msg {msg['id']}: {e}")
                        # 항상 timezone-aware로 반환
                        from datetime import timezone
                        return datetime.max.replace(tzinfo=timezone.utc)
                dt = dt.astimezone(__import__('datetime').timezone.utc)
                return dt
            except Exception as e:
                logger.warning(f"Failed to parse date for msg {msg['id']}: {e}")
                from datetime import timezone
                return datetime.max.replace(tzinfo=timezone.utc)

        all_messages.sort(key=get_msg_date)

        for msg in all_messages:
            try:
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date', 'To']
                ).execute()
                # 필터 전 정보 출력
                headers = message.get("payload", {}).get("headers", [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                from_email = next((h['value'] for h in headers if h['name'] == 'From'), '')
                to_email = next((h['value'] for h in headers if h['name'] == 'To'), '')
                logger.info(f"Processing message: {msg['id']}, from: {from_email}, to: {to_email}")
                logger.info(f"벤더 이메일 리스트: {vendor_manager.vendor_emails}")
                result = is_vendor_email(message, vendor_manager)
                logger.info(f"is_vendor_email 결과: {result}")
                if result:
                    await process_email(service, msg, email_processor, mcp_service, vendor_manager)
            except Exception as e:
                logger.error(f"Error processing message {msg['id']}: {e}")
                continue
            
    except Exception as e:
        logger.error(f"Error collecting historical emails: {e}")

async def watch_new_vendor_emails(service, email_processor, mcp_service, vendor_manager):
    """10분마다 purchase_orders 테이블에서 vendor_email을 조회해 새로운 이메일이 있으면 히스토리 수집 트리거"""
    supabase_service = SupabaseService()
    while True:
        try:
            # DB에서 vendor_email 목록 재조회
            result = supabase_service.client.from_("purchase_orders").select("vendor_email").not_.is_("vendor_email", "null").execute()
            db_emails = set(row["vendor_email"].strip().lower() for row in result.data if row.get("vendor_email"))
            # 새로 발견된 이메일
            new_emails = db_emails - vendor_manager.vendor_emails
            if new_emails:
                for email in new_emails:
                    print(f"[NEW VENDOR EMAIL] {email} 발견! 히스토리 수집 시작...")
                    # 벤더 이메일 set에 추가
                    vendor_manager.vendor_emails.add(email)
                    # 해당 이메일에 대한 히스토리 수집 트리거
                    # (collect_historical_emails는 전체를 도는 구조라면, 이메일 필터링 추가 필요)
                    # 아래는 예시: 해당 이메일만 대상으로 수집
                    await collect_historical_emails_for_vendor(service, email_processor, mcp_service, vendor_manager, email)
            await asyncio.sleep(600)  # 10분마다 반복
        except Exception as e:
            print(f"[watch_new_vendor_emails] Error: {e}")
            await asyncio.sleep(60)

async def collect_historical_emails_for_vendor(service, email_processor, mcp_service, vendor_manager, vendor_email):
    """특정 벤더 이메일에 대한 과거 이메일만 수집"""
    # Gmail API에서 해당 벤더 이메일과 관련된 과거 이메일만 검색
    # (예시: from:vendor_email OR to:vendor_email)
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
                    await process_email(service, msg, email_processor, mcp_service, vendor_manager)
            except Exception as e:
                print(f"[HISTORY] Error processing message for {vendor_email}: {e}")
    except Exception as e:
        print(f"[HISTORY] Error collecting historical emails for {vendor_email}: {e}")

async def main():
    """메인 함수"""
    try:
        # 벤더 이메일 CSV 파일 로드
        vendor_csv_path = settings.VENDOR_CSV_PATH
        logger.info(f"Vendor CSV path from .env: {vendor_csv_path}")
        
        if not vendor_csv_path:
            logger.error("VENDOR_CSV_PATH not set in .env file")
            return
            
        if not os.path.exists(vendor_csv_path):
            logger.error(f"Vendor email CSV file not found at {vendor_csv_path}")
            return
            
        # VendorEmailManager 인스턴스 생성 (DB + CSV)
        vendor_manager = VendorEmailManager(csv_path=settings.VENDOR_CSV_PATH)
        
        # Gmail 서비스 인증
        service = authenticate_gmail()
        if not service:
            logger.error("Failed to authenticate Gmail service")
            return
        
        # 서비스 초기화
        text_processor = TextProcessor()
        mcp_service = MCPService()
        supabase_service = SupabaseService()
        email_processor = EmailProcessor(service, text_processor, supabase_client=supabase_service)
        
        # 실시간 이메일 감시 시작
        watcher = GmailWatcher(service, vendor_manager)
        logger.info("GmailWatcher initialized")
        
        # 기존 서비스 초기화 및 워커 실행
        await asyncio.gather(
            collect_historical_emails(service, email_processor, mcp_service, vendor_manager, months_back=1),
            watch_new_vendor_emails(service, email_processor, mcp_service, vendor_manager),
            # 실시간 이메일 감시
            asyncio.to_thread(watcher.watch, lambda email: asyncio.create_task(process_email(service, email, email_processor, mcp_service, vendor_manager)))
        )
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        if 'email_processor' in locals():
            email_processor.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
