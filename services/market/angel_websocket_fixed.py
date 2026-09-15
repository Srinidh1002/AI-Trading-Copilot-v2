# services/market/angel_websocket_fixed.py - WORKING WEBSOCKET CLIENT

import asyncio
import json
import logging
import struct
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import websockets
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AngelOneWebSocketFixed:
    """Working Angel One WebSocket Streaming 2.0 Client."""
    
    def __init__(self):
        # Read from .env
        self.api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
        self.client_id = os.getenv('ANGEL_CLIENT_ID', '')
        self.pin = os.getenv('ANGEL_PIN', '')
        self.totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
        
        self.ws_url = "wss://smartapisocket.angelone.in/smart-stream"
        self.session_token = None
        self.feed_token = None
        self.websocket = None
        self.is_connected = False
        self.is_running = False
        self.latest_data = {}
        self.subscribers = []
        
        # Token storage
        self.token_file = Path("data/angel_token.json")
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        # NIFTY and SENSEX tokens (NSE Cash Market)
        # These are the correct token IDs for indices
        self.symbol_tokens = {
            'NIFTY': '9999',   # NIFTY 50 Index
            'SENSEX': '9998'   # SENSEX Index
        }
        
        logger.info("[ANGEL-WS] WebSocket Streaming Client initialized")
    
    def _get_feed_token(self) -> Optional[str]:
        """Get feed token from cache or login."""
        try:
            # Check cached token
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    if tokens.get('expires_at', 0) > time.time():
                        self.session_token = tokens.get('session_token')
                        self.feed_token = tokens.get('feed_token')
                        logger.info("[ANGEL-WS] Using cached token")
                        if self.feed_token:
                            return self.feed_token
            
            # Need to login
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
                    logger.info(f"[ANGEL-WS] Using TOTP")
                except Exception as e:
                    logger.warning(f"[ANGEL-WS] TOTP generation failed: {e}")
            
            logger.info("[ANGEL-WS] Authenticating for WebSocket...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == True or result.get('status') == 'true':
                    data_obj = result.get('data', {})
                    
                    self.session_token = data_obj.get('jwtToken')
                    self.feed_token = data_obj.get('feedToken')
                    
                    if not self.feed_token:
                        self.feed_token = data_obj.get('feed_token')
                    
                    if self.feed_token:
                        tokens = {
                            'session_token': self.session_token,
                            'feed_token': self.feed_token,
                            'expires_at': time.time() + 86400
                        }
                        with open(self.token_file, 'w') as f:
                            json.dump(tokens, f)
                        
                        logger.info("[ANGEL-WS] Authentication successful!")
                        return self.feed_token
                    else:
                        logger.error("[ANGEL-WS] No feed token received")
                        return None
                else:
                    logger.error(f"[ANGEL-WS] Login failed: {result.get('message')}")
                    return None
            else:
                logger.error(f"[ANGEL-WS] HTTP error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[ANGEL-WS] Authentication error: {e}")
            return None
    
    def _get_headers(self) -> dict:
        """Get WebSocket connection headers."""
        return {
            "Authorization": f"Bearer {self.session_token}",
            "x-api-key": self.api_key,
            "x-client-code": self.client_id,
            "x-feed-token": self.feed_token
        }
    
    def _parse_tick(self, data: bytes) -> dict:
        """Parse binary tick data from WebSocket."""
        try:
            # Minimum packet size for LTP mode is 51 bytes
            if len(data) < 51:
                logger.debug(f"[ANGEL-WS] Data too short: {len(data)} bytes")
                return None
            
            offset = 0
            
            # Subscription Mode (1 byte)
            mode = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            # Exchange Type (1 byte)
            exchange_type = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            # Token (25 bytes - null terminated string)
            token_bytes = data[offset:offset+25]
            token = token_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore')
            offset += 25
            
            # Sequence Number (8 bytes)
            seq_num = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # Exchange Timestamp (8 bytes)
            exchange_ts = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # LTP (8 bytes) - Price is in paise, divide by 100
            ltp_raw = struct.unpack_from('<Q', data, offset)[0]
            ltp = ltp_raw / 100.0
            offset += 8
            
            # Log raw data for debugging
            logger.debug(f"[ANGEL-WS] Token: {token}, Mode: {mode}, LTP Raw: {ltp_raw}, LTP: {ltp}")
            
            # Map token to symbol
            symbol = None
            for sym, tok in self.symbol_tokens.items():
                if tok == token:
                    symbol = sym
                    break
            
            # If token not found, try to store it for debugging
            if not symbol:
                logger.debug(f"[ANGEL-WS] Unknown token: {token}")
                # Still try to map if token is known
                if token == '9999':
                    symbol = 'NIFTY'
                elif token == '9998':
                    symbol = 'SENSEX'
            
            if symbol and ltp > 0:
                self.latest_data[symbol] = {
                    'ltp': ltp,
                    'exchange_timestamp': datetime.fromtimestamp(exchange_ts/1000).isoformat() if exchange_ts > 0 else None,
                    'timestamp': datetime.now().isoformat()
                }
                
                return {
                    'symbol': symbol,
                    'ltp': ltp,
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"[ANGEL-WS] Parse error: {e}")
            return None
    
    async def _heartbeat(self):
        """Send heartbeat every 30 seconds."""
        while self.is_running and self.is_connected:
            try:
                await asyncio.sleep(30)
                if self.websocket:
                    await self.websocket.send("ping")
                    logger.debug("[ANGEL-WS] Heartbeat sent")
            except Exception as e:
                logger.error(f"[ANGEL-WS] Heartbeat error: {e}")
                break
    
    async def _subscribe_tokens(self):
        """Subscribe to tokens."""
        try:
            # Subscribe to NIFTY and SENSEX in LTP mode
            request = {
                "correlationID": "sub12345",
                "action": 1,  # Subscribe
                "params": {
                    "mode": 1,  # LTP mode
                    "tokenList": [
                        {
                            "exchangeType": 1,  # NSE Cash Market
                            "tokens": ["9999", "9998"]  # NIFTY and SENSEX
                        }
                    ]
                }
            }
            
            await self.websocket.send(json.dumps(request))
            logger.info(f"[ANGEL-WS] Subscribed to tokens: 9999 (NIFTY), 9998 (SENSEX)")
            
        except Exception as e:
            logger.error(f"[ANGEL-WS] Subscription error: {e}")
    
    async def connect(self):
        """Connect to WebSocket and start streaming."""
        # Get feed token
        self.feed_token = self._get_feed_token()
        
        if not self.feed_token:
            logger.error("[ANGEL-WS] No feed token available")
            return False
        
        if not self.session_token:
            logger.error("[ANGEL-WS] No session token available")
            return False
        
        try:
            logger.info(f"[ANGEL-WS] Connecting to {self.ws_url}")
            
            # Build URL with query parameters (browser-based client method)
            ws_url_with_params = (
                f"{self.ws_url}"
                f"?clientCode={self.client_id}"
                f"&feedToken={self.feed_token}"
                f"&apiKey={self.api_key}"
            )
            
            # Connect with query parameters
            self.websocket = await websockets.connect(
                ws_url_with_params,
                ping_interval=None,
                ping_timeout=None
            )
            
            self.is_connected = True
            self.is_running = True
            logger.info("[ANGEL-WS] WebSocket connected!")
            
            # Subscribe to tokens
            await self._subscribe_tokens()
            
            # Start heartbeat
            asyncio.create_task(self._heartbeat())
            
            # Start receiving data
            await self._receive_data()
            
            return True
            
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"[ANGEL-WS] Connection rejected: {e.status_code}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"[ANGEL-WS] Connection error: {e}")
            self.is_connected = False
            return False
    
    async def _receive_data(self):
        """Receive and parse data from WebSocket."""
        while self.is_running and self.is_connected:
            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=35)
                
                if isinstance(message, bytes):
                    tick = self._parse_tick(message)
                    if tick:
                        for callback in self.subscribers:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(tick)
                                else:
                                    callback(tick)
                            except Exception as e:
                                logger.error(f"[ANGEL-WS] Subscriber error: {e}")
                elif isinstance(message, str):
                    if message == "pong":
                        logger.debug("[ANGEL-WS] Heartbeat received")
                    else:
                        try:
                            data = json.loads(message)
                            if 'errorCode' in data:
                                logger.error(f"[ANGEL-WS] Error: {data}")
                            else:
                                logger.debug(f"[ANGEL-WS] Message: {message}")
                        except:
                            logger.debug(f"[ANGEL-WS] Text: {message}")
                            
            except asyncio.TimeoutError:
                try:
                    await self.websocket.send("ping")
                except:
                    pass
            except websockets.exceptions.ConnectionClosed:
                logger.warning("[ANGEL-WS] Connection closed")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"[ANGEL-WS] Receive error: {e}")
                await asyncio.sleep(1)
    
    def get_latest_data(self) -> dict:
        """Get latest market data."""
        return self.latest_data
    
    async def subscribe(self, callback: Callable):
        """Subscribe to data updates."""
        self.subscribers.append(callback)
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        self.is_running = False
        self.is_connected = False
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        logger.info("[ANGEL-WS] Disconnected")
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
