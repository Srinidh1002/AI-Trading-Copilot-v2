"""
Volume Engine
"""

from typing import Dict, Optional
import pandas as pd


def analyze_volume(snapshot: Dict) -> Dict:
    """
    Analyze volume from market data.
    
    Args:
        snapshot: Market snapshot with volume data
        
    Returns:
        Dict with volume metrics
    """
    history = snapshot.get("history")
    if history is None or history.empty:
        return {
            "volume": 0,
            "volume_ratio": 1.0,
            "regime": "NORMAL",
            "reasons": ["No data available"]
        }
    
    volume = history["volume"]
    current_volume = volume.iloc[-1]
    avg_volume = volume.rolling(20).mean().iloc[-1]
    
    if avg_volume > 0:
        volume_ratio = current_volume / avg_volume
    else:
        volume_ratio = 1.0
    
    # Determine regime
    if volume_ratio > 1.5:
        regime = "HIGH"
    elif volume_ratio > 0.5:
        regime = "NORMAL"
    else:
        regime = "LOW"
    
    return {
        "volume": float(current_volume),
        "volume_ratio": float(volume_ratio),
        "regime": regime,
        "reasons": [f"Volume ratio: {volume_ratio:.2f}"]
    }


class VolumeEngine:
    """Volume analysis engine."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
    
    def analyze(self, data: Dict) -> Dict:
        """Analyze volume."""
        return analyze_volume(data)
