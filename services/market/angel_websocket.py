# services/market/angel_websocket.py - ANGEL ONE WEBSOCKET STREAMING

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


class AngelOneWebSocket:
    """Angel One WebSocket Streaming 2.0 Client."""
    
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
        
        # NIFTY and SENSEX tokens
        # NSE Cash Market tokens
        self.symbol_tokens = {
            'NIFTY': '9999',  # NIFTY 50 Index
            'SENSEX': '9998'   # SENSEX Index
        }
        
        logger.info("[ANGEL-WS] WebSocket Streaming Client initialized")
    
    def authenticate(self) -> bool:
        """Authenticate and get feed token."""
        try:
            # Check cached token
            if self.token_file.exists():
                with open(self.token_file, 'r') as f:
                    tokens = json.load(f)
                    if tokens.get('expires_at', 0) > time.time():
                        self.session_token = tokens.get('session_token')
                        self.feed_token = tokens.get('feed_token')
                        logger.info("[ANGEL-WS] Using cached token")
                        return True
            
            # Login to get feed token
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
                except:
                    pass
            
            logger.info("[ANGEL-WS] Authenticating for WebSocket...")
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == True or result.get('status') == 'true':
                    self.session_token = result.get('data', {}).get('session_token')
                    self.feed_token = result.get('data', {}).get('feed_token')
                    
                    # Save token
                    tokens = {
                        'session_token': self.session_token,
                        'feed_token': self.feed_token,
                        'expires_at': time.time() + 86400
                    }
                    with open(self.token_file, 'w') as f:
                        json.dump(tokens, f)
                    
                    logger.info("[ANGEL-WS] Authentication successful!")
                    return True
                else:
                    logger.error(f"[ANGEL-WS] Login failed: {result.get('message')}")
                    return False
            else:
                logger.error(f"[ANGEL-WS] HTTP error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[ANGEL-WS] Authentication error: {e}")
            return False
    
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
            # Parse according to Angel One WebSocket 2.0 spec
            offset = 0
            
            # Subscription Mode (1 byte)
            mode = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            # Exchange Type (1 byte)
            exchange_type = struct.unpack_from('<B', data, offset)[0]
            offset += 1
            
            # Token (25 bytes - null terminated string)
            token_bytes = data[offset:offset+25]
            token = token_bytes.split(b'\x00')[0].decode('utf-8')
            offset += 25
            
            # Sequence Number (8 bytes)
            seq_num = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # Exchange Timestamp (8 bytes)
            exchange_ts = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # LTP (8 bytes)
            ltp = struct.unpack_from('<Q', data, offset)[0] / 100.0
            offset += 8
            
            # Last traded quantity (8 bytes)
            ltq = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # Average traded price (8 bytes)
            avg_price = struct.unpack_from('<Q', data, offset)[0] / 100.0
            offset += 8
            
            # Volume traded for the day (8 bytes)
            volume = struct.unpack_from('<Q', data, offset)[0]
            offset += 8
            
            # Total buy quantity (8 bytes)
            total_buy = struct.unpack_from('<d', data, offset)[0]
            offset += 8
            
            # Total sell quantity (8 bytes)
            total_sell = struct.unpack_from('<d', data, offset)[0]
            offset += 8
            
            # Open price (8 bytes)
            open_price = struct.unpack_from('<Q', data, offset)[0] / 100.0
            offset += 8
            
            # High price (8 bytes)
            high_price = struct.unpack_from('<Q', data, offset)[0] / 100.0
            offset += 8
            
            # Low price (8 bytes)
            low_price = struct.unpack_from('<Q', data, offset)[0] / 100.0
            offset += 8
            
            # Close price (8 bytes)
            close_price = struct.unpack_from('<Q', data, offset)[0] / 100.0
            offset += 8
            
            # Map token to symbol
            symbol = None
            for sym, tok in self.symbol_tokens.items():
                if tok == token:
                    symbol = sym
                    break
            
            if symbol:
                self.latest_data[symbol] = {
                    'ltp': ltp,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume,
                    'avg_price': avg_price,
                    'exchange_timestamp': datetime.fromtimestamp(exchange_ts/1000).isoformat(),
                    'timestamp': datetime.now().isoformat()
                }
                
                logger.debug(f"[ANGEL-WS] {symbol}: LTP ₹{ltp:.2f}")
                
                return {
                    'symbol': symbol,
                    'ltp': ltp,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume,
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
            # Subscribe to NIFTY and SENSEX
            request = {
                "correlationID": "sub12345",
                "action": 1,  # Subscribe
                "params": {
                    "mode": 1,  # LTP mode
                    "tokenList": [
                        {
                            "exchangeType": 1,  # NSE Cash Market
                            "tokens": list(self.symbol_tokens.values())
                        }
                    ]
                }
            }
            
            await self.websocket.send(json.dumps(request))
            logger.info("[ANGEL-WS] Subscription request sent")
            
        except Exception as e:
            logger.error(f"[ANGEL-WS] Subscription error: {e}")
    
    async def connect(self):
        """Connect to WebSocket and start streaming."""
        if not self.authenticate():
            logger.error("[ANGEL-WS] Authentication failed")
            return False
        
        try:
            headers = self._get_headers()
            
            # Connect with headers
            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=headers,
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
            
        except Exception as e:
            logger.error(f"[ANGEL-WS] Connection error: {e}")
            self.is_connected = False
            return False
    
    async def _receive_data(self):
        """Receive and parse data from WebSocket."""
        while self.is_running and self.is_connected:
            try:
                message = await self.websocket.recv()
                
                if isinstance(message, bytes):
                    # Parse binary tick data
                    tick = self._parse_tick(message)
                    if tick:
                        # Notify subscribers
                        for callback in self.subscribers:
                            try:
                                await callback(tick)
                            except Exception as e:
                                logger.error(f"[ANGEL-WS] Subscriber error: {e}")
                elif isinstance(message, str):
                    # Text message (could be error or heartbeat response)
                    if message == "pong":
                        logger.debug("[ANGEL-WS] Heartbeat response received")
                    else:
                        try:
                            data = json.loads(message)
                            if 'errorCode' in data:
                                logger.error(f"[ANGEL-WS] Error: {data}")
                            else:
                                logger.debug(f"[ANGEL-WS] Message: {message}")
                        except:
                            logger.debug(f"[ANGEL-WS] Text: {message}")
                            
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
