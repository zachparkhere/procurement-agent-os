import re
from typing import Dict, Optional
from Vendor_email_logger_agent.config import settings
from datetime import datetime, timedelta

class StatusDetector:
    def __init__(self):
        self.status_keywords = {
            "on-time_delivery": [
                "delivered", "completed", "received", "arrived",
                "on time", "on schedule"
            ],
            "delay": [
                "delay", "late", "postponed", "rescheduled",
                "behind schedule", "running late"
            ],
            "item_issue": [
                "problem", "issue", "defect", "damage",
                "wrong", "incorrect", "missing"
            ]
        }
        
    def detect_status(self, email_data: Dict) -> str:
        """Detect status from email content"""
        # Extract email content
        content = self._extract_content(email_data)
        if not content:
            return "no_response"
            
        # Check for status keywords
        for status, keywords in self.status_keywords.items():
            if any(keyword in content.lower() for keyword in keywords):
                return status
                
        # Check if it's a response
        if self._is_response(email_data):
            return "waiting_response"
            
        return "no_response"
        
    def _extract_content(self, email_data: Dict) -> str:
        """Extract content from email"""
        # TODO: Implement proper email content extraction
        return email_data.get('snippet', '')
        
    def _is_response(self, email_data: Dict) -> bool:
        """Check if email is a response"""
        headers = email_data.get('payload', {}).get('headers', [])
        in_reply_to = next(
            (h['value'] for h in headers if h['name'].lower() == 'in-reply-to'),
            None
        )
        return in_reply_to is not None 