# utils/text_processor.py
from openai import OpenAI
from typing import Dict, List, Tuple
import numpy as np
from config import settings
import tiktoken
import logging
from datetime import datetime, timezone
import re

logger = logging.getLogger(__name__)

class TextProcessor:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 8192  # GPT-4-turbo의 최대 토큰 수
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산"""
        return len(self.encoding.encode(text))
    
    def truncate_text(self, text: str) -> str:
        """텍스트를 최대 토큰 수에 맞게 자르기"""
        tokens = self.encoding.encode(text)
        if len(tokens) > self.max_tokens:
            tokens = tokens[:self.max_tokens]
        return self.encoding.decode(tokens)
    
    def get_embedding(self, text: str) -> List[float]:
        """텍스트의 임베딩 벡터 생성"""
        try:
            # 텍스트가 너무 길면 자르기
            truncated_text = self.truncate_text(text)
            
            response = self.client.embeddings.create(
                input=truncated_text,
                model="text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []
    
#     def summarize_text(self, text: str) -> str:
#         """텍스트 요약"""
#         try:
#             # 텍스트가 너무 길면 자르기
#             truncated_text = self.truncate_text(text)
            
#             response = self.client.chat.completions.create(
#                 model="gpt-3.5-turbo",
#                 messages=[
#                     {
#                         "role": "system", 
#                         "content": """You are a procurement expert. Your task is to summarize emails in a way that helps procurement professionals quickly understand the key points and take necessary actions. Focus on:
# 1. The main purpose of the email (request, order, inquiry, etc.)
# 2. Key dates and deadlines
# 3. Important quantities, prices, or specifications
# 4. Any required actions or responses
# 5. Potential issues or concerns
# Keep the summary concise and actionable."""
#                     },
#                     {
#                         "role": "user", 
#                         "content": f"Please summarize this procurement-related email:\n\n{truncated_text}"
#                     }
#                 ],
#                 max_tokens=500,
#                 temperature=0.3
#             )
#             return response.choices[0].message.content.strip()
#         except Exception as e:
#             logger.error(f"Error summarizing text: {e}")
#             return ""
    
    def process_email_content(self, message_data):
        """이메일 내용 처리 (요약)"""
        try:
            body_text = message_data.get("body_text", "")
            if not body_text:
                return "", ""
                
            # LLM을 사용하여 요약 생성
            prompt = f"""
You are a procurement specialist assistant.

Your task is to analyze the following email and deliver two outputs:

1. **Summary** (1–3 clear sentences):  
   Focus specifically on the procurement-related **action** or **request**.  
   Exclude unnecessary greetings, background stories, or non-actionable information.  
   Be direct and practical as a procurement professional would expect.

2. **Type** (short 2–3 word category):  
   Provide a short but clear 2–3 word phrase that best describes the critical **action and purpose** of this email for a procurement specialist.  
   Avoid vague or generic words. Be specific and professional.

Examples:
- delivery delay
- delay confirmation
- purchase order
- payment request
- contract negotiation
- shipment inquiry
- invoice issue

Pick a phrase that immediately tells a procurement professional what the email is about.


Format your response exactly like this:
---
SUMMARY: [your 1–3 sentence summary]  
TYPE: [your single word]
---

Email content:
{body_text}

"""
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a procurement specialist analyzing emails."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.0
            )
            
            result = response.choices[0].message.content.strip()
            
            # 결과 파싱
            summary = ""
            email_type = ""
            
            for line in result.split('\n'):
                if line.startswith('SUMMARY:'):
                    summary = line.replace('SUMMARY:', '').strip()
                elif line.startswith('TYPE:'):
                    email_type = line.replace('TYPE:', '').strip().lower()
            
            return summary, email_type
            
        except Exception as e:
            logger.error(f"Error processing email content: {e}")
            return "", ""
    
    def parse_delivery_date(self, email_content: str, attachments: List[Dict] = None, existing_date: str = None, received_date: str = None) -> str:
        """
        이메일 본문과 첨부파일에서 배송 날짜를 파싱
        
        Args:
            email_content: 이메일 본문
            attachments: 첨부파일 목록 (선택사항)
            existing_date: 기존 배송 날짜 (선택사항)
            sent_date: 보낸 날짜 (선택사항)
        Returns:
            str: ISO 형식의 날짜 문자열 (YYYY-MM-DD)
        """
        print(f"existing_date: {existing_date}, received_date: {received_date}")
        try:
            # 첨부파일 내용 추출
            attachment_texts = []
            if attachments:
                for attachment in attachments:
                    if "text" in attachment:
                        attachment_texts.append(attachment["text"])
            
            # LLM에 전달할 프롬프트 구성
            prompt = f"""
You are a procurement expert. Analyze the email body and attachments to find the latest delivery date.

You must carefully read both the email content and the attachment texts to extract the most accurate **delivery date**, also known as "requested delivery date", "expected delivery date", "delivery by", or similar expressions.

The delivery date may be explicitly stated (e.g., "delivery date: 2025-04-30") or implied using relative expressions (e.g., "delayed by 2 days", "delivery next Friday").

Use the following rules carefully:

Rules for Choosing the Delivery Date:
1. If multiple delivery dates are mentioned, ALWAYS choose the LATEST one.
2. If a delivery date change is described (e.g., "delivery moved from April 24 to April 30", "delayed by a week"), ALWAYS use the NEW (updated) delivery date.
3. If a clear explicit date is written, use it ONLY IF there is no later delivery update.
4. Even if an explicit (clearly written) delivery date exists, if a LATER delay or reschedule is mentioned (even indirectly), calculate and use the NEW latest delivery date instead.
5. When calculating a delivery date from a **relative expression** (e.g., "2 days later", "delayed by one week", "next Friday"):
    - Prefer using the **reference_date** (most recent scheduled delivery date) as the base.
    - If no valid reference_date is available, use the **received_date** (email sent/received date) as the base.
6. If no valid delivery date can be determined, return only the word **"Null"** (case-sensitive).
7. Final output must be ONLY a date in **YYYY-MM-DD** format, without any other text.

Examples:
- "Original delivery was 2025-04-24, changed to 2025-04-30" → **2025-04-30**
- "First batch delivery on 2025-04-24, second batch on 2025-04-30" → **2025-04-30**
- "Shipment delayed by 2 days" (reference_date = 2025-04-26) → **2025-04-28**
- "Delivery next Friday" (received_date = 2025-04-26) → **2025-05-02**
- "Delivery date: 2025-04-26", but later mentions "delayed by 5 days" → **2025-05-01** (even though explicit 4/26 exists, the latest update matters)

Context information:
- Sent date (received_date): {received_date}
- Reference delivery date (reference_date): {existing_date}

Email content:
{email_content}

Attachment content:
{chr(10).join(attachment_texts)}

Final answer (Only one date or "Null"):
"""

            # LLM 호출
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a procurement expert. Your task is to find the LATEST delivery date mentioned in the document. Return ONLY the date in YYYY-MM-DD format, with no additional text or explanation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.0
            )
            
            # 응답에서 날짜 추출
            date_str = response.choices[0].message.content.strip()
            
            # "Null" 응답 처리
            if date_str.lower() == "null":
                return None
            
            # 날짜 형식 검증 및 추출
            try:
                # 날짜 형식이 아닌 경우, 날짜만 추출 시도
                if not date_str.startswith("20"):  # YYYY-MM-DD 형식이 아닌 경우
                    # 숫자와 하이픈만 추출
                    date_match = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
                    if date_match:
                        date_str = date_match.group(0)
                
                # 최종 날짜 형식 검증
                datetime.strptime(date_str, "%Y-%m-%d")
                return date_str
            except ValueError:
                logger.error(f"Invalid date format: {date_str}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing delivery date: {e}")
            return None 

def clean_date_str(date_str):
    # 1. +0000 (UTC) → +0000
    date_str = re.sub(r"([+-][0-9]{4}) ?\([^)]+\)", r"\1", date_str)
    # 2. +0000 +0000 → 마지막만 남기기
    date_str = re.sub(r"([+-][0-9]{4}) ?([+-][0-9]{4})", r"\2", date_str)
    # 3. 남은 괄호 및 앞 공백 제거
    date_str = re.sub(r" ?\([^)]+\)", "", date_str)
    # 4. 여러 공백 정리
    date_str = re.sub(r" +", " ", date_str).strip()
    logging.getLogger(__name__).debug(f"[clean_date_str] after clean: '{date_str}'")
    return date_str

def parse_email_date(date_str):
    date_str = clean_date_str(date_str)
    logging.getLogger(__name__).debug(f"[parse_email_date] final date_str: '{date_str}'")
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
            dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.max.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc) 