# services/market/realtime_price.py - REAL-TIME PRICE UPDATES

import random
import time
from datetime import datetime
from typing import Dict, Any

class RealtimePriceSimulator:
    """Simulates real-time price movements with realistic volatility."""
    
    def __init__(self):
        self.base_prices = {
            'NIFTY': 24461.3,
            'SENSEX': 78180.31
        }
        self.current_prices = self.base_prices.copy()
        self.last_update = time.time()
        self.volatility = {
            'NIFTY': 0.0005,  # 0.05% per tick
            'SENSEX': 0.0004
        }
        self.trend = {
            'NIFTY': 0,  # -1 to 1
            'SENSEX': 0
        }
        self.trend_change_counter = 0
        
        # Option premiums (will be calculated from underlying)
        self.premiums = {
            'NIFTY': 195.74,
            'SENSEX': 234.33
        }
        
        print("[REALTIME] Price simulator initialized")
    
    def update(self) -> Dict[str, Any]:
        """Update prices with realistic movements."""
        now = time.time()
        dt = now - self.last_update
        self.last_update = now
        
        # Change trend occasionally
        self.trend_change_counter += 1
        if self.trend_change_counter > random.randint(3, 8):
            self.trend_change_counter = 0
            # Random walk with bias
            for symbol in ['NIFTY', 'SENSEX']:
                self.trend[symbol] = random.uniform(-0.3, 0.3)
                # Add some momentum
                if random.random() < 0.3:
                    self.trend[symbol] *= 1.5
        
        # Update prices
        for symbol in ['NIFTY', 'SENSEX']:
            # Base movement
            movement = self.trend[symbol] * self.volatility[symbol] * 100
            
            # Add random noise
            noise = random.uniform(-0.5, 0.5) * self.volatility[symbol] * 50
            
            # Combined change
            change = movement + noise
            
            # Apply change
            self.current_prices[symbol] += change
            
            # Ensure price stays within reasonable range
            base = self.base_prices[symbol]
            max_change = base * 0.01  # 1% max change
            if abs(self.current_prices[symbol] - base) > max_change:
                self.current_prices[symbol] = base + (max_change if self.current_prices[symbol] > base else -max_change)
            
            # Update option premiums based on underlying
            if symbol == 'NIFTY':
                self.premiums[symbol] = self.current_prices[symbol] * 0.008
            else:
                self.premiums[symbol] = self.current_prices[symbol] * 0.003
            
            # Add slight random variation to premium
            self.premiums[symbol] *= (1 + random.uniform(-0.02, 0.02))
            self.premiums[symbol] = max(10, round(self.premiums[symbol], 2))
        
        return {
            'NIFTY': {
                'ltp': round(self.current_prices['NIFTY'], 2),
                'premium': self.premiums['NIFTY'],
                'timestamp': datetime.now().isoformat()
            },
            'SENSEX': {
                'ltp': round(self.current_prices['SENSEX'], 2),
                'premium': self.premiums['SENSEX'],
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current prices without updating."""
        return {
            'NIFTY': {
                'ltp': round(self.current_prices['NIFTY'], 2),
                'premium': self.premiums['NIFTY'],
                'timestamp': datetime.now().isoformat()
            },
            'SENSEX': {
                'ltp': round(self.current_prices['SENSEX'], 2),
                'premium': self.premiums['SENSEX'],
                'timestamp': datetime.now().isoformat()
            }
        }
