# services/auth/auth_manager.py - Authentication Manager

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AuthManager:
    """Authentication manager for broker APIs."""
    
    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY", "") or os.getenv("ANGEL_APIKEY", "")
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "")
        self.pin = os.getenv("ANGEL_PIN", "")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "")
        self.is_authenticated = False
        self._load_credentials()
    
    def _load_credentials(self):
        """Load credentials from environment."""
        if all([self.api_key, self.client_id, self.pin]):
            logger.info("✅ Credentials loaded successfully")
            self.is_authenticated = True
        else:
            missing = []
            if not self.api_key:
                missing.append("API_KEY")
            if not self.client_id:
                missing.append("CLIENT_ID")
            if not self.pin:
                missing.append("PIN")
            logger.warning(f"⚠️ Missing credentials: {', '.join(missing)}")
    
    def get_auth_headers(self) -> dict:
        """Get authentication headers."""
        return {
            "X-PrivateKey": self.api_key,
            "X-ClientCode": self.client_id
        }
    
    def authenticate(self) -> bool:
        """Authenticate with broker."""
        return self.is_authenticated
