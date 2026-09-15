# services/broker/angel_client.py
# FIXED: Better error handling and reconnection

import requests
import logging
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)

class AngelClient:
    """Angel One API client with auto-reconnect"""
    
    def __init__(self, jwt_token: str = None, api_key: str = None):
        self.jwt_token = jwt_token
        self.api_key = api_key
        self.base_url = "https://api.angelone.in"
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        self.is_connected = False
        self.reconnect_attempts = 0
        
    def connect(self) -> bool:
        """Connect to Angel One API"""
        try:
            if not self.jwt_token or not self.api_key:
                logger.error("[ERROR] Missing credentials")
                return False
            
            self.session.headers.update({
                'Authorization': f'Bearer {self.jwt_token}',
                'x-api-key': self.api_key
            })
            
            # Test connection
            response = self.session.get(f"{self.base_url}/rest/secure/user/profile")
            if response.status_code == 200:
                self.is_connected = True
                self.reconnect_attempts = 0
                logger.info("[OK] Angel One API connected")
                return True
            else:
                logger.error(f"[ERROR] Connection failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[ERROR] Connection error: {e}")
            return False
    
    def get_ltp(self, symboltoken: str, exchange: str = "NSE") -> Optional[Dict]:
        """Get Last Traded Price"""
        if not self.is_connected:
            if not self.connect():
                return None
        
        try:
            url = f"{self.base_url}/rest/secure/ltp"
            payload = {
                'symboltoken': symboltoken,
                'exchange': exchange
            }
            response = self.session.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return data.get('data', {})
                else:
                    logger.warning(f"[WARN] API returned error: {data}")
                    return None
            elif response.status_code in [401, 403]:
                # Token expired - reconnect
                logger.warning("[WARN] Token expired, reconnecting...")
                self.is_connected = False
                if self.connect():
                    return self.get_ltp(symboltoken, exchange)
                return None
            else:
                logger.error(f"[ERROR] API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] get_ltp error: {e}")
            return None
    
    def get_positions(self) -> Optional[Dict]:
        """Get current positions"""
        if not self.is_connected:
            if not self.connect():
                return None
        
        try:
            url = f"{self.base_url}/rest/secure/position"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {})
            else:
                logger.warning(f"[WARN] Positions API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] get_positions error: {e}")
            return None
    
    def place_order(self, order_data: Dict) -> Optional[Dict]:
        """Place an order"""
        if not self.is_connected:
            if not self.connect():
                return None
        
        try:
            url = f"{self.base_url}/rest/secure/placeorder"
            response = self.session.post(url, json=order_data)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    logger.info(f"[OK] Order placed: {data.get('data', {}).get('orderid')}")
                    return data.get('data', {})
                else:
                    logger.error(f"[ERROR] Order failed: {data}")
                    return None
            else:
                logger.error(f"[ERROR] Order API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[ERROR] place_order error: {e}")
            return None
    
    def disconnect(self):
        """Disconnect from API"""
        self.is_connected = False
        self.session.close()
        logger.info("[OK] Disconnected from Angel One API")
