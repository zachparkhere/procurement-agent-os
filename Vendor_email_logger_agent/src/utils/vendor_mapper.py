from typing import Dict, Optional
import re
from ..config import settings

class VendorMapper:
    def __init__(self):
        self.vendor_mapping: Dict[str, str] = {}  # email -> vendor_id
        self.domain_mapping: Dict[str, str] = {}  # domain -> vendor_id
        
    def add_vendor(self, email: str, vendor_id: str):
        """Add a vendor mapping"""
        self.vendor_mapping[email.lower()] = vendor_id
        domain = self._extract_domain(email)
        if domain:
            self.domain_mapping[domain] = vendor_id
            
    def get_vendor_id(self, email: str) -> Optional[str]:
        """Get vendor_id from email"""
        email = email.lower()
        
        # Check exact email match
        if email in self.vendor_mapping:
            return self.vendor_mapping[email]
            
        # Check domain match
        domain = self._extract_domain(email)
        if domain in self.domain_mapping:
            return self.domain_mapping[domain]
            
        return None
        
    def _extract_domain(self, email: str) -> Optional[str]:
        """Extract domain from email address"""
        match = re.search(r'@(.+)$', email)
        return match.group(1) if match else None
        
    def load_from_database(self):
        """Load vendor mappings from database"""
        # TODO: Implement database loading
        pass
        
    def save_to_database(self):
        """Save vendor mappings to database"""
        # TODO: Implement database saving
        pass 