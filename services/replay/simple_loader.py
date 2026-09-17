"""
Simple Replay Loader - Fallback when full replay system is unavailable.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def generate_synthetic_data(market: str, days: int = 5) -> List[Dict]:
    "Generate synthetic market data for testing."
    base_price = 25000 if market == "NIFTY" else 85000
    volatility = 0.01
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    data = []
    current_price = base_price
    
    for i in range(days * 390):
        timestamp = start_date + timedelta(minutes=i)
        change = current_price * volatility * random.gauss(0, 1)
        current_price += change
        
        data.append({
            "timestamp": timestamp.isoformat(),
            "open": float(current_price),
            "high": float(current_price * (1 + abs(random.gauss(0, 0.005)))),
            "low": float(current_price * (1 - abs(random.gauss(0, 0.005)))),
            "close": float(current_price),
            "volume": float(random.randint(100000, 1000000)),
            "price": float(current_price),
            "market": market,
            "vwap": float(current_price * (1 + random.gauss(0, 0.002))),
            "rsi": float(50 + random.gauss(0, 10)),
            "trend": random.choice(["BULLISH", "BEARISH", "SIDEWAYS"]),
            "regime": random.choice(["BULL", "RANGE", "BEAR"]),
        })
    
    return data


class SimpleReplayLoader:
    "Simple replay loader that generates synthetic data."
    
    def load_market_data(self, market: str, days: int = 5) -> List[Dict]:
        "Load market data for replay."
        return generate_synthetic_data(market, days)
