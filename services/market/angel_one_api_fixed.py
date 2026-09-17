# services/market/angel_one_api_fixed.py
# FIXED ANGEL ONE API - Multiple authentication methods

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


class AngelOneAPIFixed:
    """Fixed Angel One API with multiple auth methods."""
    
    def __init__(self):
        # Read credentials from .env
        self.api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
        self.client_id = os.getenv('ANGEL_CLIENT_ID', '')
        self.pin = os.getenv('ANGEL_PIN', '')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
        
        self.base_url = "https://apiconnect.angelone.in"
        self.session_token = None
        self.feed_token = None
        self.is_authenticated = False
        
        # Token storage
        self.token_file = Path("data/angel_token.json")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("[ANGEL] API Client initialized")
    
    def authenticate(self) -> bool:
        """Authenticate using multiple methods."""
        # Check cached token first
        if self._load_cached_token():
            return True
        
        # Try methods in order
        methods = [
            self._auth_with_totp,
            self._auth_without_totp,
            self._auth_web_login
        ]
        
        for method in methods:
            try:
                if method():
                    return True
            except Exception as e:
                logger.debug(f"[ANGEL] Auth method failed: {e}")
                continue
        
        logger.error("[ANGEL] All authentication methods failed")
        return False
    
    def _load_cached_token(self) -> bool:
        """Load cached token if valid."""
        if not self.token_file.exists():
            return False
        
        try:
            with open(self.token_file, 'r') as f:
                tokens = json.load(f)
                if tokens.get('expires_at', 0) > time.time():
                    self.session_token = tokens.get('session_token')
                    self.feed_token = tokens.get('feed_token')
                    self.is_authenticated = True
                    logger.info("[ANGEL] Using cached token")
                    return True
        except:
            pass
        return False
    
    def _auth_with_totp(self) -> bool:
        """Authenticate with TOTP."""
        if not self.totp_secret:
            return False
        
        try:
            import pyotp
            totp = pyotp.TOTP(self.totp_secret)
            current_totp = totp.now()
        except:
            # Try with base32
            try:
                import pyotp
                totp = pyotp.TOTP(base64.b32encode(self.totp_secret.encode()).decode())
                current_totp = totp.now()
            except:
                logger.warning("[ANGEL] TOTP generation failed")
                return False
        
        url = f"{self.base_url}/rest/auth/angelbroking/user/v1/loginByPassword"
        headers = self._get_auth_headers()
        data = {
            "clientcode": self.client_id,
            "password": self.pin,
            "totp": current_totp
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status'):
                self._save_token(result.get('data', {}))
                logger.info("[ANGEL] TOTP authentication successful")
                return True
        
        return False
    
    def _auth_without_totp(self) -> bool:
        """Authenticate without TOTP (some accounts don't need it)."""
        url = f"{self.base_url}/rest/auth/angelbroking/login/v1/products"
        headers = self._get_auth_headers()
        data = {
            "clientcode": self.client_id,
            "password": self.pin
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('status'):
                    self._save_token(result.get('data', {}))
                    logger.info("[ANGEL] Without TOTP authentication successful")
                    return True
            except:
                pass
        
        return False
    
    def _auth_web_login(self) -> bool:
        """Authenticate using web login endpoint."""
        url = f"{self.base_url}/rest/auth/angelbroking/oauth/v2/login"
        headers = self._get_auth_headers()
        data = {
            "clientcode": self.client_id,
            "password": self.pin
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('status'):
                    self._save_token(result.get('data', {}))
                    logger.info("[ANGEL] Web login successful")
                    return True
            except:
                pass
        
        return False
    
    def _get_auth_headers(self) -> dict:
        """Get authentication headers."""
        return {
            "Content-Type": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key
        }
    
    def _save_token(self, data: dict):
        """Save authentication token."""
        self.session_token = data.get('session_token')
        self.feed_token = data.get('feed_token')
        self.is_authenticated = True
        
        tokens = {
            'session_token': self.session_token,
            'feed_token': self.feed_token,
            'refresh_token': data.get('refresh_token'),
            'expires_at': time.time() + 86400
        }
        
        with open(self.token_file, 'w') as f:
            json.dump(tokens, f)
    
    def _get_headers(self) -> dict:
        """Get API headers with authentication."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
            "Authorization": f"Bearer {self.session_token}" if self.session_token else ""
        }
    
    def get_ltp(self, symbol: str) -> float:
        """Get LTP from Angel One."""
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return 0
            
            url = f"{self.base_url}/rest/secure/angelbroking/quote/v1/ltp"
            payload = {"symbol": symbol, "exchange": "NSE"}
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return data.get('data', {}).get('ltp', 0)
            return 0
        except Exception as e:
            logger.error(f"[ANGEL] LTP error: {e}")
            return 0
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> dict:
        """Get option chain data."""
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return self._get_simulated_data(symbol)
            
            if not expiry:
                expiry = self._get_weekly_expiry()
            
            url = f"{self.base_url}/rest/secure/angelbroking/option/v1/getOptionChain"
            payload = {"symbol": symbol, "expiry": expiry}
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return self._parse_option_chain(data.get('data', {}), symbol)
            
            return self._get_simulated_data(symbol)
        except Exception as e:
            logger.error(f"[ANGEL] Option chain error: {e}")
            return self._get_simulated_data(symbol)
    
    def _parse_option_chain(self, data: dict, symbol: str) -> dict:
        """Parse option chain response."""
        strikes = []
        underlying = data.get('underlying', 0)
        
        call_data = data.get('calls', [])
        put_data = data.get('puts', [])
        
        call_map = {}
        for c in call_data:
            strike = c.get('strike', 0)
            call_map[strike] = {
                'ltp': c.get('ltp', 0),
                'oi': c.get('oi', 0),
                'oi_change': c.get('change', 0),
                'volume': c.get('volume', 0)
            }
        
        put_map = {}
        for p in put_data:
            strike = p.get('strike', 0)
            put_map[strike] = {
                'ltp': p.get('ltp', 0),
                'oi': p.get('oi', 0),
                'oi_change': p.get('change', 0),
                'volume': p.get('volume', 0)
            }
        
        all_strikes = sorted(set(call_map.keys()) | set(put_map.keys()))
        
        for strike in all_strikes:
            call = call_map.get(strike, {})
            put = put_map.get(strike, {})
            
            call_oi = call.get('oi', 0)
            put_oi = put.get('oi', 0)
            
            strikes.append({
                'strike': strike,
                'call_ltp': call.get('ltp', 0),
                'call_oi': call_oi,
                'call_oi_change': call.get('oi_change', 0),
                'call_volume': call.get('volume', 0),
                'put_ltp': put.get('ltp', 0),
                'put_oi': put_oi,
                'put_oi_change': put.get('oi_change', 0),
                'put_volume': put.get('volume', 0),
                'pcr': put_oi / call_oi if call_oi > 0 else 0
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
    
    def _get_simulated_data(self, symbol: str) -> dict:
        """Get simulated option chain data."""
        from services.market.websocket_bridge import WebSocketBridge
        bridge = WebSocketBridge('data/task9/live_stream')
        bridge.initialize()
        market_data = bridge.get_latest_data()
        
        underlying = market_data.get(symbol, {}).get('ltp', 24461.3 if symbol == 'NIFTY' else 78180.31)
        
        strikes = []
        step = 50 if symbol == 'NIFTY' else 100
        atm_strike = round(underlying / step) * step
        
        for offset in range(-5, 6):
            strike = atm_strike + (offset * step)
            atm_premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
            distance_pct = abs(strike - underlying) / underlying
            
            call_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
            put_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
            
            if strike < underlying:
                call_premium *= 1 + distance_pct * 2
                put_premium *= max(0.1, 1 - distance_pct * 2)
            else:
                call_premium *= max(0.1, 1 - distance_pct * 2)
                put_premium *= 1 + distance_pct * 2
            
            oi_factor = max(0.1, 1 - distance_pct * 10)
            call_oi = int(100000 * oi_factor * (0.5 + offset / 20))
            put_oi = int(100000 * oi_factor * (0.5 - offset / 20))
            
            strikes.append({
                'strike': strike,
                'call_ltp': round(max(5, call_premium), 2),
                'call_oi': max(1000, call_oi),
                'call_oi_change': round(offset * 10, 2),
                'call_volume': max(100, call_oi // 10),
                'put_ltp': round(max(5, put_premium), 2),
                'put_oi': max(1000, put_oi),
                'put_oi_change': round(-offset * 10, 2),
                'put_volume': max(100, put_oi // 10),
                'pcr': max(0.1, put_oi / call_oi if call_oi > 0 else 1)
            })
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'strikes': strikes,
            'total_pcr': 0.5,
            'timestamp': datetime.now().isoformat(),
            'simulated': True
        }
    
    def _get_weekly_expiry(self) -> str:
        """Get weekly expiry date."""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
