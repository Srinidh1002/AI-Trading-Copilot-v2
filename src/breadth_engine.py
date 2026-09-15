"""Market Breadth - A/D, weighted A/D, % above VWAP/EMA."""
from typing import List, Dict


class BreadthEngine:
    def __init__(self):
        pass
    
    def compute(self, stocks: List[Dict]) -> Dict:
        """Compute breadth from stock list.
        Each stock dict: {symbol, weight, change_pct, above_vwap (bool), above_ema20 (bool)}
        """
        if not stocks:
            return {"status": "EVIDENCE_UNAVAILABLE"}
        
        advancing = [s for s in stocks if s.get("change_pct", 0) > 0.1]
        declining = [s for s in stocks if s.get("change_pct", 0) < -0.1]
        unchanged = [s for s in stocks if -0.1 <= s.get("change_pct", 0) <= 0.1]
        
        total = len(stocks)
        total_weight = sum(s.get("weight", 0) for s in stocks) or 1.0
        
        weight_advancing = sum(s.get("weight", 0) for s in advancing)
        weight_declining = sum(s.get("weight", 0) for s in declining)
        
        above_vwap = sum(1 for s in stocks if s.get("above_vwap") is True)
        below_vwap = sum(1 for s in stocks if s.get("above_vwap") is False)
        above_ema20 = sum(1 for s in stocks if s.get("above_ema20") is True)
        
        # Breadth bias
        up_pct = (weight_advancing / total_weight) * 100
        down_pct = (weight_declining / total_weight) * 100
        
        if up_pct > down_pct * 1.5 and up_pct > 40:
            bias = "BULLISH"
        elif down_pct > up_pct * 1.5 and down_pct > 40:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return {
            "status": "OK",
            "total": total,
            "advancing": len(advancing),
            "declining": len(declining),
            "unchanged": len(unchanged),
            "weight_advancing_pct": round(up_pct, 1),
            "weight_declining_pct": round(down_pct, 1),
            "above_vwap_count": above_vwap,
            "below_vwap_count": below_vwap,
            "above_vwap_pct": round((above_vwap / total) * 100, 1) if total else 0,
            "above_ema20_count": above_ema20,
            "bias": bias,
        }


if __name__ == "__main__":
    eng = BreadthEngine()
    stocks = [
        {"symbol": "HDFCBANK", "weight": 10.6, "change_pct": 0.5, "above_vwap": True},
        {"symbol": "ICICIBANK", "weight": 8.3, "change_pct": -0.8, "above_vwap": False},
        {"symbol": "RELIANCE", "weight": 8.3, "change_pct": -0.6, "above_vwap": False},
        {"symbol": "BHARTIARTL", "weight": 5.2, "change_pct": 1.1, "above_vwap": True},
        {"symbol": "LT", "weight": 4.4, "change_pct": 0.3, "above_vwap": True},
        {"symbol": "SBIN", "weight": 4.0, "change_pct": 0.4, "above_vwap": True},
        {"symbol": "INFY", "weight": 3.6, "change_pct": -0.2, "above_vwap": False},
        {"symbol": "AXISBANK", "weight": 3.4, "change_pct": 0.6, "above_vwap": True},
        {"symbol": "KOTAKBANK", "weight": 2.8, "change_pct": 0.05, "above_vwap": None},
        {"symbol": "M&M", "weight": 2.7, "change_pct": -0.9, "above_vwap": False},
    ]
    r = eng.compute(stocks)
    for k, v in r.items():
        print(f"  {k}: {v}")
