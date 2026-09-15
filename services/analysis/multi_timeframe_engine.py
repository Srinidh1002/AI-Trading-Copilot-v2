"""
Multi Timeframe Engine V1
"""

import pandas as pd
from typing import Dict, List, Optional


def analyze_multi_timeframe(snapshot):
    """Analyze multi-timeframe data from a snapshot."""
    history = snapshot.get("history")
    if history is None or history.empty:
        return {
            "timeframe": "Unknown",
            "price": 0,
            "ema20": 0,
            "ema50": 0,
            "trend": "Unknown",
        }

    close = history["close"]

    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]

    current = close.iloc[-1]

    if current > ema20 > ema50:
        trend = "Bullish"
    elif current < ema20 < ema50:
        trend = "Bearish"
    else:
        trend = "Sideways"

    return {
        "timeframe": "5 Minute",
        "price": round(current, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "trend": trend,
    }


class MultiTimeframeEngine:
    """
    Multi-Timeframe Engine - Analyzes multiple timeframes.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.timeframes = self.config.get("timeframes", ["1m", "5m", "15m", "1h", "daily"])
    
    def analyze(self, snapshot: Dict) -> Dict:
        """Analyze multi-timeframe data."""
        results = {}
        alignment = 0
        total_analyzed = 0
        
        for tf in self.timeframes:
            tf_data = snapshot.get(tf, snapshot.get("history"))
            if tf_data is not None and not tf_data.empty:
                result = analyze_multi_timeframe({"history": tf_data})
                results[tf] = result
                total_analyzed += 1
                
                trend = result.get("trend", "Sideways")
                if trend == "Bullish":
                    alignment += 1
                elif trend == "Bearish":
                    alignment -= 1
        
        if total_analyzed > 0:
            alignment_ratio = alignment / total_analyzed
            if alignment_ratio > 0.5:
                overall_trend = "BULLISH"
            elif alignment_ratio < -0.5:
                overall_trend = "BEARISH"
            else:
                overall_trend = "MIXED"
        else:
            overall_trend = "UNKNOWN"
            alignment_ratio = 0
        
        return {
            "overall_trend": overall_trend,
            "alignment": alignment,
            "alignment_ratio": alignment_ratio,
            "total_analyzed": total_analyzed,
            "timeframe_results": results,
            "reasons": [f"Multi-timeframe analysis: {overall_trend} ({alignment}/{total_analyzed})"]
        }
