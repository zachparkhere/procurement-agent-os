# utils/text_processor.py
from openai import OpenAI
from typing import Dict, List, Tuple, Optional
import numpy as np
from Vendor_email_logger_agent.config import settings
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
            r"\bPO[-_]?\d{6}-\d{3}\b",             
            r"\bPO[-_#]?\d{4}-\d{3}\b",            
            r"\bPO[-_#]?\d{4,}\b",                 
            r"\bPO[-_]?\d{8}-\d{1,3}\b",           
            r"\bPR[-_]?\d{5,}\b",                  
            r"\bPUR\d{5,}\b",                      
            r"\bORD[-_]?[A-Z]{1,2}\d{3,}\b",       
            r"\b\d{6,}\b",                         
            r"\(PO[-_#]?\d{4}-\d{3}\)",            
            r"\(PO[-_#]?\d{4,}\)",                 
            r"\(PO[-_]?\d{8}-\d{1,3}\)",           
            r"\(PR[-_]?\d{5,}\)",                  
            r"\(PUR\d{5,}\)",                      
            r"\(ORD[-_]?[A-Z]{1,2}\d{3,}\)",       
            r"\(\d{6,}\)"                          
        ]
        self.po_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in self.po_patterns]
        
    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
    
    def truncate_text(self, text: str) -> str:
        tokens = self.encoding.encode(text)
        if len(tokens) > self.max_tokens:
            tokens = tokens[:self.max_tokens]
        return self.encoding.decode(tokens)
    
    def get_embedding(self, text: str) -> List[float]:
        try:
            truncated_text = self.truncate_text(text)
            response = self.client.embeddings.create(
                input=truncated_text,
                model="text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

    def process_email_content(self, message_data):
        try:
            body_text = message_data.get("body", "")
            if not body_text:
                return "", ""
                
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

    def parse_delivery_date(self, message_data: Dict, attachments: List[Dict] = None, existing_date: str = None, received_date: str = None) -> Optional[str]:
        try:
            body_text = message_data.get("body", "")
            if not body_text:
                return None

            context = []
            if received_date:
                context.append(f"Email received date: {received_date}")
                try:
                    received_year = datetime.strptime(received_date[:10], "%Y-%m-%d").year
                except:
                    received_year = datetime.now().year
            else:
                received_year = datetime.now().year

            if existing_date:
                context.append(f"Previous delivery date: {existing_date}")
            context_str = "\n".join(context) if context else "No additional context available."
            
            prompt = f"""
Extract the delivery date from the following email content. Follow these rules:

1. Look for dates in these formats:
   - Full dates: "May 5th, 2025", "05/05/2025", "2025-05-05"
   - Relative dates: "next Tuesday", "in 2 weeks", "end of this month"
   - Partial dates: "May 5th", "next month", "end of year"
   - Implicit dates: "ASAP", "urgent", "immediately"

2. If the **year is not mentioned**, you MUST assume the year is **{received_year}**.

3. For relative dates, calculate them based on this received date: {received_date or 'unknown'}

4. Return ONLY the date in YYYY-MM-DD format, nothing else.

5. If no valid date is found, return "None".

Context:
{context_str}

Email Content:
{body_text}
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
            result = re.sub(r'[^0-9-]', '', result)
            if not result or result.lower() == 'none':
                return None
            try:
                parsed_date = datetime.strptime(result, "%Y-%m-%d")
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format returned by LLM: {result}")
                return None
        except Exception as e:
            logger.error(f"Error parsing delivery date: {e}")
            return None

    def extract_po_number(self, text: str, attachments: List[Dict] = None) -> Optional[str]:
        if not text and not attachments:
            return None
        if text:
            for regex in self.po_regexes:
                match = regex.search(text)
                if match:
                    return match.group(0)
            po_llm = self.extract_po_number_with_llm(text)
            if po_llm:
                return po_llm
        if attachments:
            for attachment in attachments:
                filename = attachment.get('filename', '')
                for regex in self.po_regexes:
                    match = regex.search(filename)
                    if match:
                        return match.group(0)
        return None

    def extract_po_number_with_llm(self, text: str) -> Optional[str]:
        try:
            prompt = f"""
Extract the PO number from the following text. Follow these flexible rules to handle various formats and real-world phrasing:

1. Look for PO numbers in any of these formats (case-insensitive):
    - PO123456, PO-123456, PO_123456, PO#123456, PO 123456
    - PO-20240512-001 (date-based formats)
    - PR-89012 (purchase request)
    - PUR456789 (purchase number)
    - ORD-AX0342 (order number)
    - Standalone 6+ digit numbers that could be POs (e.g., 20240512)

2. PO numbers might appear next to labels like:
    - "PO number", "P.O. No.", "purchase order", "order number", "request ID", etc.
    - These may be followed by colons (:), dashes (-), spaces, or enclosed in brackets or parentheses.

3. If multiple PO numbers are mentioned, return the one mentioned last.

4. Return only the PO number string without any extra text or explanation.

5. If no PO number is found, return 'None'.

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
            for regex in self.po_regexes:
                if regex.search(result):
                    return result
            return None
        except Exception as e:
            logger.error(f"Error extracting PO number with LLM: {e}")
            return None

    def find_po_number(self, subject: str, body: str, attachments: List[Dict] = None) -> Optional[str]:
        try:
            text = f"{subject}\n{body}"
            po_number = self.extract_po_number(text, attachments)
            if po_number:
                logger.info(f"Found PO number using regex: {po_number}")
                return po_number
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
