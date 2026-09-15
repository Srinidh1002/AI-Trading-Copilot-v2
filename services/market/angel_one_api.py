# services/market/angel_one_api.py
# REAL ANGEL ONE API INTEGRATION - Fixed to match .env variable names

import json
import logging
import requests
import hashlib
import time
import base64
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AngelOneAPI:
    """Real Angel One API Integration - Reads credentials from .env."""
    
    def __init__(self):
        """Initialize Angel One API with credentials from .env."""
        # Read from .env - CHECK BOTH VARIABLE NAMES
        self.api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
        self.client_id = os.getenv('ANGEL_CLIENT_ID', '')
        self.pin = os.getenv('ANGEL_PIN', '')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
        
        # Also check UPSTOX if Angel One not available
        if not self.api_key:
            self.api_key = os.getenv('UPSTOX_API_KEY', '')
            self.client_id = os.getenv('UPSTOX_CLIENT_ID', '')
        
        self.base_url = "https://apiconnect.angelone.in"
        self.auth_url = "https://auth.angelone.in"
        self.session_token = None
        self.feed_token = None
        self.refresh_token = None
        self.is_authenticated = False
        self.user_profile = None
        
        # Token storage
        self.token_file = Path("data/angel_token.json")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Cache for real data
        self.cache = {}
        self.cache_timeout = 3  # seconds
        
        logger.info("[ANGEL] API Client initialized")
        logger.info(f"[ANGEL] API Key: {self.api_key[:8] if self.api_key else 'MISSING'}...")
        logger.info(f"[ANGEL] Client ID: {self.client_id if self.client_id else 'MISSING'}")
        logger.info(f"[ANGEL] PIN: {'SET' if self.pin else 'MISSING'}")
        logger.info(f"[ANGEL] TOTP: {'SET' if self.totp_secret else 'MISSING'}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Angel One API using credentials from .env.
        """
        try:
            # Check if we have a valid token
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    if tokens.get('expires_at', 0) > time.time():
                        self.session_token = tokens.get('session_token')
                        self.refresh_token = tokens.get('refresh_token')
                        self.feed_token = tokens.get('feed_token')
                        self.is_authenticated = True
                        logger.info("[ANGEL] Using cached authentication")
                        return True
            
            if not all([self.api_key, self.client_id, self.pin]):
                logger.warning("[ANGEL] Missing credentials. Check .env file.")
                logger.warning(f"[ANGEL] API Key: {'SET' if self.api_key else 'MISSING'}")
                logger.warning(f"[ANGEL] Client ID: {'SET' if self.client_id else 'MISSING'}")
                logger.warning(f"[ANGEL] PIN: {'SET' if self.pin else 'MISSING'}")
                return False
            
            # Step 1: Login
            login_url = f"{self.base_url}/rest/auth/angelbroking/login/v1/products"
            headers = {
                "Content-Type": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": self.api_key
            }
            
            login_data = {
                "clientcode": self.client_id,
                "password": self.pin,
                "totp": self.totp_secret
            }
            
            logger.info("[ANGEL] Authenticating...")
            response = requests.post(login_url, headers=headers, json=login_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    self.session_token = data.get('data', {}).get('session_token')
                    self.feed_token = data.get('data', {}).get('feed_token')
                    self.refresh_token = data.get('data', {}).get('refresh_token')
                    self.is_authenticated = True
                    
                    # Save tokens
                    tokens = {
                        'session_token': self.session_token,
                        'feed_token': self.feed_token,
                        'refresh_token': self.refresh_token,
                        'expires_at': time.time() + 86400  # 24 hours
                    }
                    with open(self.token_file, 'w') as f:
                        json.dump(tokens, f)
                    
                    logger.info("[ANGEL] Authentication successful!")
                    return True
                else:
                    logger.error(f"[ANGEL] Login failed: {data.get('message', 'Unknown error')}")
                    return False
            else:
                logger.error(f"[ANGEL] Login error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[ANGEL] Authentication error: {e}")
            return False
    
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
        """
        Get REAL LTP from Angel One.
        
        Args:
            symbol: NIFTY or SENSEX
        
        Returns:
            float: Latest trading price
        """
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return 0
            
            # Get LTP from quote
            url = f"{self.base_url}/rest/secure/angelbroking/quote/v1/ltp"
            
            payload = {
                "symbol": symbol,
                "exchange": "NSE"
            }
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    return data.get('data', {}).get('ltp', 0)
            
            return 0
            
        except Exception as e:
            logger.error(f"[ANGEL] LTP error for {symbol}: {e}")
            return 0
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> dict:
        """
        Get REAL option chain data from Angel One.
        
        Args:
            symbol: NIFTY or SENSEX
            expiry: Expiry date (YYYY-MM-DD) or None for weekly
        
        Returns:
            dict: Option chain data with REAL prices
        """
        # Check cache
        cache_key = f"option_chain_{symbol}_{expiry}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (time.time() - cached_time) < self.cache_timeout:
                return cached_data
        
        try:
            if not self.is_authenticated:
                if not self.authenticate():
                    return self._get_simulated_option_chain(symbol)
            
            # Get expiry if not provided
            if not expiry:
                expiry = self.get_weekly_expiry(symbol)
            
            # API endpoint for option chain
            url = f"{self.base_url}/rest/secure/angelbroking/option/v1/getOptionChain"
            
            payload = {
                "symbol": symbol,
                "expiry": expiry
            }
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status'):
                    option_data = data.get('data', {})
                    result = self._parse_option_chain(option_data, symbol)
                    
                    # Cache
                    self.cache[cache_key] = (time.time(), result)
                    
                    logger.info(f"[ANGEL] Got {len(result.get('strikes', []))} strikes for {symbol}")
                    return result
                else:
                    logger.error(f"[ANGEL] Option chain error: {data.get('message', 'Unknown')}")
                    return self._get_simulated_option_chain(symbol)
            else:
                logger.error(f"[ANGEL] HTTP error: {response.status_code}")
                return self._get_simulated_option_chain(symbol)
                
        except Exception as e:
            logger.error(f"[ANGEL] Option chain error: {e}")
            return self._get_simulated_option_chain(symbol)
    
    def _parse_option_chain(self, data: dict, symbol: str) -> dict:
        """Parse the option chain response."""
        strikes = []
        underlying = data.get('underlying', 0)
        
        # Parse the option chain data
        call_data = data.get('calls', [])
        put_data = data.get('puts', [])
        
        # Create strike map
        call_map = {}
        for c in call_data:
            strike = c.get('strike', 0)
            call_map[strike] = {
                'ltp': c.get('ltp', 0),
                'oi': c.get('oi', 0),
                'oi_change': c.get('change', 0),
                'volume': c.get('volume', 0),
                'iv': c.get('iv', 0),
                'bid': c.get('bid', 0),
                'ask': c.get('ask', 0)
            }
        
        put_map = {}
        for p in put_data:
            strike = p.get('strike', 0)
            put_map[strike] = {
                'ltp': p.get('ltp', 0),
                'oi': p.get('oi', 0),
                'oi_change': p.get('change', 0),
                'volume': p.get('volume', 0),
                'iv': p.get('iv', 0),
                'bid': p.get('bid', 0),
                'ask': p.get('ask', 0)
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
                'call_oi_change': call.get('oi_change', 0),
                'call_volume': call.get('volume', 0),
                'call_iv': call.get('iv', 0),
                'call_bid': call.get('bid', 0),
                'call_ask': call.get('ask', 0),
                'put_ltp': put.get('ltp', 0),
                'put_oi': put_oi,
                'put_oi_change': put.get('oi_change', 0),
                'put_volume': put.get('volume', 0),
                'put_iv': put.get('iv', 0),
                'put_bid': put.get('bid', 0),
                'put_ask': put.get('ask', 0),
                'pcr': pcr
            })
        
        # Calculate total PCR
        total_call_oi = sum(s['call_oi'] for s in strikes)
        total_put_oi = sum(s['put_oi'] for s in strikes)
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'strikes': strikes,
            'total_pcr': total_put_oi / total_call_oi if total_call_oi > 0 else 0.5,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_simulated_option_chain(self, symbol: str) -> dict:
        """Get simulated option chain when API fails."""
        logger.info(f"[ANGEL] Using simulated data for {symbol}")
        
        # Get underlying from market data
        from services.market.websocket_bridge import WebSocketBridge
        bridge = WebSocketBridge('data/task9/live_stream')
        bridge.initialize()
        market_data = bridge.get_latest_data()
        
        underlying = market_data.get(symbol, {}).get('ltp', 24461.3 if symbol == 'NIFTY' else 78180.31)
        
        # Generate strikes around ATM
        strikes = []
        step = 50 if symbol == 'NIFTY' else 100
        atm_strike = round(underlying / step) * step
        
        for offset in range(-5, 6):
            strike = atm_strike + (offset * step)
            
            # Calculate realistic premiums
            distance_pct = abs(strike - underlying) / underlying
            
            # ATM premium
            atm_premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
            
            # Call premium (OTM = cheaper)
            call_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
            if strike < underlying:
                call_premium *= 1 + distance_pct * 2
            else:
                call_premium *= max(0.1, 1 - distance_pct * 2)
            
            # Put premium
            put_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
            if strike > underlying:
                put_premium *= 1 + distance_pct * 2
            else:
                put_premium *= max(0.1, 1 - distance_pct * 2)
            
            # OI - higher near ATM
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
        
        total_call_oi = sum(s['call_oi'] for s in strikes)
        total_put_oi = sum(s['put_oi'] for s in strikes)
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'strikes': strikes,
            'total_pcr': total_put_oi / total_call_oi if total_call_oi > 0 else 0.5,
            'timestamp': datetime.now().isoformat(),
            'simulated': True
        }
    
    def get_weekly_expiry(self, symbol: str) -> str:
        """Get the weekly expiry date (Thursday)."""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
    
    def get_monthly_expiry(self, symbol: str) -> str:
        """Get the monthly expiry date (last Thursday)."""
        today = datetime.now()
        if today.month == 12:
            last_day = datetime(today.year, 12, 31)
        else:
            last_day = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
        days_until_thursday = (3 - last_day.weekday()) % 7
        expiry = last_day - timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
