"""
Utility functions for ETA status inference
Analyzes vendor response text to infer ETA status.
"""

from datetime import datetime
from typing import Optional

def infer_eta_status_from_reply(reply_text: str, reply_date: datetime) -> Optional[str]:
    """
    Analyzes vendor response text to infer ETA status.

    Args:
        reply_text (str): Vendor's response text
        reply_date (datetime): Response date

    Returns:
        Optional[str]: Inferred ETA status. Returns None if inference is not possible.

    Status Types:
    - promised_confirmation_within_2_days: Vendor promised to confirm within 2 days
    - checking_logistics: Checking logistics status
    - waiting_eta_confirmation: Waiting for ETA confirmation
    - uncertain_promise: Uncertain promise from vendor
    """
    if not reply_text or not isinstance(reply_text, str):
        return None

    text = reply_text.lower().strip()
    date_str = reply_date.date().isoformat()

    # Check for ETA or delivery related keywords
    eta_keywords = ["eta", "delivery", "ship", "dispatch", "arrival"]
    has_eta_keyword = any(keyword in text for keyword in eta_keywords)

    # Promise to confirm within 2 days
    if has_eta_keyword and any(phrase in text for phrase in [
        "within 2 days", "in 2 days", "next 2 days", 
        "within two days", "in two days", "next two days"
    ]):
        return f"promised_confirmation_within_2_days (since {date_str})"

    # Checking logistics status
    if has_eta_keyword and any(phrase in text for phrase in [
        "checking", "confirming", "will check", "will confirm",
        "looking into", "investigating", "verifying"
    ]):
        return f"checking_logistics ({date_str})"

    # Uncertain promise
    uncertain_phrases = [
        "will get back", "get back to you", "will update",
        "soon", "shortly", "as soon as possible", "asap"
    ]
    if any(phrase in text for phrase in uncertain_phrases):
        return f"uncertain_promise ({date_str})"

    # ETA mentioned but not specific
    if has_eta_keyword:
        return "waiting_eta_confirmation"

    return None

def get_eta_status_description(status: str) -> str:
    """
    Returns a description for the ETA status code.

    Args:
        status (str): ETA status code

    Returns:
        str: Description of the status
    """
    if not status:
        return "Unknown status"

    base_status = status.split(" (")[0]  # Remove date information
    
    descriptions = {
        "promised_confirmation_within_2_days": "Vendor promised to confirm ETA within 2 days",
        "checking_logistics": "Vendor is checking logistics status",
        "waiting_eta_confirmation": "Waiting for ETA confirmation",
        "uncertain_promise": "Vendor provided an uncertain response"
    }

    return descriptions.get(base_status, "Unknown status") 