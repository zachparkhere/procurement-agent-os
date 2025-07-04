import logging
from datetime import datetime
from supabase import create_client, Client
from config import settings
from storage3.utils import StorageException

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        try:
            logger.info(f"Initializing Supabase client with URL: {settings.SUPABASE_URL}")
            self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            self.storage = self.client.storage
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    async def save_email_log(self, email_data, summary=None):
        """이메일 로그 저장 (중복 방지: thread_id + message_id 조합)"""
        try:
            now = datetime.utcnow()
            thread_id = email_data.get("thread_id")
            message_id = email_data.get("message_id")

            # 1. (thread_id, message_id) 조합이 이미 있는지 확인
            exists = self.client.from_("email_logs") \
                .select("id") \
                .eq("thread_id", thread_id) \
                .eq("message_id", message_id) \
                .execute().data
            if exists:
                logger.info(f"Skip: Already exists for thread_id={thread_id}, message_id={message_id}")
                return None

            # 2. 없으면 insert
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
                "draft_body": email_data.get("draft_body"),
                "status": email_data.get("status"),
                "email_type": email_data.get("email_type"),
                "has_attachment": email_data.get("has_attachment", False),
                "filename": email_data.get("filename"),
                "attachment_types": email_data.get("attachment_types", False),
                "summary": summary if summary else "",
                "sender_role": email_data.get("sender_role"),
                "parsed_delivery_date": email_data.get("parsed_delivery_date"),
                "trigger_reason": email_data.get("trigger_reason"),
                "body": email_data.get("body"),
                "message_id": message_id
            }
            logger.info(f"Insert: New email log for thread_id={thread_id}, message_id={message_id}")
            response = self.client.from_("email_logs").insert(email_log_data).execute()
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
            }).eq("id", email_log_id).execute()
            
            logger.info(f"Delivery date updated successfully for email {email_log_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error updating delivery date: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise 