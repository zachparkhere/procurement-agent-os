import os
import base64
import tempfile
import logging
import PyPDF2
import docx
import pandas as pd
from supabase import create_client, Client
from Vendor_email_logger_agent.src.utils.text_processor import TextProcessor
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class AttachmentProcessor:
    def __init__(self, service, text_processor: TextProcessor, supabase_url: str, supabase_anon_key: str):
        self.service = service
        self.text_processor = text_processor
        self.temp_dir = tempfile.mkdtemp(prefix='email_attachments_')

        # Supabase 클라이언트 초기화
        self.supabase: Client = create_client(supabase_url, supabase_anon_key)
        self.bucket_name = "your-bucket-name"  # 여기서 버킷 이름을 지정

    async def download_attachment(self, message_id: str, attachment_id: str, filename: str) -> Optional[str]:
        """
        Download attachment from Gmail and save to Supabase storage
        
        Args:
            message_id (str): Gmail message ID
            attachment_id (str): Gmail attachment ID
            filename (str): Original filename
            
        Returns:
            Optional[str]: Path to downloaded file or None if failed
        """
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            
            # Download attachment
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            if not attachment:
                logger.error(f"Failed to get attachment {attachment_id} from message {message_id}")
                return None
                
            # Decode attachment data
            data = attachment['data']
            file_data = base64.urlsafe_b64decode(data)
            
            # Save to temporary file
            temp_path = os.path.join(self.temp_dir, unique_filename)
            with open(temp_path, 'wb') as f:
                f.write(file_data)
                
            # Upload to Supabase storage
            try:
                with open(temp_path, 'rb') as f:
                    self.supabase.storage.from_('attachments-from-vendor').upload(
                        unique_filename,
                        f
                    )
            except Exception as e:
                if 'Duplicate' in str(e):
                    logger.info(f"File {unique_filename} already exists in storage")
                    return unique_filename
                else:
                    raise
                    
            return unique_filename
            
        except Exception as e:
            logger.error(f"Error downloading attachment: {e}")
            return None
        finally:
            # Clean up temporary file
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)

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
            file_data = self.download_attachment(message_id, attachment['attachment_id'], attachment['filename'])
            if not file_data:
                return None
                
            # 임시 파일 생성 후 데이터 쓰기
            temp_file = tempfile.NamedTemporaryFile(
                dir=self.temp_dir,
                suffix=os.path.splitext(attachment['filename'])[1],
                delete=False
            )
            temp_file.write(file_data)
            temp_file.close()

            # 텍스트 추출
            try:
                text = self.extract_text_from_file(temp_file.name, attachment['mime_type'])
                embedding = self.text_processor.get_embedding(text) if text else None
                
                # Supabase에 파일 업로드
                file_name = attachment['filename']
                with open(temp_file.name, 'rb') as file:
                    response = self.supabase.storage.from_(self.bucket_name).upload(file_name, file)
                    if response.status_code == 200:
                        logger.info(f"File '{file_name}' uploaded to Supabase successfully.")
                        file_url = response.data['Key']  # 업로드된 파일 URL을 저장
                    else:
                        logger.error(f"Failed to upload file '{file_name}' to Supabase.")
                        file_url = None
                
                return {
                    "filename": attachment['filename'],
                    "mime_type": attachment['mime_type'],
                    "text": text,
                    "embedding": embedding,
                    "file_url": file_url  # URL 포함
                }
                
            finally:
                os.unlink(temp_file.name)
            
        except Exception as e:
            logger.error(f"Error processing attachment: {e}")
            return None

    def cleanup(self):
        """임시 디렉토리 정리"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}") 
