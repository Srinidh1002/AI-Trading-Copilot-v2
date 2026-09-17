"""
Volatility Engine
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np


def analyze_volatility(snapshot: Dict) -> Dict:
    """
    Analyze volatility from market data.
    
    Args:
        snapshot: Market snapshot with price data
        
    Returns:
        Dict with volatility metrics
    """
    history = snapshot.get("history")
    if history is None or history.empty:
        return {
            "volatility": 0,
            "atr": 0,
            "volatility_percent": 0,
            "regime": "LOW",
            "reasons": ["No data available"]
        }
    
    # Calculate daily returns
    close = history["close"]
    returns = close.pct_change().dropna()
    
    if len(returns) < 2:
        return {
            "volatility": 0,
            "atr": 0,
            "volatility_percent": 0,
            "regime": "LOW",
            "reasons": ["Insufficient data"]
        }
    
    # Calculate volatility
    volatility = returns.std() * np.sqrt(252) * 100  # Annualized
    atr = (history["high"] - history["low"]).rolling(14).mean().iloc[-1]
    
    # Determine regime
    if volatility > 30:
        regime = "HIGH"
    elif volatility > 20:
        regime = "MEDIUM"
    else:
        regime = "LOW"
    
    return {
        "volatility": float(volatility),
        "atr": float(atr),
        "volatility_percent": float(volatility),
        "regime": regime,
        "reasons": [f"Volatility regime: {regime} ({volatility:.2f}%)"]
    }


class VolatilityEngine:
    """Volatility analysis engine."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
    
    def analyze(self, data: Dict) -> Dict:
        """Analyze volatility."""
        return analyze_volatility(data)
