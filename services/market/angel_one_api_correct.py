# services/market/angel_one_api_correct.py - CORRECT ANGEL ONE API

import json
import logging
import requests
import time
import os
import base64
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AngelOneAPICorrect:
    """Correct Angel One API based on official documentation."""
    
    def __init__(self):
        # Read from .env
        self.api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
        self.client_id = os.getenv('ANGEL_CLIENT_ID', '')
        self.pin = os.getenv('ANGEL_PIN', '')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
        
        self.base_url = "https://apiconnect.angelone.in"
        self.session_token = None
        self.feed_token = None
        self.refresh_token = None
        self.is_authenticated = False
        
        # Token storage
        self.token_file = Path("data/angel_token.json")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Cache
        self.cache = {}
        self.cache_timeout = 3
        
        logger.info("[ANGEL] API Client initialized")
        logger.info(f"[ANGEL] API Key: {self.api_key[:8] if self.api_key else 'MISSING'}...")
        logger.info(f"[ANGEL] Client ID: {self.client_id}")
    
    def _get_auth_headers(self) -> dict:
        """Get authentication headers (without Authorization)."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key
        }
    
    def _get_headers(self) -> dict:
        """Get API headers with Authorization."""
        headers = self._get_auth_headers()
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers
    
    def authenticate(self) -> bool:
        """Authenticate with Angel One using loginByPassword."""
        try:
            # Check cached token
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    if tokens.get('expires_at', 0) > time.time():
                        self.session_token = tokens.get('session_token')
                        self.feed_token = tokens.get('feed_token')
                        self.refresh_token = tokens.get('refresh_token')
                        self.is_authenticated = True
                        logger.info("[ANGEL] Using cached token")
                        return True
            
            if not all([self.api_key, self.client_id, self.pin]):
                logger.error("[ANGEL] Missing credentials")
                return False
            
            # Login endpoint from documentation
            url = f"{self.base_url}/rest/auth/angelbroking/user/v1/loginByPassword"
            headers = self._get_auth_headers()
            
            # Request body
            data = {
                "clientcode": self.client_id,
                "password": self.pin
            }
            
            # Add TOTP if available
            if self.totp_secret:
                try:
                    import pyotp
                    totp = pyotp.TOTP(self.totp_secret)
                    data["totp"] = totp.now()
                    logger.info(f"[ANGEL] Using TOTP: {data['totp']}")
                except Exception as e:
                    logger.warning(f"[ANGEL] TOTP generation failed: {e}")
            
            logger.info("[ANGEL] Authenticating...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            logger.info(f"[ANGEL] Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"[ANGEL] Response: {json.dumps(result, indent=2)}")
                
                if result.get('status') == True or result.get('status') == 'true':
                    self.session_token = result.get('data', {}).get('session_token')
                    self.feed_token = result.get('data', {}).get('feed_token')
                    self.refresh_token = result.get('data', {}).get('refresh_token')
                    self.is_authenticated = True
                    
                    # Save token
                    tokens = {
                        'session_token': self.session_token,
                        'feed_token': self.feed_token,
                        'refresh_token': self.refresh_token,
                        'expires_at': time.time() + 86400
                    }
                    with open(self.token_file, 'w') as f:
                        json.dump(tokens, f)
                    
                    logger.info("[ANGEL] Authentication successful!")
                    return True
                else:
                    logger.error(f"[ANGEL] Login failed: {result.get('message', 'Unknown error')}")
                    logger.error(f"[ANGEL] Error code: {result.get('errorcode', 'N/A')}")
                    return False
            else:
                logger.error(f"[ANGEL] HTTP error: {response.status_code}")
                logger.error(f"[ANGEL] Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.error(f"[ANGEL] Authentication error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_ltp(self, symbol: str) -> float:
        """
        Get LTP from Angel One.
        
        Endpoint: /rest/secure/angelbroking/quote/v1/ltp
        """
        cache_key = f"ltp_{symbol}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if (time.time() - cached_time) < self.cache_timeout:
                return cached_value
        
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return 0
            
            url = f"{self.base_url}/rest/secure/angelbroking/quote/v1/ltp"
            payload = {
                "symbol": symbol,
                "exchange": "NSE"
            }
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == True or data.get('status') == 'true':
                    ltp = data.get('data', {}).get('ltp', 0)
                    if ltp > 0:
                        self.cache[cache_key] = (time.time(), ltp)
                        return ltp
            
            return 0
            
        except Exception as e:
            logger.error(f"[ANGEL] LTP error for {symbol}: {e}")
            return 0
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> dict:
        """
        Get option chain from Angel One.
        
        Endpoint: /rest/secure/angelbroking/option/v1/getOptionChain
        """
        cache_key = f"option_chain_{symbol}_{expiry}"
        if cache_key in self.cache:
            cached_time, cached_value = self.cache[cache_key]
            if (time.time() - cached_time) < self.cache_timeout:
                return cached_value
        
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return {}
            
            if not expiry:
                expiry = self._get_weekly_expiry()
            
            url = f"{self.base_url}/rest/secure/angelbroking/option/v1/getOptionChain"
            payload = {
                "symbol": symbol,
                "expiry": expiry
            }
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == True or data.get('status') == 'true':
                    option_data = data.get('data', {})
                    result = self._parse_option_chain(option_data, symbol)
                    self.cache[cache_key] = (time.time(), result)
                    return result
            
            return {}
            
        except Exception as e:
            logger.error(f"[ANGEL] Option chain error for {symbol}: {e}")
            return {}
    
    def _parse_option_chain(self, data: dict, symbol: str) -> dict:
        """Parse option chain response."""
        strikes = []
        underlying = data.get('underlying', 0)
        
        call_data = data.get('calls', [])
        put_data = data.get('puts', [])
        
        # Create maps
        call_map = {}
        for c in call_data:
            strike = c.get('strike', 0)
            if strike > 0:
                call_map[strike] = {
                    'ltp': c.get('ltp', 0),
                    'oi': c.get('oi', 0),
                    'change': c.get('change', 0),
                    'volume': c.get('volume', 0)
                }
        
        put_map = {}
        for p in put_data:
            strike = p.get('strike', 0)
            if strike > 0:
                put_map[strike] = {
                    'ltp': p.get('ltp', 0),
                    'oi': p.get('oi', 0),
                    'change': p.get('change', 0),
                    'volume': p.get('volume', 0)
                }
        
        # Combine strikes
        all_strikes = sorted(set(call_map.keys()) | set(put_map.keys()))
        
        for strike in all_strikes:
            call = call_map.get(strike, {})
            put = put_map.get(strike, {})
            
            call_oi = call.get('oi', 0)
            put_oi = put.get('oi', 0)
            pcr = put_oi / call_oi if call_oi > 0 else 0
            
            strikes.append({
                'strike': strike,
                'call_ltp': call.get('ltp', 0),
                'call_oi': call_oi,
                'call_oi_change': call.get('change', 0),
                'call_volume': call.get('volume', 0),
                'put_ltp': put.get('ltp', 0),
                'put_oi': put_oi,
                'put_oi_change': put.get('change', 0),
                'put_volume': put.get('volume', 0),
                'pcr': round(pcr, 2)
            })
        
        total_call_oi = sum(s['call_oi'] for s in strikes)
        total_put_oi = sum(s['put_oi'] for s in strikes)
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'strikes': strikes,
            'total_pcr': total_put_oi / total_call_oi if total_call_oi > 0 else 0.5,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_weekly_expiry(self) -> str:
        """Get weekly expiry date (Thursday)."""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
