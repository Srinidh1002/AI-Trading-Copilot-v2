"""
Market Breadth Engine
"""

from typing import Dict, Optional
import pandas as pd


def analyze_market_breadth(data: Dict) -> Dict:
    """
    Analyze market breadth from market data.
    
    Args:
        data: Market snapshot with breadth data
        
    Returns:
        Dict with breadth metrics
    """
    # If no breadth data available, return default
    breadth_data = data.get("breadth", {})
    if not breadth_data:
        return {
            "advances": 0,
            "declines": 0,
            "advance_decline_ratio": 1.0,
            "breadth_score": 50,
            "regime": "NEUTRAL",
            "reasons": ["Breadth data not available"]
        }
    
    advances = breadth_data.get("advances", 0)
    declines = breadth_data.get("declines", 0)
    
    if declines > 0:
        ad_ratio = advances / declines
    else:
        ad_ratio = 1.0
    
    # Score based on ratio
    if ad_ratio > 1.5:
        regime = "BULLISH"
        score = 80
    elif ad_ratio > 1.0:
        regime = "POSITIVE"
        score = 65
    elif ad_ratio > 0.5:
        regime = "NEUTRAL"
        score = 50
    else:
        regime = "BEARISH"
        score = 30
    
    return {
        "advances": advances,
        "declines": declines,
        "advance_decline_ratio": float(ad_ratio),
        "breadth_score": score,
        "regime": regime,
        "reasons": [f"AD Ratio: {ad_ratio:.2f} - {regime}"]
    }


class MarketBreadthEngine:
    """Market breadth analysis engine."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
    
    def analyze(self, data: Dict) -> Dict:
        """Analyze market breadth."""
        return analyze_market_breadth(data)
