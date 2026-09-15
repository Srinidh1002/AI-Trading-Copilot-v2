# services/market/websocket_collector.py - FINAL FIXED VERSION

import asyncio
import logging
import json
import struct
import time
import ssl
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
import websockets
import os
import random
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class WebSocketCollector:
    """Angel One WebSocket collector with proper parsing."""
    
    def __init__(self):
        self.subscribers: List[Callable] = []
        self.latest_data: Dict[str, Any] = {}
        self.option_chain: Dict[str, List[Dict]] = {}
        self.is_running = False
        self.websocket = None
        self.tick_count = 0
        self.use_websocket = False
        self.real_prices = {"NIFTY": 0, "SENSEX": 0}
        
        # Angel One credentials
        self.api_key = os.getenv("ANGEL_API_KEY", "") or os.getenv("ANGEL_APIKEY", "")
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "")
        self.pin = os.getenv("ANGEL_PIN", "")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "")
        
        self.ws_url = "wss://smartapisocket.angelone.in/smart-stream"
        self.session_token = None
        self.feed_token = None
        
        # Symbol tokens
        self.symbol_tokens = {"NIFTY": "9999", "SENSEX": "9998"}
        self.lot_sizes = {"NIFTY": 65, "SENSEX": 20}
        self.strike_steps = {"NIFTY": 50, "SENSEX": 100}
        
        # Load Task 9 data as fallback
        self.task9_prices = {"NIFTY": 24461.3, "SENSEX": 78180.31}
        self._load_task9_data()
        
        # Authenticate
        self._authenticate()
        
        logger.info("✅ WebSocket collector initialized")
    
    def _load_task9_data(self):
        """Load Task 9 data as fallback."""
        try:
            bridge = WebSocketBridge('data/task9/live_stream')
            bridge.initialize()
            data = bridge.get_latest_data()
            for symbol in ["NIFTY", "SENSEX"]:
                if symbol in data and data[symbol].get("ltp", 0) > 0:
                    self.task9_prices[symbol] = data[symbol]["ltp"]
                    logger.info(f"[TASK9] {symbol}: ₹{self.task9_prices[symbol]:.2f}")
        except Exception as e:
            logger.warning(f"[TASK9] Could not load data: {e}")
    
    def _authenticate(self) -> bool:
        """Authenticate with Angel One."""
        try:
            import requests
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
                    self.feed_token = result.get("data", {}).get("feedToken")
                    logger.info("✅ Angel One authentication successful")
                    return True
            
            logger.warning("⚠️ Authentication failed, using Task 9 data")
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Authentication error: {e}")
            return False
    
    def _parse_tick(self, data: bytes) -> Optional[Dict]:
        """Parse binary tick data from WebSocket."""
        try:
            if len(data) < 51:
                return None
            
            offset = 0
            
            # 1. Subscription Mode (1 byte)
            mode = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            # 2. Exchange Type (1 byte)
            exchange_type = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            # 3. Token (25 bytes - null terminated)
            token_bytes = data[offset:offset+25]
            token = token_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore')
            offset += 25
            
            # 4. Sequence Number (8 bytes)
            seq_num = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # 5. Exchange Timestamp (8 bytes)
            exchange_ts = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # 6. LTP (8 bytes) - price in paise, divide by 100
            ltp_raw = struct.unpack_from('<Q', data, offset)[0]
            ltp = ltp_raw / 100.0
            
            # Map token to symbol
            symbol = None
            for sym, tok in self.symbol_tokens.items():
                if tok == token:
                    symbol = sym
                    break
            
            if symbol:
                # Check if this is real data (ltp > 50)
                if ltp > 50:
                    self.use_websocket = True
                    self.real_prices[symbol] = ltp
                    logger.info(f"📊 REAL {symbol}: ₹{ltp:.2f}")
                else:
                    # Dummy data - use Task 9 fallback
                    ltp = self.task9_prices.get(symbol, 0)
                    self.real_prices[symbol] = ltp
                
                return {
                    "symbol": symbol,
                    "ltp": ltp,
                    "token": token,
                    "mode": mode,
                    "exchange_type": exchange_type,
                    "sequence": seq_num,
                    "exchange_timestamp": exchange_ts,
                    "timestamp": datetime.now().isoformat(),
                    "source": "WebSocket" if ltp > 50 else "Task9"
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def _generate_option_chain(self, symbol: str, ltp: float) -> List[Dict]:
        """Generate option chain."""
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
        """Get best strike."""
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
        """Get option chain."""
        return self.option_chain.get(symbol, [])
    
    async def connect(self):
        """Connect to WebSocket."""
        if not self.feed_token:
            logger.warning("⚠️ No feed token, using Task 9 data")
            asyncio.create_task(self._task9_fallback())
            return True
        
        try:
            ws_url = f"{self.ws_url}?clientCode={self.client_id}&feedToken={self.feed_token}&apiKey={self.api_key}"
            
            logger.info(f"🔌 Connecting to Angel One WebSocket...")
            
            self.websocket = await websockets.connect(
                ws_url,
                ping_interval=None,
                ping_timeout=None
            )
            
            logger.info("✅ WebSocket connected!")
            self.is_running = True
            
            # Subscribe to tokens
            request = {
                "correlationID": "sub001",
                "action": 1,
                "params": {
                    "mode": 1,
                    "tokenList": [
                        {"exchangeType": 1, "tokens": ["9999", "9998"]}
                    ]
                }
            }
            await self.websocket.send(json.dumps(request))
            logger.info("📡 Subscribed to NIFTY and SENSEX")
            
            # Start receiving data
            asyncio.create_task(self._receive_data())
            
            # Also start fallback (for when WebSocket gives dummy data)
            asyncio.create_task(self._task9_fallback())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            logger.info("⚠️ Using Task 9 fallback")
            asyncio.create_task(self._task9_fallback())
            return True
    
    async def _receive_data(self):
        """Receive and process data."""
        while self.is_running and self.websocket:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=35)
                
                if isinstance(message, bytes):
                    tick = self._parse_tick(message)
                    if tick:
                        symbol = tick.get("symbol")
                        ltp = tick.get("ltp", 0)
                        
                        if symbol and ltp > 0:
                            self.latest_data[symbol] = {
                                "ltp": ltp,
                                "timestamp": tick.get("timestamp"),
                                "source": tick.get("source", "WebSocket")
                            }
                            
                            chain = self._generate_option_chain(symbol, ltp)
                            self.option_chain[symbol] = chain
                            
                            best = self._get_best_strike(symbol, chain)
                            self.latest_data[symbol]["best_call"] = best
                            self.latest_data[symbol]["option_chain"] = chain
                            
                            for callback in self.subscribers:
                                try:
                                    await callback(self.latest_data[symbol])
                                except:
                                    pass
                            
                            if self.tick_count % 5 == 0:
                                logger.info(f"📊 {symbol}: ₹{ltp:,.2f} | Best: {best.get('strike', 0)} @ ₹{best.get('premium', 0):.2f}")
                            
                            self.tick_count += 1
                            
                elif isinstance(message, str):
                    if message == "pong":
                        pass
                    else:
                        try:
                            data = json.loads(message)
                            if "errorCode" in data:
                                logger.error(f"❌ Error: {data}")
                        except:
                            pass
                            
            except asyncio.TimeoutError:
                try:
                    await self.websocket.send("ping")
                except:
                    pass
            except websockets.exceptions.ConnectionClosed:
                logger.warning("⚠️ WebSocket disconnected, using fallback")
                asyncio.create_task(self._task9_fallback())
                break
            except Exception as e:
                logger.error(f"❌ Receive error: {e}")
                await asyncio.sleep(1)
    
    async def _task9_fallback(self):
        """Task 9 fallback data."""
        logger.info("📊 Using Task 9 fallback data")
        
        while self.is_running:
            # Use Task 9 prices with small movement
            for symbol in ["NIFTY", "SENSEX"]:
                base = self.task9_prices.get(symbol, 24461.3 if symbol == "NIFTY" else 78180.31)
                change = random.uniform(-0.0003, 0.0003) * base
                ltp = round(base + change, 2)
                
                self.latest_data[symbol] = {
                    "ltp": ltp,
                    "timestamp": datetime.now().isoformat(),
                    "source": "Task9 Fallback"
                }
                
                chain = self._generate_option_chain(symbol, ltp)
                self.option_chain[symbol] = chain
                
                best = self._get_best_strike(symbol, chain)
                self.latest_data[symbol]["best_call"] = best
                self.latest_data[symbol]["option_chain"] = chain
                
                for callback in self.subscribers:
                    try:
                        await callback(self.latest_data[symbol])
                    except:
                        pass
                
                if self.tick_count % 5 == 0:
                    logger.info(f"📊 {symbol}: ₹{ltp:,.2f} | Best: {best.get('strike', 0)} @ ₹{best.get('premium', 0):.2f}")
            
            self.tick_count += 1
            await asyncio.sleep(2)
    
    async def poll_data(self):
        """Alias for compatibility."""
        pass
    
    def stop(self):
        """Stop the collector."""
        self.is_running = False
        if self.websocket:
            try:
                asyncio.create_task(self.websocket.close())
            except:
                pass
        logger.info("🛑 WebSocket collector stopped")
