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
        이메일 내용 추출
        이메일 본문과 첨부파일 정보를 추출
        text/plain, text/html 형식의 본문 처리
        첨부파일 정보 수집
        """
        try:
            message = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get("payload", {})
            parts = payload.get("parts", [])
            
            attachments = []
            body_text = ""
            
            def process_part(part):
                nonlocal body_text
                mime_type = part.get("mimeType", "")
                
                if mime_type in ["text/plain", "text/html"]:
                    if "body" in part and "data" in part["body"]:
                        data = part["body"]["data"]
                        decoded_bytes = base64.urlsafe_b64decode(data.encode('UTF-8'))
                        decoded_text = decoded_bytes.decode('utf-8', errors='replace')
                        if mime_type == "text/plain":
                            body_text = decoded_text
                        elif mime_type == "text/html" and not body_text:
                            body_text = decoded_text
                
                if "filename" in part and part["filename"]:
                    attachment = {
                        "filename": part["filename"],
                        "mime_type": mime_type,
                        "attachment_id": part.get("body", {}).get("attachmentId")
                    }
                    attachments.append(attachment)
                
                if "parts" in part:
                    for subpart in part["parts"]:
                        process_part(subpart)
            
            if "body" in payload and "data" in payload["body"]:
                data = payload["body"]["data"]
                decoded_bytes = base64.urlsafe_b64decode(data.encode('UTF-8'))
                body_text = decoded_bytes.decode('utf-8', errors='replace')
            else:
                for part in parts:
                    process_part(part)
            
            return {
                "body_text": body_text,
                "attachments": attachments
            }
        except Exception as e:
            logger.error(f"Error getting message content: {e}")
            return {"body_text": "", "attachments": []}

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
                upload_response = self.supabase.storage.from_(bucket_name).upload(file_path, file_data)
                
                if upload_response.status_code == 200:
                    # 파일 업로드 성공 후 public URL을 가져오기
                    public_url = self.supabase.storage.from_(bucket_name).get_public_url(file_path).public_url
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
                        self.supabase.storage.from_('email-attachments').upload(
                            file_path,
                            f.read(),
                            {"content-type": attachment['mime_type']}
                        )
                    
                    # 파일 URL 가져오기
                    file_url = self.supabase.storage.from_('email-attachments').get_public_url(file_path)
                    
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

    async def save_email_log(self, message_data):
        """이메일 로그를 데이터베이스에 저장"""
        try:
            now = datetime.utcnow()
            
            # 저장 전 중복 체크
            existing = self.supabase.client.from_("email_logs").select("message_id").eq("message_id", message_data["message_id"]).execute().data
            if existing:
                logger.info(f"Duplicate message_id {message_data['message_id']} detected, skipping save.")
                return None

            # PO 번호 추출 (정규식+LLM)
            po_number = message_data.get("po_number")
            attachments = message_data.get("attachments", [])
            if not po_number:
                po_number = self.text_processor.find_po_number(
                    subject=message_data.get("subject", ""),
                    body=message_data.get("body_text", ""),
                    attachments=attachments
                )
                message_data["po_number"] = po_number
            print(f"[DEBUG] 추출된 PO 번호: {po_number}")

            # 이메일 내용 처리
            summary, email_type = self.text_processor.process_email_content(message_data)
            logger.info(f"Generated email type: {email_type}")
            
            # 첨부파일 처리
            has_attachment = len(attachments) > 0
            attachment_types = [att["mime_type"] for att in attachments]
            filenames = [att["filename"] for att in attachments]
            
            processed_attachments = []
            if has_attachment:
                for attachment in attachments:
                    processed = await self.process_attachment(message_data['message_id'], attachment)
                    if processed:
                        processed_attachments.append(processed)
            
            # 기존 배송 날짜 조회
            existing_delivery_date = None
            if message_data.get("thread_id"):
                thread_history = await self.supabase.get_thread_history(message_data["thread_id"])
                if thread_history:
                    # 가장 최근의 배송 날짜 찾기
                    for email in reversed(thread_history):
                        if email.get("parsed_delivery_date"):
                            existing_delivery_date = email["parsed_delivery_date"]
                            received_at = email["received_at"]
                            break
            
            # 배송 날짜 파싱
            delivery_date = self.text_processor.parse_delivery_date(
                message_data.get("body_text", ""),
                processed_attachments,
                existing_delivery_date,
                message_data.get("received_at")
            )
            logger.info(f"Parsed delivery date: {delivery_date}")
            
            # 이메일 방향에 따른 처리
            direction = message_data.get("direction")
            status = "sent" if direction == "outbound" else "received"
            sender_role = "admin" if direction == "outbound" else "vendor"
            
            # 이메일 방향에 따른 시간 설정
            sent_at = message_data.get("sent_at") if direction == "outbound" else None
            received_at = message_data.get("sent_at") if direction == "inbound" else None  # sent_at이 실제 이메일 수신 시간
            
            # 이메일 로그 데이터 준비
            email_log_data = {
                "thread_id": message_data.get("thread_id"),
                "po_number": po_number,
                "direction": direction,
                "sender_email": message_data.get("from"),
                "recipient_email": message_data.get("to"),
                "subject": message_data.get("subject"),
                "sent_at": sent_at,  # outbound인 경우에만 설정, 보낸 시간
                "created_at": now.isoformat(),  # DB에 저장된 시간
                "updated_at": now.isoformat(),  # DB 업데이트 시간
                "received_at": received_at,  # inbound인 경우에만 설정, 받은 시간
                "status": status,  # outbound면 "sent", inbound면 "received"
                "email_type": email_type,
                "has_attachment": has_attachment,
                "filename": filenames[0] if filenames else None,
                "attachment_types": attachment_types,
                "summary": summary if summary else "",
                "sender_role": sender_role,  # outbound면 "admin", inbound면 "vendor"
                "parsed_delivery_date": delivery_date,
                "body": message_data.get("body_text"),
                "message_id": message_data.get("message_id"),  # ✅ message_id도 항상 저장
                "user_id": message_data.get("user_id")  # user_id 추가
            }
            
            # Supabase에 저장 (중복 체크/업데이트 기준은 thread_id)
            response = await self.supabase.save_email_log(email_log_data, summary)
            if not response:
                logger.error("Failed to save email log to Supabase")
                return False
                
            # 첨부파일 저장
            if processed_attachments:
                for attachment in processed_attachments:
                    attachment_data = {
                        "email_log_id": response.data[0]['id'],
                        "filename": attachment['filename'],
                        "mime_type": attachment['mime_type'],
                    }
                    await self.supabase.save_attachment(response.data[0]['id'], attachment_data)
            
            return response
            
        except Exception as e:
            logger.error(f"Error saving email log: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return None

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
            # supabase.client 대신 supabase 직접 사용
            existing = self.supabase.table("email_logs").select("message_id").eq("message_id", message_id).execute().data
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
            data = {
                "message_id": email_data["message_id"],
                "thread_id": email_data["thread_id"],
                "subject": email_data["subject"],
                "body": email_data["body"],
                "from_email": email_data["from_email"],
                "to_email": email_data["to_email"],
                "sent_at": email_data["sent_at"],
                "direction": email_data["direction"],
                "po_number": email_data["po_number"],
                "attachments": email_data["attachments"]
            }
            
            # supabase.client 대신 supabase 직접 사용
            result = self.supabase.table("email_logs").insert(data).execute()
            return result
        except Exception as e:
            logger.error(f"Error saving email to Supabase: {e}")
            raise 