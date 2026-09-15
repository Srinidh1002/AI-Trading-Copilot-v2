"""Market Regime - Classifies market into TRENDING/RANGE/HIGH_VOL/CHOPPY."""


class MarketRegimeEngine:
    def classify(self, mtf_data, vwap_ctx=None, or_data=None):
        """Classify regime from MTF indicators + optional context.
        
        Args:
            mtf_data: dict {tf_name: indicator_dict} where each has 'status', 'trend', 'adx', 'atr_pct', 'rsi'
            vwap_ctx: {'vwap': float, 'high': float, 'low': float, 'position': 'ABOVE'/'BELOW'/'AT'}
            or_data: {'15m': {'high', 'low', 'width', 'status'}}
        """
        if not mtf_data:
            return {"regime": "UNKNOWN", "confidence": 0.0}
        
        # Collect available timeframes
        trends = []
        adxs = []
        atrs = []
        for tf, data in mtf_data.items():
            if not isinstance(data, dict) or data.get("status") != "OK":
                continue
            t = data.get("trend")
            if t in ("UP", "DOWN", "FLAT"):
                trends.append(t)
            if data.get("adx") is not None:
                adxs.append(data["adx"])
            if data.get("atr_pct") is not None:
                atrs.append(data["atr_pct"])
        
        if not trends:
            return {"regime": "UNKNOWN", "confidence": 0.0}
        
        avg_adx = sum(adxs) / len(adxs) if adxs else 0
        avg_atr_pct = sum(atrs) / len(atrs) if atrs else 0
        
        up = trends.count("UP")
        down = trends.count("DOWN")
        flat = trends.count("FLAT")
        total = len(trends)
        
        # High volatility check first
        if avg_atr_pct > 0.8:
            regime = "HIGH_VOLATILITY"
        # Strong trend
        elif avg_adx >= 25:
            if up > down:
                regime = "TRENDING_UP"
            elif down > up:
                regime = "TRENDING_DOWN"
            else:
                regime = "CHOPPY"
        # Weak ADX = range
        elif avg_adx < 15:
            if flat >= 2 or (up == down):
                regime = "RANGE_BOUND"
            else:
                regime = "LOW_VOLATILITY_COMPRESSION"
        # Moderate
        else:
            if up >= 3:
                regime = "TRENDING_UP"
            elif down >= 3:
                regime = "TRENDING_DOWN"
            elif abs(up - down) <= 1:
                regime = "RANGE_BOUND"
            else:
                regime = "CHOPPY"
        
        # Confidence based on how aligned trends are
        alignment = max(up, down) / total if total else 0
        confidence = round(alignment * min(1.0, avg_adx / 25), 2)
        
        return {
            "regime": regime,
            "confidence": confidence,
            "avg_adx": round(avg_adx, 1),
            "avg_atr_pct": round(avg_atr_pct, 3),
            "trends_summary": f"UP:{up} DOWN:{down} FLAT:{flat}",
        }


if __name__ == "__main__":
    eng = MarketRegimeEngine()
    
    # Test 1: Strong trend
    mtf = {
        "1h": {"status": "OK", "trend": "DOWN", "adx": 30, "atr_pct": 0.4, "rsi": 35},
        "15m": {"status": "OK", "trend": "DOWN", "adx": 28, "atr_pct": 0.35, "rsi": 33},
        "5m": {"status": "OK", "trend": "DOWN", "adx": 26, "atr_pct": 0.3, "rsi": 30},
    }
    print("Strong trend:", eng.classify(mtf))
    
    # Test 2: Range
    mtf2 = {
        "1h": {"status": "OK", "trend": "FLAT", "adx": 12, "atr_pct": 0.15},
        "15m": {"status": "OK", "trend": "FLAT", "adx": 10, "atr_pct": 0.12},
        "5m": {"status": "OK", "trend": "UP", "adx": 11, "atr_pct": 0.14},
    }
    print("Range:", eng.classify(mtf2))
    
    # Test 3: High vol
    mtf3 = {
        "1h": {"status": "OK", "trend": "DOWN", "adx": 22, "atr_pct": 0.9},
        "15m": {"status": "OK", "trend": "DOWN", "adx": 20, "atr_pct": 1.1},
    }
    print("High vol:", eng.classify(mtf3))
