"""
Support and Resistance Engine
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


def calculate_support_resistance(data: Dict) -> Dict:
    """
    Calculate support and resistance levels from market data.
    
    Args:
        data: Market snapshot with OHLCV data
        
    Returns:
        Dict with support and resistance levels
    """
    history = data.get("history")
    if history is None or history.empty:
        return {
            "support": 0,
            "resistance": 0,
            "support_levels": [],
            "resistance_levels": [],
            "reasons": ["No data available"]
        }
    
    close = history["close"]
    high = history["high"]
    low = history["low"]
    current_price = close.iloc[-1]
    
    # Use recent data for levels
    recent_high = high.iloc[-20:].max()
    recent_low = low.iloc[-20:].min()
    
    # Find pivot points (swing highs and lows)
    pivots_high = []
    pivots_low = []
    
    for i in range(2, len(close) - 2):
        if high.iloc[i] > high.iloc[i-1] and high.iloc[i] > high.iloc[i-2] and high.iloc[i] > high.iloc[i+1] and high.iloc[i] > high.iloc[i+2]:
            pivots_high.append(high.iloc[i])
        if low.iloc[i] < low.iloc[i-1] and low.iloc[i] < low.iloc[i-2] and low.iloc[i] < low.iloc[i+1] and low.iloc[i] < low.iloc[i+2]:
            pivots_low.append(low.iloc[i])
    
    # Get recent pivots
    support_levels = sorted(set(pivots_low[-5:])) if pivots_low else []
    resistance_levels = sorted(set(pivots_high[-5:]), reverse=True) if pivots_high else []
    
    # Find nearest support and resistance
    nearest_support = 0
    nearest_resistance = 0
    
    for level in support_levels:
        if level < current_price:
            nearest_support = max(nearest_support, level)
    
    for level in resistance_levels:
        if level > current_price:
            nearest_resistance = min(nearest_resistance, level) if nearest_resistance > 0 else level
    
    # If no pivots found, use recent high/low
    if nearest_support == 0:
        nearest_support = recent_low
        support_levels.append(nearest_support)
    
    if nearest_resistance == 0:
        nearest_resistance = recent_high
        resistance_levels.append(nearest_resistance)
    
    return {
        "support": float(nearest_support),
        "resistance": float(nearest_resistance),
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "current_price": float(current_price),
        "reasons": [
            f"Support at {nearest_support:.2f}",
            f"Resistance at {nearest_resistance:.2f}"
        ]
    }


class SupportResistanceEngine:
    """Support and Resistance analysis engine."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
    
    def analyze(self, data: Dict) -> Dict:
        """Calculate support and resistance levels."""
        return calculate_support_resistance(data)
