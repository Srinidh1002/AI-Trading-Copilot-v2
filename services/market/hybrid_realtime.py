# services/market/hybrid_realtime.py - HYBRID REAL-TIME DATA SOURCE

import time
import json
import random
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class HybridRealtime:
    """Hybrid real-time data - WebSocket + Simulated movements."""
    
    def __init__(self):
        self.last_update = 0
        self.update_interval = 2  # seconds
        
        # Base prices from WebSocket
        self.base_prices = {
            'NIFTY': 24461.3,
            'SENSEX': 78180.31
        }
        
        # Current prices (will update with simulation)
        self.current_prices = self.base_prices.copy()
        
        # Premiums
        self.premiums = {
            'NIFTY': 195.74,
            'SENSEX': 234.33
        }
        
        # Strikes
        self.strikes = {
            'NIFTY': 24450,
            'SENSEX': 78200
        }
        
        # Trend and volatility
        self.trend = {'NIFTY': 0, 'SENSEX': 0}
        self.volatility = {'NIFTY': 0.0003, 'SENSEX': 0.00025}
        self.trend_change = 0
        
        # Load from WebSocket
        self._load_from_websocket()
        
        logger.info("[HYBRID] Initialized with WebSocket data")
    
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
                            
                            # Calculate premium
                            if symbol == 'NIFTY':
                                self.premiums[symbol] = ltp * 0.008
                            else:
                                self.premiums[symbol] = ltp * 0.003
                            self.premiums[symbol] = max(10, round(self.premiums[symbol], 2))
                            
                            # Calculate strike
                            step = 50 if symbol == 'NIFTY' else 100
                            self.strikes[symbol] = round(ltp / step) * step
                            
                            logger.info(f"[HYBRID] Loaded {symbol}: ₹{ltp:.2f}")
        except Exception as e:
            logger.warning(f"[HYBRID] WebSocket load failed: {e}")
    
    def _simulate_movement(self):
        """Simulate realistic price movements."""
        # Change trend occasionally
        self.trend_change += 1
        if self.trend_change > random.randint(3, 6):
            self.trend_change = 0
            for symbol in ['NIFTY', 'SENSEX']:
                # Random walk with mean reversion
                self.trend[symbol] = random.uniform(-0.2, 0.2)
                # Sometimes add momentum
                if random.random() < 0.3:
                    self.trend[symbol] *= 1.5
        
        for symbol in ['NIFTY', 'SENSEX']:
            # Base movement
            movement = self.trend[symbol] * self.volatility[symbol] * 100
            
            # Add random noise
            noise = random.uniform(-0.5, 0.5) * self.volatility[symbol] * 50
            
            # Combined change
            change = movement + noise
            
            # Apply change
            self.current_prices[symbol] += change
            
            # Ensure price stays within 2% of base
            base = self.base_prices[symbol]
            max_change = base * 0.02  # 2% max
            if abs(self.current_prices[symbol] - base) > max_change:
                self.current_prices[symbol] = base + (max_change if self.current_prices[symbol] > base else -max_change)
            
            # Round to 2 decimals
            self.current_prices[symbol] = round(self.current_prices[symbol], 2)
            
            # Update premium
            if symbol == 'NIFTY':
                premium = self.current_prices[symbol] * 0.008
            else:
                premium = self.current_prices[symbol] * 0.003
            premium *= (1 + random.uniform(-0.02, 0.02))
            self.premiums[symbol] = max(10, round(premium, 2))
            
            # Update strike
            step = 50 if symbol == 'NIFTY' else 100
            self.strikes[symbol] = round(self.current_prices[symbol] / step) * step
    
    def update(self) -> Dict[str, Any]:
        """Update data with simulated movements."""
        now = time.time()
        if now - self.last_update >= self.update_interval:
            self.last_update = now
            self._simulate_movement()
        
        return self.get_current_data()
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current data."""
        return {
            'NIFTY': {
                'ltp': self.current_prices['NIFTY'],
                'premium': self.premiums['NIFTY'],
                'strike': self.strikes['NIFTY'],
                'timestamp': datetime.now().isoformat()
            },
            'SENSEX': {
                'ltp': self.current_prices['SENSEX'],
                'premium': self.premiums['SENSEX'],
                'strike': self.strikes['SENSEX'],
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def get_ltp(self, symbol: str) -> float:
        """Get LTP for a symbol."""
        data = self.get_current_data()
        return data.get(symbol, {}).get('ltp', 0)
    
    def get_premium(self, symbol: str) -> float:
        """Get premium for a symbol."""
        data = self.get_current_data()
        return data.get(symbol, {}).get('premium', 0)
    
    def get_strike(self, symbol: str) -> float:
        """Get ATM strike for a symbol."""
        data = self.get_current_data()
        return data.get(symbol, {}).get('strike', 0)
