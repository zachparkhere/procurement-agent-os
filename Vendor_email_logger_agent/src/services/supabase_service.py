import logging
from datetime import datetime
from po_agent_os.supabase_client import supabase
from supabase import Client
from Vendor_email_logger_agent.config import settings
from storage3.utils import StorageException
from typing import Dict

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        try:
            logger.info(f"Initializing Supabase client with URL: {settings.SUPABASE_URL}")
            self.client: Client = supabase
            self.storage = self.client.storage
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    async def get_user_id_from_email(self, email: str) -> str | None:
        """이메일 주소로부터 user_id를 조회합니다."""
        try:
            if not email:
                return None
                
            response = self.client.from_("users") \
                .select("id") \
                .eq("email", email) \
                .execute()
                
            if response.data and len(response.data) > 0:
                return response.data[0]["id"]
            return None
            
        except Exception as e:
            logger.error(f"Error getting user_id for email {email}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            return None

    async def save_email_log(self, email_data, summary=None):
        """이메일 로그 저장 (중복 방지: thread_id + message_id 조합)"""
        try:
            now = datetime.utcnow()
            thread_id = email_data.get("thread_id")
            message_id = email_data.get("message_id")

            # 1. (thread_id, message_id) 조합이 이미 있는지 확인
            exists = self.client.from_("email_logs") \
                .select("message_id") \
                .eq("thread_id", thread_id) \
                .eq("message_id", message_id) \
                .execute().data
            if exists:
                logger.info(f"Skip: Already exists for thread_id={thread_id}, message_id={message_id}")
                return None

            # 2. user_id 우선 할당, 없으면 sender/recipient_email로 매핑
            user_id = email_data.get("user_id")
            if not user_id:
                user_id = await self.get_user_id_from_email(email_data.get("sender_email"))
                if not user_id:
                    user_id = await self.get_user_id_from_email(email_data.get("recipient_email"))
            logger.info(f"Mapped user_id {user_id} for email {email_data.get('sender_email') or email_data.get('recipient_email')}")

            # 3. email_log_data 생성 및 저장
            email_log_data = {
                "thread_id": thread_id,
                "direction": email_data.get("direction", "inbound"),
                "sender_email": email_data.get("sender_email"),
                "recipient_email": email_data.get("recipient_email"),
                "subject": email_data.get("subject"),
                "sent_at": email_data.get("sent_at"),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "received_at": email_data.get("received_at"),
                "status": email_data.get("status"),
                "email_type": email_data.get("email_type"),
                "has_attachment": email_data.get("has_attachment", False),
                "filename": email_data.get("filename"),
                "attachment_types": email_data.get("attachment_types", False),
                "summary": summary if summary else "",
                "sender_role": email_data.get("sender_role"),
                "parsed_delivery_date": email_data.get("parsed_delivery_date"),
                "body": email_data.get("body"),
                "message_id": message_id,
                "po_number": email_data.get("po_number"),
                "user_id": user_id
            }
            logger.info(f"[INSERT-DEBUG] email_log_data to insert: {email_log_data}")
            response = self.client.from_("email_logs").insert(email_log_data).execute()
            logger.info(f"[INSERT-DEBUG] insert response: {response}")
            return response
        except Exception as e:
            logger.error(f"Supabase insert error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Email data: {email_data}")
            raise

    async def save_attachment(self, email_log_id, attachment_data):
        """첨부파일 데이터 저장"""
        try:
            attachment_data["email_log_id"] = email_log_id
            logger.info(f"Attempting to save attachment: {attachment_data['filename']}")
            logger.debug(f"Attachment data: {attachment_data}")
            
            response = self.client.from_("email_attachments").insert(attachment_data).execute()
            logger.info(f"Attachment saved successfully: {attachment_data['filename']}")
            return response
            
        except Exception as e:
            logger.error(f"Error saving attachment: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Attachment data: {attachment_data}")
            raise

    async def get_thread_history(self, thread_id: str):
        """스레드의 이메일 히스토리 조회"""
        try:
            logger.info(f"Fetching thread history for thread_id: {thread_id}")
            response = self.client.from_("email_logs").select("*").eq("thread_id", thread_id).order("sent_at").execute()
            logger.info(f"Found {len(response.data)} emails in thread")
            return response.data
        except Exception as e:
            logger.error(f"Error getting thread history: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            return []

    async def update_delivery_date(self, email_log_id: int, new_date: str):
        """배송 날짜 업데이트"""
        try:
            logger.info(f"Updating delivery date for email {email_log_id} to {new_date}")
            response = self.client.from_("email_logs").update({
                "parsed_delivery_date": new_date,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("message_id", email_log_id).execute()
            
            logger.info(f"Delivery date updated successfully for email {email_log_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error updating delivery date: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def get_users_with_email_access(self):
        """이메일 접근 권한이 있는 모든 사용자를 조회합니다."""
        try:
            logger.info("Fetching users with email access")
            response = self.client.from_("users") \
                .select("id, email, email_access_token, email_refresh_token, email_token_expiry") \
                .not_.is_("email_access_token", "null") \
                .execute()
            
            if not response.data:
                logger.warning("No users found with email access")
                return []
                
            logger.info(f"Found {len(response.data)} users with email access")
            return response.data
            
        except Exception as e:
            logger.error(f"Error getting users with email access: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            return []

    async def insert_email_log(self, email_data: Dict) -> Dict:
        """이메일 로그를 Supabase에 저장"""
        try:
            logger.info(f"[CHECK] summary before constructing email_log_data: {email_data.get('summary')}")
            
            email_log_data = {
                "thread_id": email_data.get("thread_id"),
                "direction": email_data.get("direction", "inbound"),
                "sender_email": email_data.get("sender_email"),
                "recipient_email": email_data.get("recipient_email"),
                "subject": email_data.get("subject"),
                "sent_at": email_data.get("sent_at"),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "received_at": email_data.get("received_at"),
                "status": email_data.get("status"),
                "email_type": email_data.get("email_type"),
                "has_attachment": email_data.get("has_attachment", False),
                "filename": email_data.get("filename"),
                "attachment_types": email_data.get("attachment_types", False),
                "summary": email_data.get("summary", ""),
                "sender_role": email_data.get("sender_role"),
                "parsed_delivery_date": email_data.get("parsed_delivery_date"),
                "body": email_data.get("body"),
                "message_id": email_data.get("message_id"),
                "po_number": email_data.get("po_number"),
                "user_id": email_data.get("user_id")
            }
            
            logger.info(f"[CHECK] email_log_data['summary']: {email_log_data.get('summary')}")
            
            response = self.client.from_("email_logs").insert(email_log_data).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error inserting email log: {str(e)}")
            raise 