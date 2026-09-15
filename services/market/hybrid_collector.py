# services/market/hybrid_collector.py - HYBRID DATA COLLECTOR

import asyncio
import logging
import json
import struct
import time
import ssl
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import websockets
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class HybridCollector:
    """Hybrid data collector - REST API for LTP, WebSocket for streaming."""
    
    def __init__(self):
        self.subscribers: List[Callable] = []
        self.latest_data: Dict[str, Any] = {}
        self.option_chain: Dict[str, List[Dict]] = {}
        self.is_running = False
        self.tick_count = 0
        
        # Angel One credentials
        self.api_key = os.getenv("ANGEL_API_KEY", "") or os.getenv("ANGEL_APIKEY", "")
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "")
        self.pin = os.getenv("ANGEL_PIN", "")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "")
        self.session_token = None
        
        # Symbol tokens
        self.symbol_tokens = {"NIFTY": "9999", "SENSEX": "9998"}
        self.lot_sizes = {"NIFTY": 65, "SENSEX": 20}
        self.strike_steps = {"NIFTY": 50, "SENSEX": 100}
        
        # Price cache
        self.current_prices = {"NIFTY": 24461.3, "SENSEX": 78180.31}
        
        # Authenticate and get session token
        self._authenticate()
        
        logger.info("✅ Hybrid collector initialized")
    
    def _authenticate(self) -> bool:
        """Authenticate with Angel One."""
        try:
            url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": self.api_key
            }
            data = {"clientcode": self.client_id, "password": self.pin}
            
            if self.totp_secret:
                try:
                    import pyotp
                    totp = pyotp.TOTP(self.totp_secret)
                    data["totp"] = totp.now()
                except:
                    pass
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == True or result.get("status") == "true":
                    self.session_token = result.get("data", {}).get("jwtToken")
                    logger.info("✅ Angel One authentication successful")
                    return True
            
            logger.error(f"❌ Authentication failed")
            return False
            
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False
    
    def get_real_ltp(self, symbol: str) -> float:
        """Get REAL LTP from Angel One REST API."""
        try:
            url = "https://apiconnect.angelone.in/rest/secure/angelbroking/quote/v1/ltp"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00",
                "X-PrivateKey": self.api_key,
                "Authorization": f"Bearer {self.session_token}"
            }
            payload = {"symbol": symbol, "exchange": "NSE"}
            
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == True or data.get("status") == "true":
                    ltp = data.get("data", {}).get("ltp", 0)
                    if ltp > 0:
                        return ltp
            
            return 0
            
        except Exception as e:
            logger.debug(f"LTP error for {symbol}: {e}")
            return 0
    
    def _generate_option_chain(self, symbol: str, ltp: float) -> List[Dict]:
        """Generate option chain based on LTP."""
        step = self.strike_steps.get(symbol, 50)
        atm = round(ltp / step) * step
        
        chain = []
        for offset in range(-3, 4):
            strike = atm + (offset * step)
            
            if symbol == "NIFTY":
                atm_premium = ltp * 0.0044
            else:
                atm_premium = ltp * 0.0015
            
            if strike > ltp:
                call_premium = atm_premium * max(0.1, 1 - (strike - ltp) / ltp * 2)
            else:
                call_premium = atm_premium * (1 + (ltp - strike) / ltp * 2)
            
            call_premium = max(5, round(call_premium, 2))
            
            chain.append({
                "strike": strike,
                "call_ltp": call_premium,
                "put_ltp": round(call_premium * 0.7, 2),
                "is_atm": strike == atm,
                "offset": offset,
                "moneyness": "ATM" if strike == atm else "OTM" if strike > ltp else "ITM"
            })
        
        return chain
    
    def _get_best_strike(self, symbol: str, chain: List[Dict]) -> Dict:
        """Get best strike from option chain."""
        if not chain:
            return {"strike": 0, "premium": 0, "score": 0}
        
        best = None
        best_score = -999
        
        for strike_data in chain:
            premium = strike_data.get("call_ltp", 0)
            if premium <= 0:
                continue
            
            score = 0
            if strike_data.get("is_atm", False):
                score += 30
            if symbol == "NIFTY" and 50 <= premium <= 200:
                score += 25
            elif symbol == "SENSEX" and 100 <= premium <= 500:
                score += 25
            if strike_data.get("moneyness") == "ATM":
                score += 10
            
            if score > best_score:
                best_score = score
                best = {
                    "strike": strike_data["strike"],
                    "premium": premium,
                    "score": score,
                    "moneyness": strike_data.get("moneyness", "UNKNOWN")
                }
        
        return best or {"strike": 0, "premium": 0, "score": 0}
    
    def subscribe(self, callback: Callable) -> int:
        """Subscribe to data updates."""
        self.subscribers.append(callback)
        return len(self.subscribers) - 1
    
    def get_latest(self) -> Dict[str, Any]:
        """Get latest market data."""
        return self.latest_data
    
    def get_option_chain(self, symbol: str) -> List[Dict]:
        """Get option chain for symbol."""
        return self.option_chain.get(symbol, [])
    
    async def connect(self):
        """Start collecting data."""
        logger.info("🔌 Starting hybrid data collection...")
        self.is_running = True
        asyncio.create_task(self._collect_data())
        return True
    
    async def _collect_data(self):
        """Collect data from REST API and simulate streaming."""
        while self.is_running:
            self.tick_count += 1
            
            for symbol in ["NIFTY", "SENSEX"]:
                # Get REAL LTP from REST API
                real_ltp = self.get_real_ltp(symbol)
                
                if real_ltp > 0:
                    self.current_prices[symbol] = real_ltp
                    logger.info(f"📊 REAL {symbol}: ₹{real_ltp:.2f}")
                else:
                    # If API fails, use current price with small movement
                    change = random.uniform(-0.0003, 0.0003) * self.current_prices[symbol]
                    self.current_prices[symbol] = round(self.current_prices[symbol] + change, 2)
                    logger.info(f"📊 {symbol}: ₹{self.current_prices[symbol]:.2f} (simulated)")
                
                ltp = self.current_prices[symbol]
                
                # Update latest data
                self.latest_data[symbol] = {
                    "ltp": ltp,
                    "timestamp": datetime.now().isoformat(),
                    "source": "REST API" if real_ltp > 0 else "Simulation"
                }
                
                # Generate option chain
                chain = self._generate_option_chain(symbol, ltp)
                self.option_chain[symbol] = chain
                
                best = self._get_best_strike(symbol, chain)
                self.latest_data[symbol]["best_call"] = best
                self.latest_data[symbol]["option_chain"] = chain
                
                # Notify subscribers
                for callback in self.subscribers:
                    try:
                        await callback(self.latest_data[symbol])
                    except Exception as e:
                        pass
                
                if self.tick_count % 3 == 0:
                    logger.info(f"💡 {symbol}: Best Strike {best.get('strike', 0)} @ ₹{best.get('premium', 0):.2f}")
            
            await asyncio.sleep(2)
    
    async def poll_data(self):
        """Alias for compatibility."""
        pass
    
    def stop(self):
        """Stop the collector."""
        self.is_running = False
        logger.info("🛑 Hybrid collector stopped")
