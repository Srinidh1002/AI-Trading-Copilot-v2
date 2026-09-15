# services/market/real_stock_collector_fixed.py - FIXED NIFTY CALCULATION

import asyncio
import logging
import json
import struct
import ssl
import os
import random
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
import websockets
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class RealStockCollectorFixed:
    """Real stock data collector - FIXED NIFTY/SENSEX calculation."""
    
    def __init__(self):
        self.subscribers: List[Callable] = []
        self.latest_data: Dict[str, Any] = {}
        self.option_chain: Dict[str, List[Dict]] = {}
        self.is_running = False
        self.websocket = None
        self.tick_count = 0
        self.stock_prices = {}
        self._recv_lock = asyncio.Lock()
        
        # Angel One credentials
        self.api_key = os.getenv("ANGEL_API_KEY", "") or os.getenv("ANGEL_APIKEY", "")
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "")
        self.pin = os.getenv("ANGEL_PIN", "")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "")
        
        self.ws_url = "wss://smartapisocket.angelone.in/smart-stream"
        self.session_token = None
        self.feed_token = None
        
        # Stock tokens
        self.stock_tokens = {
            "RELIANCE": "2885",
            "TCS": "11536",
            "HDFC": "1330",
            "HDFC_BANK": "341",
            "ICICI_BANK": "1333",
            "SBIN": "3045",
            "BHARTI": "10626",
            "INFY": "4083"
        }
        
        # Last known prices
        self.last_prices = {
            "RELIANCE": 1328.40,
            "TCS": 2309.00,
            "HDFC": 2724.30,
            "HDFC_BANK": 691.30,
            "ICICI_BANK": 715.30,
            "SBIN": 1019.40,
            "BHARTI": 1330.00,
            "INFY": 110.00
        }
        
        # NIFTY and SENSEX tracking (realistic range)
        self.nifty = 24461.3
        self.sensex = 78180.31
        self.nifty_base = 24461.3
        self.sensex_base = 78180.31
        
        # Lot sizes
        self.lot_sizes = {"NIFTY": 65, "SENSEX": 20}
        self.strike_steps = {"NIFTY": 50, "SENSEX": 100}
        
        # Authenticate
        self._authenticate()
        
        logger.info("✅ Real Stock Collector (Fixed) initialized")
    
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
            
            logger.warning("⚠️ Authentication failed")
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Authentication error: {e}")
            return False
    
    def _parse_tick(self, data: bytes) -> Optional[Dict]:
        """Parse binary tick data."""
        try:
            if len(data) < 51:
                return None
            
            offset = 0
            mode = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            exchange_type = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            token_bytes = data[offset:offset+25]
            token = token_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore')
            offset += 25
            seq_num = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            exchange_ts = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            ltp_raw = struct.unpack_from('<Q', data, offset)[0]
            ltp = ltp_raw / 100.0
            
            stock_name = None
            for name, tok in self.stock_tokens.items():
                if tok == token:
                    stock_name = name
                    break
            
            if stock_name and ltp > 0:
                return {
                    "symbol": stock_name,
                    "ltp": ltp,
                    "token": token,
                    "timestamp": datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def _calculate_nifty_sensex(self, stock_prices: dict) -> tuple:
        """Calculate NIFTY and SENSEX using realistic correlation."""
        if not stock_prices:
            return self.nifty, self.sensex
        
        # Calculate average change of all stocks
        total_change = 0
        count = 0
        
        for stock, current_price in stock_prices.items():
            base = self.last_prices.get(stock, 1)
            if base > 0:
                change_pct = (current_price - base) / base
                total_change += change_pct
                count += 1
        
        if count > 0:
            avg_change = total_change / count
            # Apply dampened change to NIFTY and SENSEX (0.5x)
            dampened_change = avg_change * 0.5
            new_nifty = self.nifty_base * (1 + dampened_change)
            new_sensex = self.sensex_base * (1 + dampened_change * 0.8)
            
            # Ensure values stay in realistic range
            new_nifty = max(24000, min(25000, new_nifty))
            new_sensex = max(77000, min(80000, new_sensex))
            
            return round(new_nifty, 2), round(new_sensex, 2)
        
        return self.nifty, self.sensex
    
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
    
    def _get_best_strike(self, symbol: str, ltp: float) -> Dict:
        """Get best strike."""
        chain = self._generate_option_chain(symbol, ltp)
        for strike_data in chain:
            if strike_data.get("is_atm", False):
                return {
                    "strike": strike_data["strike"],
                    "premium": strike_data["call_ltp"],
                    "score": 50,
                    "moneyness": "ATM"
                }
        return {"strike": 0, "premium": 0, "score": 0}
    
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
            logger.error("❌ No feed token")
            return False
        
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
            
            tokens = list(self.stock_tokens.values())
            request = {
                "correlationID": "sub001",
                "action": 1,
                "params": {
                    "mode": 1,
                    "tokenList": [
                        {"exchangeType": 1, "tokens": tokens}
                    ]
                }
            }
            await self.websocket.send(json.dumps(request))
            logger.info(f"📡 Subscribed to {len(tokens)} stocks")
            
            asyncio.create_task(self._receive_data())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            return False
    
    async def _receive_data(self):
        """Receive and process data."""
        stock_updates = {}
        
        while self.is_running and self.websocket:
            try:
                async with self._recv_lock:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=35)
                
                if isinstance(message, bytes):
                    tick = self._parse_tick(message)
                    if tick:
                        stock_name = tick.get("symbol")
                        ltp = tick.get("ltp", 0)
                        
                        if stock_name and ltp > 0:
                            stock_updates[stock_name] = ltp
                            self.last_prices[stock_name] = ltp
                            
                            # Calculate NIFTY and SENSEX
                            nifty, sensex = self._calculate_nifty_sensex(stock_updates)
                            self.nifty = nifty
                            self.sensex = sensex
                            
                            if self.tick_count % 5 == 0:
                                logger.info(f"📊 {stock_name}: ₹{ltp:.2f}")
                                logger.info(f"   NIFTY: ₹{nifty:.2f} | SENSEX: ₹{sensex:.2f}")
                            
                            self.tick_count += 1
                            
                            # Update data
                            for symbol, ltp_val in [("NIFTY", nifty), ("SENSEX", sensex)]:
                                self.latest_data[symbol] = {
                                    "ltp": ltp_val,
                                    "timestamp": datetime.now().isoformat(),
                                    "source": "Stock-derived"
                                }
                                
                                chain = self._generate_option_chain(symbol, ltp_val)
                                self.option_chain[symbol] = chain
                                
                                best = self._get_best_strike(symbol, ltp_val)
                                self.latest_data[symbol]["best_call"] = best
                                self.latest_data[symbol]["option_chain"] = chain
                            
                            # Notify subscribers
                            for callback in self.subscribers:
                                try:
                                    await callback(self.latest_data["NIFTY"])
                                    await callback(self.latest_data["SENSEX"])
                                except:
                                    pass
                            
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
                logger.warning("⚠️ WebSocket disconnected")
                await asyncio.sleep(2)
                await self.connect()
                break
            except Exception as e:
                logger.error(f"❌ Receive error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop the collector."""
        self.is_running = False
        if self.websocket:
            try:
                asyncio.create_task(self.websocket.close())
            except:
                pass
        logger.info("🛑 Real stock collector stopped")
