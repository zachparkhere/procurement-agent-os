# utils/text_processor.py
from openai import OpenAI
from typing import Dict, List, Tuple, Optional
import numpy as np
from config import settings
import tiktoken
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class TextProcessor:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.max_tokens = 8192  # Maximum tokens for GPT-4-turbo
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # PO number patterns
        self.po_patterns = [
            r"\bPO[-_#]?\d{4}-\d{3}\b",            # PO-2025-001 format
            r"\bPO[-_#]?\d{4,}\b",                 # PO123456, PO-123456, PO_123456, PO#123456
            r"\bPO[-_]?\d{8}-\d{1,3}\b",           # PO-20240512-001
            r"\bPR[-_]?\d{5,}\b",                  # PR-89012
            r"\bPUR\d{5,}\b",                      # PUR456789
            r"\bORD[-_]?[A-Z]{1,2}\d{3,}\b",       # ORD-AX0342
            r"\b\d{6,}\b",                         # 6+ digit numeric PO (ex. 20240512)
            r"\(PO[-_#]?\d{4}-\d{3}\)",            # (PO-2025-001)
            r"\(PO[-_#]?\d{4,}\)",                 # (PO123456), (PO-123456)
            r"\(PO[-_]?\d{8}-\d{1,3}\)",           # (PO-20240512-001)
            r"\(PR[-_]?\d{5,}\)",                  # (PR-89012)
            r"\(PUR\d{5,}\)",                      # (PUR456789)
            r"\(ORD[-_]?[A-Z]{1,2}\d{3,}\)",       # (ORD-AX0342)
            r"\(\d{6,}\)"                          # (20240512)
        ]
        self.po_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in self.po_patterns]
        
    def count_tokens(self, text: str) -> int:
        """Calculate the number of tokens in the text"""
        return len(self.encoding.encode(text))
    
    def truncate_text(self, text: str) -> str:
        """Truncate text to fit within maximum token limit"""
        tokens = self.encoding.encode(text)
        if len(tokens) > self.max_tokens:
            tokens = tokens[:self.max_tokens]
        return self.encoding.decode(tokens)
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for the text"""
        try:
            # Truncate text if too long
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
    
    def parse_delivery_date(self, email_content: str, attachments: List[Dict] = None, existing_date: str = None, received_date: str = None) -> Optional[str]:
        """
        Parse delivery date from email content and metadata.
        Uses LLM to extract and validate the delivery date.
        
        Args:
            email_content (str): Email content to analyze
            attachments (List[Dict], optional): List of attachment information
            existing_date (str, optional): Previously found delivery date
            received_date (str, optional): Email received date
            
        Returns:
            Optional[str]: Parsed delivery date in YYYY-MM-DD format or None
        """
        try:
            # Prepare context for LLM
            context = []
            if received_date:
                context.append(f"Email received date: {received_date}")
            if existing_date:
                context.append(f"Previous delivery date: {existing_date}")
            context_str = "\n".join(context) if context else "No additional context available."
            
            # Prepare prompt for LLM
            prompt = f"""
            Extract the delivery date from the following email content. Follow these rules:
            1. Look for dates in these formats:
               - Full dates: "May 5th, 2024", "05/05/2024", "2024-05-05"
               - Relative dates: "next Tuesday", "in 2 weeks", "end of this month"
               - Partial dates: "May 5th", "next month", "end of year"
               - Implicit dates: "ASAP", "urgent", "immediately"
            2. If year is not specified, assume current year unless the date would be in the past
            3. For relative dates, calculate based on the received date
            4. Return ONLY the date in YYYY-MM-DD format, nothing else
            5. If no valid date is found, return "None"
            
            Context:
            {context_str}
            
            Email Content:
            {email_content}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a delivery date extraction assistant. Extract and validate delivery dates from text following the given rules. Return ONLY the date in YYYY-MM-DD format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            
            # Clean up the result - remove any explanatory text
            result = re.sub(r'[^0-9-]', '', result)
            
            # Validate the date format
            if not result or result.lower() == 'none':
                return None
                
            try:
                # Try to parse the date
                parsed_date = datetime.strptime(result, "%Y-%m-%d")
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format returned by LLM: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing delivery date: {e}")
            return None

    def extract_po_number(self, text: str, attachments: List[Dict] = None) -> Optional[str]:
        """
        Extract PO number from given text and attachments.
        
        Args:
            text (str): Text to search for PO number
            attachments (List[Dict], optional): List of attachment information
            
        Returns:
            Optional[str]: Found PO number or None
        """
        if not text and not attachments:
            return None
            
        # Search for PO number in text
        if text:
            for regex in self.po_regexes:
                match = regex.search(text)
                if match:
                    return match.group(0)
        
        # Search for PO number in attachment filenames
        if attachments:
            for attachment in attachments:
                filename = attachment.get('filename', '')
                for regex in self.po_regexes:
                    match = regex.search(filename)
                    if match:
                        return match.group(0)
                        
        return None

    def extract_po_number_with_llm(self, text: str) -> Optional[str]:
        """
        Extract PO number from text using LLM.
        
        Args:
            text (str): Text to search for PO number
            
        Returns:
            Optional[str]: Found PO number or None
        """
        try:
            prompt = f"""
            Extract the PO number from the following text. Follow these rules:
            1. Look for PO numbers in these formats:
               - PO123456, PO-123456, PO_123456, PO#123456
               - PO-20240512-001 (date-number format)
               - PR-89012 (purchase request)
               - PUR456789 (purchase number)
               - ORD-AX0342 (order number)
               - 20240512 (6+ digit numeric PO)
            2. If multiple PO numbers are found, return the most recently mentioned one
            3. Return only the PO number without any additional text
            4. If no PO number is found, return 'None'
            
            Text to analyze:
            {text}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a PO number extraction assistant. Extract PO numbers from text following the given rules."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            if result.lower() == 'none':
                return None
                
            # Validate the extracted PO number
            for regex in self.po_regexes:
                if regex.search(result):
                    return result
                    
            return None
            
        except Exception as e:
            logger.error(f"Error extracting PO number with LLM: {e}")
            return None

    def find_po_number(self, subject: str, body: str, attachments: List[Dict] = None) -> Optional[str]:
        """
        Find PO number from email subject, body and attachments.
        Uses both regex patterns and LLM for extraction.
        
        Args:
            subject (str): Email subject
            body (str): Email body
            attachments (List[Dict], optional): List of attachment information
            
        Returns:
            Optional[str]: Found PO number or None
        """
        try:
            # Combine subject and body for regex search
            text = f"{subject}\n{body}"
            
            # First try regex patterns
            po_number = self.extract_po_number(text, attachments)
            if po_number:
                logger.info(f"Found PO number using regex: {po_number}")
                return po_number
                
            # If regex fails, try LLM
            logger.info("Regex patterns did not find PO number, trying LLM...")
            po_number = self.extract_po_number_with_llm(text)
            if po_number:
                logger.info(f"Found PO number using LLM: {po_number}")
                return po_number
                
            logger.info("No PO number found in email content")
            return None
            
        except Exception as e:
            logger.error(f"Error finding PO number: {e}")
            return None 