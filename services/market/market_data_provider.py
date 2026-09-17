# services/market/market_data_provider.py

import asyncio
import logging
from typing import Dict, Optional, Callable
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)

class MarketDataProvider:
    """Market data provider with REST API fallback"""
    
    def __init__(self):
        self.is_websocket_mode = False
        self.latest_data = {}
        self.subscribers = []
        self.is_running = False
        
        # REST API endpoints
        self.base_url = "https://api.angelone.in"
        self.jwt_token = None
        self.api_key = None
        
    def initialize(self, jwt_token: str, api_key: str):
        """Initialize with credentials"""
        self.jwt_token = jwt_token
        self.api_key = api_key
        logger.info("✅ Market data provider initialized")
        
    async def get_ltp_rest(self, symbol: str, token: str, exchange: str) -> Optional[float]:
        """Get LTP via REST API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.jwt_token}',
                'x-api-key': self.api_key,
                'Accept': 'application/json'
            }
            
            # Adjust endpoint based on your Angel One API
            url = f"{self.base_url}/rest/secure/ltp"
            payload = {
                'symboltoken': token,
                'exchange': exchange
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status'):
                            ltp = float(data['data']['ltp'])
                            tick_data = {
                                'symbol': symbol,
                                'token': token,
                                'exchange': exchange,
                                'ltp': ltp,
                                'timestamp': datetime.now().isoformat()
                            }
                            self.latest_data[symbol] = tick_data
                            return tick_data
                    else:
                        logger.error(f"REST API error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"REST API error: {e}")
            return None
            
    async def poll_data(self):
        """Poll data using REST API"""
        self.is_running = True
        
        symbols = {
            'NIFTY': {'token': '99926000', 'exchange': 'NSE'},
            'SENSEX': {'token': '99919000', 'exchange': 'BSE'}
        }
        
        while self.is_running:
            for symbol, info in symbols.items():
                tick_data = await self.get_ltp_rest(symbol, info['token'], info['exchange'])
                if tick_data:
                    # Notify subscribers
                    for subscriber in self.subscribers:
                        try:
                            if asyncio.iscoroutinefunction(subscriber):
                                await subscriber(tick_data)
                            else:
                                subscriber(tick_data)
                        except Exception as e:
                            logger.error(f"Error notifying subscriber: {e}")
                            
            await asyncio.sleep(2)  # Poll every 2 seconds
            
    def subscribe(self, callback: Callable):
        """Add a subscriber"""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            
    def get_latest(self, symbol: str = None) -> dict:
        """Get latest data"""
        if symbol:
            return self.latest_data.get(symbol)
        return self.latest_data.copy()
        
    def stop(self):
        """Stop polling"""
        self.is_running = False
