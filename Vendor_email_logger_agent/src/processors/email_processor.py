import os
import base64
import tempfile
import logging
from datetime import datetime, timezone
import PyPDF2
import docx
import pandas as pd
from Vendor_email_logger_agent.src.utils.text_processor import TextProcessor
from Vendor_email_logger_agent.src.gmail.message_filter import get_email_type
from typing import Dict, List
from po_agent_os.supabase_client import supabase
import re
import traceback

logger = logging.getLogger(__name__)

class EmailProcessor:
    def __init__(self, service, text_processor: TextProcessor, supabase_client):
        self.service = service
        self.text_processor = text_processor
        self.supabase = supabase_client
        self.temp_dir = tempfile.mkdtemp(prefix='email_attachments_')
        self.thread_po_cache = {}  # 스레드 ID를 키로 하는 PO 번호 캐시

    def get_message_content(self, msg_id):
        """
        Extracts email content and metadata for logging.
        Returns a dictionary with body text, headers, summary, delivery date, etc.
        """
        try:
            message = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get('payload', {})
            parts = payload.get('parts', [])
            headers = payload.get('headers', [])

            attachments = []
            body_text = ''

            # Extract body from parts
            def process_part(part):
                nonlocal body_text
                mime_type = part.get('mimeType', '')
                if mime_type in ['text/plain', 'text/html']:
                    if 'body' in part and 'data' in part['body']:
                        data = part['body']['data']
                        decoded_bytes = base64.urlsafe_b64decode(data.encode('UTF-8'))
                        decoded_text = decoded_bytes.decode('utf-8', errors='replace')
                        if mime_type == 'text/plain':
                            body_text = decoded_text
                        elif mime_type == 'text/html' and not body_text:
                            body_text = decoded_text
                if 'filename' in part and part['filename']:
                    attachment = {
                        'filename': part['filename'],
                        'mime_type': mime_type,
                        'attachment_id': part.get('body', {}).get('attachmentId')
                    }
                    attachments.append(attachment)
                if 'parts' in part:
                    for subpart in part['parts']:
                        process_part(subpart)

            if 'body' in payload and 'data' in payload['body']:
                part = payload
                process_part(part)
            else:
                for part in parts:
                    process_part(part)

            # Extract headers
            def extract_header(name):
                return next((h['value'] for h in headers if h['name'].lower() == name.lower()), None)

            from_email = extract_header('From')
            to_email = extract_header('To')
            subject = extract_header('Subject')
            date_str = extract_header('Date')
            thread_id = message.get('threadId')
            message_id = message.get('id')

            # NLP processing
            email_content = {
                'body': body_text,
                'subject': subject
            }
            summary, email_type = self.text_processor.process_email_content(email_content)
            parsed_delivery_date = self.text_processor.parse_delivery_date(email_content)
            
            # PO 번호 추출
            po_number = self.text_processor.find_po_number(
                subject=subject,
                body=body_text,
                attachments=attachments
            )

            # Build email_data dictionary
            email_data = {
                'sender_email': from_email,
                'recipient_email': to_email,
                'subject': subject,
                'body': body_text,
                'summary': summary,
                'email_type': email_type,
                'parsed_delivery_date': parsed_delivery_date,
                'thread_id': thread_id,
                'message_id': message_id,
                'sent_at': date_str,
                'received_at': date_str,
                'has_attachment': bool(attachments),
                'attachment_types': [a['mime_type'] for a in attachments if 'mime_type' in a],
                'filename': attachments[0]['filename'] if attachments else None,
                'po_number': po_number
            }

            return email_data, attachments

        except Exception as e:
            logger.error(f"Error in get_message_content for msg_id {msg_id}: {e}")
            logger.error(traceback.format_exc())
            return None, []

    def download_attachment(self, message_id, attachment_id):
        """첨부파일 다운로드, Supabase Storage에 업로드"""
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            if 'data' in attachment:
                file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))
                
                # 파일을 Supabase Storage에 업로드
                filename = attachment.get('filename')
                bucket_name = 'attachments-from-vendor'  # 버킷 이름 설정
                
                # Supabase Storage에 업로드
                file_path = f"/{filename}"  # 파일 경로 설정
                upload_response = self.supabase.client.storage.from_(bucket_name).upload(file_path, file_data)
                
                if upload_response.status_code == 200:
                    # 파일 업로드 성공 후 public URL을 가져오기
                    public_url = self.supabase.client.storage.from_(bucket_name).get_public_url(file_path).public_url
                    logger.info(f"File uploaded successfully: {public_url}")
                    return public_url  # 업로드된 파일의 URL을 반환
                else:
                    logger.error(f"Error uploading file to Supabase Storage: {upload_response.text}")
                    return None
            return None
        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None

    def extract_text_from_file(self, file_path, mime_type):
        """파일에서 텍스트 추출"""
        try:
            if mime_type == 'application/pdf':
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    return text
                    
            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                doc = docx.Document(file_path)
                return "\n".join([paragraph.text for paragraph in doc.paragraphs])
                
            elif mime_type in ['text/plain', 'text/csv']:
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
                    
            elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                df = pd.read_excel(file_path)
                return df.to_string()
                
            else:
                logger.warning(f"Unsupported file type: {mime_type}")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting text from file: {e}")
            return ""

    async def process_attachment(self, message_id, attachment):
        """첨부파일 처리"""
        try:
            file_data = self.download_attachment(message_id, attachment['attachment_id'])
            if not file_data:
                return None
                
            temp_file = tempfile.NamedTemporaryFile(
                dir=self.temp_dir,
                suffix=os.path.splitext(attachment['filename'])[1],
                delete=False
            )
            temp_file.write(file_data)
            temp_file.close()
            
            try:
                # 파일 텍스트 추출
                text = self.extract_text_from_file(temp_file.name, attachment['mime_type'])
                
                # Supabase Storage에 파일 업로드
                file_path = f"attachments/{message_id}/{attachment['filename']}"
                try:
                    # 파일 업로드
                    with open(temp_file.name, 'rb') as f:
                        self.supabase.client.storage.from_('email-attachments').upload(
                            file_path,
                            f.read(),
                            {"content-type": attachment['mime_type']}
                        )
                    
                    # 파일 URL 가져오기
                    file_url = self.supabase.client.storage.from_('email-attachments').get_public_url(file_path)
                    
                    return {
                        "filename": attachment['filename'],
                        "mime_type": attachment['mime_type'],
                        "text": text,
                        "file_url": file_url,
                        "file_path": file_path
                    }
                except Exception as e:
                    logger.error(f"Error uploading file to Supabase Storage: {e}")
                    return None
                    
            finally:
                # 임시 파일 삭제
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    logger.error(f"Error deleting temp file: {e}")
            
        except Exception as e:
            logger.error(f"Error processing attachment: {e}")
            return None

    async def save_email_log(self, email_data: Dict):
        """이메일 로그를 Supabase에 저장"""
        try:
            # SupabaseService를 통해 이메일 로그 저장
            response = await self.supabase.save_email_log(email_data)
            
            if not response:
                logger.error("Failed to save email log to Supabase")
                raise Exception("Failed to save email log")
            
            logger.info(f"Email log saved successfully: {email_data.get('message_id')}")
            return response.data
        except Exception as e:
            logger.error(f"Error saving email log: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            raise

    def cleanup(self):
        """임시 디렉토리 정리"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")

    async def get_thread_history(self, thread_id: str) -> List[Dict]:
        """
        스레드의 이메일 히스토리 조회
        
        Args:
            thread_id: 스레드 ID
            
        Returns:
            List[Dict]: 스레드의 이메일 목록 (시간순 정렬)
        """
        try:
            # Supabase에서 스레드 이메일 조회
            response = await self.supabase.table("email_logs").select("*").eq("thread_id", thread_id).order("sent_at").execute()
            
            if not response.data:
                return []
                
            return response.data
            
        except Exception as e:
            logger.error(f"Error getting thread history: {e}")
            return []

    def is_new_thread(self, subject: str, thread_id: str) -> bool:
        """
        새로운 스레드인지 확인
        
        Args:
            subject: 이메일 제목
            thread_id: 스레드 ID
            
        Returns:
            bool: 새로운 스레드 여부
        """
        try:
            # Re: 또는 Fwd:로 시작하지 않는 제목이면 새로운 스레드
            if not subject.lower().startswith(('re:', 'fwd:')):
                return True
                
            # 스레드 ID가 없으면 새로운 스레드
            if not thread_id:
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking new thread: {e}")
            return True

    def clean_date_str(self, date_str):
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

    def parse_email_date(self, date_str):
        date_str = self.clean_date_str(date_str)
        logger.debug(f"[parse_email_date] final date_str: '{date_str}'")
        try:
            # Try format with timezone
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            try:
                # Try format without timezone
                dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    # Try format without day name
                    dt = datetime.strptime(date_str, "%d %b %Y %H:%M:%S %z")
                except ValueError:
                    try:
                        # Try format without day name and timezone
                        dt = datetime.strptime(date_str, "%d %b %Y %H:%M:%S")
                        dt = dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        logger.warning(f"Failed to parse date: {date_str}")
                        return datetime.max.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def is_already_logged(self, message_id: str) -> bool:
        try:
            # supabase.client 사용
            existing = self.supabase.client.table("email_logs").select("message_id").eq("message_id", message_id).execute().data
            return bool(existing)
        except Exception as e:
            logger.error(f"Error checking duplicate message_id: {e}")
            return False

    async def process_email(self, message_id: str, thread_id: str, subject: str, body: str, 
                          attachments: List[Dict], from_email: str, to_email: str, 
                          sent_at: str, direction: str) -> Dict:
        """
        Process email and extract necessary information.
        
        Args:
            message_id (str): Email message ID
            thread_id (str): Email thread ID
            subject (str): Email subject
            body (str): Email body
            attachments (List[Dict]): List of attachment information
            from_email (str): Sender email
            to_email (str): Recipient email
            sent_at (str): Sent time
            direction (str): Email direction (inbound/outbound)
            
        Returns:
            Dict: Processed email information
        """
        # Find PO number using thread cache
        po_number = self.text_processor.find_po_number(
            subject=subject,
            body=body,
            attachments=attachments
        )

        processed_email = {
            "message_id": message_id,
            "thread_id": thread_id,
            "subject": subject,
            "body": body,
            "attachments": attachments,
            "from_email": from_email,
            "to_email": to_email,
            "sent_at": sent_at,
            "direction": direction,
            "po_number": po_number
        }

        # Save to Supabase
        if self.supabase:
            await self.save_to_supabase(processed_email)

        return processed_email

    async def save_to_supabase(self, email_data: Dict):
        """
        이메일 데이터를 Supabase에 저장합니다.
        
        Args:
            email_data (Dict): 저장할 이메일 데이터
        """
        try:
            now = datetime.utcnow()
            thread_id = email_data.get("thread_id")
            message_id = email_data.get("message_id")

            # 1. (thread_id, message_id) 조합이 이미 있는지 확인
            exists = self.supabase.client.from_("email_logs") \
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
                "summary": email_data.get("summary", ""),
                "sender_role": email_data.get("sender_role"),
                "parsed_delivery_date": email_data.get("parsed_delivery_date"),
                "body": email_data.get("body"),
                "message_id": message_id,
                "po_number": email_data.get("po_number"),
                "user_id": user_id
            }
            logger.info(f"[INSERT-DEBUG] email_log_data to insert: {email_log_data}")
            response = self.supabase.client.from_("email_logs").insert(email_log_data).execute()
            logger.info(f"[INSERT-DEBUG] insert response: {response}")
            return response
        except Exception as e:
            logger.error(f"Supabase insert error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Email data: {email_data}")
            raise 

    async def check_existing_email(self, message_id: str) -> bool:
        """이메일이 이미 처리되었는지 확인"""
        try:
            existing = self.supabase.client.from_("email_logs") \
                .select("message_id") \
                .eq("message_id", message_id) \
                .execute().data
            return bool(existing)
        except Exception as e:
            logger.error(f"Error checking existing email: {e}")
            return False

    async def save_failed_email(self, message_id: str, error_message: str):
        """실패한 이메일 정보 저장"""
        try:
            failed_email_data = {
                "message_id": message_id,
                "error_message": error_message,
                "failed_at": datetime.utcnow().isoformat()
            }
            response = self.supabase.client.from_("failed_emails").insert(failed_email_data).execute()
            logger.info(f"Failed email saved: {message_id}")
            return response.data
        except Exception as e:
            logger.error(f"Error saving failed email: {e}")
            return None

    async def log_collection_failure(self, error_message: str):
        """이메일 수집 실패 로깅"""
        try:
            failure_data = {
                "error_message": error_message,
                "failed_at": datetime.utcnow().isoformat()
            }
            response = self.supabase.client.from_("collection_failures").insert(failure_data).execute()
            logger.info("Collection failure logged")
            return response.data
        except Exception as e:
            logger.error(f"Error logging collection failure: {e}")
            return None

    async def get_user_id_from_email(self, email: str) -> str:
        """이메일 주소로 사용자 ID 조회"""
        try:
            if not email:
                return None
                
            response = self.supabase.client.from_("users") \
                .select("id") \
                .eq("email", email.lower()) \
                .single() \
                .execute()
                
            if response.data:
                return response.data.get("id")
            return None
        except Exception as e:
            logger.error(f"Error getting user ID from email: {e}")
            return None 