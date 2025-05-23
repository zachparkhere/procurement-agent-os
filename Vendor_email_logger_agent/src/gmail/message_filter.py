# gmail/message_filter.py
import re, csv, os, logging
from typing import Dict, List, Set
from pathlib import Path
from procurement_agent_os.supabase_client import supabase
from dotenv import load_dotenv
from Vendor_email_logger_agent.config import settings

# Load environment variables
load_dotenv()
# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = supabase

# 로깅 설정
logger = logging.getLogger(__name__)

# 벤더 이메일 도메인 목록
# VENDOR_DOMAINS = [
#     'vendor.com',
#     'supplier.com',
#     'manufacturer.com'
# ]

# 구매 관련 키워드
PURCHASE_KEYWORDS = {
    # 'purchase_request': [
    #     'purchase request',
    #     'pr request',
    #     '구매 요청',
    #     '구매요청서',
    #     '구매 의뢰',
    #     '구매의뢰서'
    # ],
    'purchase_order': [
        'purchase order',
        'po',
        'po number',
        '구매 주문',
        '구매주문서',
        '발주서',
        '발주'
    ],
    'vendor_communication': [
        'quote',
        'quotation',
        '견적',
        '견적서',
        'invoice',
        '청구서',
        'delivery',
        '배송',
        'shipment',
        '출하',
        'payment',
        '결제',
        'settlement',
        '정산'
    ]
}

class VendorEmailManager:
    def __init__(self, csv_path: str = None):
        self.vendor_emails: Set[str] = set()
        self.load_from_database()
        if csv_path:
            self.load_from_csv(csv_path)
    
    def load_from_database(self):
        """데이터베이스에서 벤더 이메일 로드"""
        try:
            # purchase_orders 테이블에서 vendor_email이 있는 레코드 조회
            response = supabase.table("purchase_orders").select("vendor_email").not_.is_("vendor_email", "null").execute()
            
            for row in response.data:
                email = row.get("vendor_email", "").strip().lower()
                if email and '@' in email:
                    self.vendor_emails.add(email)
                    
            logger.info(f"Loaded {len(self.vendor_emails)} vendor emails from database")
            
        except Exception as e:
            logger.error(f"Error loading vendor emails from database: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def load_from_csv(self, csv_path: str):
        """CSV 파일에서 벤더 이메일 로드"""
        try:
            if not os.path.exists(csv_path):
                logger.warning(f"Vendor email CSV file not found: {csv_path}")
                return
                
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                initial_count = len(self.vendor_emails)
                
                for row in reader:
                    email = row.get('vendor_email', '').strip().lower()
                    if email and '@' in email:
                        self.vendor_emails.add(email)
                    else:
                        logger.warning(f"Invalid email in row: {row}")
                        
            new_count = len(self.vendor_emails) - initial_count
            logger.info(f"Loaded {new_count} additional vendor emails from CSV")
            logger.info(f"Total unique vendor emails: {len(self.vendor_emails)}")
            
        except Exception as e:
            logger.error(f"Error loading vendor emails from CSV: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def is_vendor_email(self, email: str) -> bool:
        """이메일이 벤더 이메일인지 확인"""
        email = email.lower()
        is_vendor = email in self.vendor_emails
        if is_vendor:
            logger.info(f"Is vendor: {is_vendor}")
        return is_vendor

def extract_email_address(email_header: str) -> str:
    """이메일 헤더에서 이메일 주소 추출"""
    email_match = re.search(r'<([^>]+)>', email_header)
    if email_match:
        return email_match.group(1)
    return email_header.strip()

def is_vendor_email(email_data: Dict, vendor_manager) -> bool:
    """
    이메일이 벤더 이메일인지 확인 (보낸 이메일과 받은 이메일 모두 처리)
    """
    try:
        # 이메일 헤더 추출
        headers = email_data.get("payload", {}).get("headers", [])
        from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        to_header = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
        
        # 이메일 주소 추출
        from_email = extract_email_address(from_header)
        to_email = extract_email_address(to_header)
        
        # 보낸 이메일인지 확인 (Gmail API의 SENT 라벨 확인)
        is_outbound = 'SENT' in email_data.get('labelIds', [])
        
        if is_outbound:
            # 보낸 이메일인 경우, 수신자가 벤더인지 확인
            if vendor_manager.is_vendor_email(to_email):
                return True
        else:
            # 받은 이메일인 경우, 발신자가 벤더인지 확인
            if vendor_manager.is_vendor_email(from_email):
                return True
        return False
        
    except Exception as e:
        logger.error(f"Error checking vendor email: {e}")
        return False

def get_email_type(email_data: Dict) -> str:
    """
    이메일 유형 반환 (purchase_request, purchase_order, vendor_communication)
    """
    headers = email_data.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '').lower()
    
    # if any(keyword in subject for keyword in PURCHASE_KEYWORDS['purchase_request']):
    #     return 'purchase_request'
    if any(keyword in subject for keyword in PURCHASE_KEYWORDS['purchase_order']):
        return 'purchase_order'
    elif any(keyword in subject for keyword in PURCHASE_KEYWORDS['vendor_communication']):
        return 'vendor_communication'
    
    return 'other'
