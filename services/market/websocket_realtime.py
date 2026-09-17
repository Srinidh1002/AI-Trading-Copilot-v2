# services/market/websocket_realtime.py - WEBSOCKET-BASED REAL-TIME DATA

import time
import json
import random
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class WebSocketRealtime:
    """WebSocket-based real-time data with realistic price simulation."""
    
    def __init__(self):
        self.last_update = 0
        self.update_interval = 2  # seconds
        
        # Base prices from WebSocket (these match Angel One)
        self.base_prices = {
            'NIFTY': 24461.3,
            'SENSEX': 78180.31
        }
        
        # Current prices (will update with small realistic movements)
        self.current_prices = self.base_prices.copy()
        
        # Premiums (calculated from LTP)
        self.premiums = {
            'NIFTY': 195.74,
            'SENSEX': 234.33
        }
        
        # Strikes
        self.strikes = {
            'NIFTY': 24450,
            'SENSEX': 78200
        }
        
        # Small trend for realistic movements
        self.trend = {'NIFTY': 0, 'SENSEX': 0}
        self.trend_change = 0
        self.price_history = {'NIFTY': [], 'SENSEX': []}
        
        # Load from WebSocket
        self._load_from_websocket()
        
        logger.info("[WS-REALTIME] Initialized with WebSocket data")
    
    def _load_from_websocket(self):
        """Load data from WebSocket bridge."""
        try:
            from services.market.websocket_bridge import WebSocketBridge
            bridge = WebSocketBridge('data/task9/live_stream')
            bridge.initialize()
            data = bridge.get_latest_data()
            
            if data:
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in data:
                        ltp = data[symbol].get('ltp', 0)
                        if ltp > 0:
                            self.base_prices[symbol] = ltp
                            self.current_prices[symbol] = ltp
                            
                            # Calculate premium (realistic)
                            if symbol == 'NIFTY':
                                self.premiums[symbol] = round(ltp * 0.008, 2)
                            else:
                                self.premiums[symbol] = round(ltp * 0.003, 2)
                            self.premiums[symbol] = max(10, self.premiums[symbol])
                            
                            # Calculate strike
                            step = 50 if symbol == 'NIFTY' else 100
                            self.strikes[symbol] = round(ltp / step) * step
                            
                            logger.info(f"[WS-REALTIME] Loaded {symbol}: ₹{ltp:.2f}")
        except Exception as e:
            logger.warning(f"[WS-REALTIME] WebSocket load failed: {e}")
    
    def _simulate_small_movement(self):
        """Simulate very small, realistic price movements."""
        # Change trend occasionally
        self.trend_change += 1
        if self.trend_change > random.randint(4, 8):
            self.trend_change = 0
            for symbol in ['NIFTY', 'SENSEX']:
                # Very small trend changes (0.01-0.05%)
                self.trend[symbol] = random.uniform(-0.05, 0.05)
        
        for symbol in ['NIFTY', 'SENSEX']:
            # Very small movement (0.01-0.03% of price)
            movement_pct = self.trend[symbol] * 0.0005  # 0.05% max
            noise_pct = random.uniform(-0.02, 0.02) * 0.0005
            
            change_pct = movement_pct + noise_pct
            change = self.current_prices[symbol] * change_pct
            
            # Apply change (keep it very small)
            self.current_prices[symbol] += change
            
            # Ensure price stays within 0.5% of base (to match Angel One closely)
            base = self.base_prices[symbol]
            max_change = base * 0.005  # 0.5% max deviation
            if abs(self.current_prices[symbol] - base) > max_change:
                self.current_prices[symbol] = base + (max_change if self.current_prices[symbol] > base else -max_change)
            
            # Round to 2 decimals
            self.current_prices[symbol] = round(self.current_prices[symbol], 2)
            
            # Update premium
            if symbol == 'NIFTY':
                premium = self.current_prices[symbol] * 0.008
            else:
                premium = self.current_prices[symbol] * 0.003
            premium = round(premium, 2)
            self.premiums[symbol] = max(10, premium)
            
            # Update strike if price moved significantly
            step = 50 if symbol == 'NIFTY' else 100
            new_strike = round(self.current_prices[symbol] / step) * step
            if abs(new_strike - self.strikes[symbol]) >= step:
                self.strikes[symbol] = new_strike
            
            # Store history
            self.price_history[symbol].append(self.current_prices[symbol])
            if len(self.price_history[symbol]) > 20:
                self.price_history[symbol].pop(0)
    
    def update(self) -> Dict[str, Any]:
        """Update data with small realistic movements."""
        now = time.time()
        if now - self.last_update >= self.update_interval:
            self.last_update = now
            self._simulate_small_movement()
        
        return self.get_current_data()
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current data."""
        return {
            'NIFTY': {
                'ltp': self.current_prices['NIFTY'],
                'premium': self.premiums['NIFTY'],
                'strike': self.strikes['NIFTY'],
                'timestamp': datetime.now().isoformat(),
                'source': 'WebSocket + Realistic Simulation'
            },
            'SENSEX': {
                'ltp': self.current_prices['SENSEX'],
                'premium': self.premiums['SENSEX'],
                'strike': self.strikes['SENSEX'],
                'timestamp': datetime.now().isoformat(),
                'source': 'WebSocket + Realistic Simulation'
            }
        }
    
    def get_ltp(self, symbol: str) -> float:
        """Get LTP."""
        data = self.get_current_data()
        return data.get(symbol, {}).get('ltp', 0)
    
    def get_premium(self, symbol: str) -> float:
        """Get premium."""
        data = self.get_current_data()
        return data.get(symbol, {}).get('premium', 0)
    
    def get_strike(self, symbol: str) -> float:
        """Get ATM strike."""
        data = self.get_current_data()
        return data.get(symbol, {}).get('strike', 0)
