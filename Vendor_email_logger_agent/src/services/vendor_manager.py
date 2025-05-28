from typing import Dict, List, Optional
import logging
from Vendor_email_logger_agent.src.po_agent_os.supabase_client_anon import supabase

logger = logging.getLogger(__name__)

class VendorManager:
    def __init__(self):
        self.vendor_emails = set()
        self.load_vendor_emails()

    def load_vendor_emails(self):
        """Load vendor emails from database"""
        try:
            # Get all vendor emails from purchase_orders table
            response = supabase.table("purchase_orders").select("vendor_email").not_.is_("vendor_email", "null").execute()
            
            if response.data:
                self.vendor_emails = {po['vendor_email'] for po in response.data if po.get('vendor_email')}
                logger.info(f"Loaded {len(self.vendor_emails)} vendor emails from database")
            else:
                logger.warning("No vendor emails found in database")
        except Exception as e:
            logger.error(f"Error loading vendor emails: {e}")
            self.vendor_emails = set()

    def is_vendor_email(self, email: str) -> bool:
        """Check if an email belongs to a vendor"""
        return email in self.vendor_emails

    # ... existing code ... 