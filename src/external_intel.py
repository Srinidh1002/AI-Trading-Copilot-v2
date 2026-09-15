"""External Intelligence - Enhanced global/commodity/FX with freshness + regime.
"""
import time
from datetime import datetime, timedelta

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False


class ExternalIntelEngine:
    GLOBAL = {
        "Dow": "^DJI", "SP500": "^GSPC", "Nasdaq": "^IXIC",
        "Nikkei": "^N225", "HangSeng": "^HSI",
        "FTSE": "^FTSE", "DAX": "^GDAXI",
        "US10Y": "^TNX", "DXY": "DX-Y.NYB",
        "Brent": "BZ=F", "WTI": "CL=F",
        "USDINR": "USDINR=X", "Gold": "GC=F",
    }
    
    # Market session label by ticker
    SESSION_LABELS = {
        "Dow": "US_PREV_CLOSE", "SP500": "US_PREV_CLOSE", "Nasdaq": "US_PREV_CLOSE",
        "Nikkei": "ASIA", "HangSeng": "ASIA",
        "FTSE": "EUROPE", "DAX": "EUROPE",
        "US10Y": "LIVE", "DXY": "LIVE",
        "Brent": "LIVE", "WTI": "LIVE",
        "USDINR": "LIVE", "Gold": "LIVE",
    }
    
    def __init__(self, cache_ttl=900):
        self.cache_ttl = cache_ttl
        self._cache = None
        self._cache_at = None
    
    def _fresh(self):
        if self._cache is None:
            return False
        return (time.time() - self._cache_at) < self.cache_ttl
    
    def fetch(self, force=False):
        if not force and self._fresh():
            return self._cache
        if not YF_AVAILABLE:
            return {"status": "YF_UNAVAILABLE"}
        
        result = {"status": "OK", "fetched_at": datetime.now().isoformat(), "markets": {}}
        fetched_count = 0
        now = datetime.now()
        
        for name, ticker in self.GLOBAL.items():
            try:
                hist = yf.Ticker(ticker).history(period="30d", interval="1d")
                if hist is None or len(hist) < 2:
                    result["markets"][name] = {"status": "EVIDENCE_UNAVAILABLE"}
                    continue
                
                close = hist["Close"]
                prev = float(close.iloc[-2]) if len(close) >= 2 else None
                curr = float(close.iloc[-1])
                
                change_1d = ((curr - prev) / prev * 100) if prev and prev > 0 else 0
                change_5d = None
                if len(close) >= 6:
                    c5 = float(close.iloc[-6])
                    change_5d = ((curr - c5) / c5 * 100) if c5 > 0 else 0
                change_20d = None
                if len(close) >= 21:
                    c20 = float(close.iloc[-21])
                    change_20d = ((curr - c20) / c20 * 100) if c20 > 0 else 0
                
                # Percentile in 30d window
                percentile = None
                if len(close) >= 10:
                    rank = (close < curr).sum() / len(close) * 100
                    percentile = round(float(rank), 1)
                
                result["markets"][name] = {
                    "status": "OK",
                    "value": round(curr, 4),
                    "prev": round(prev, 4) if prev else None,
                    "change_1d_pct": round(change_1d, 3),
                    "change_5d_pct": round(change_5d, 3) if change_5d is not None else None,
                    "change_20d_pct": round(change_20d, 3) if change_20d is not None else None,
                    "percentile_30d": percentile,
                    "session": self.SESSION_LABELS.get(name, "UNKNOWN"),
                    "age_hours": 0,
                }
                fetched_count += 1
            except Exception as e:
                result["markets"][name] = {"status": "ERROR", "error": str(e)[:50]}
        
        result["coverage"] = f"{fetched_count}/{len(self.GLOBAL)}"
        result["risk"] = self._classify_risk(result["markets"])
        result["crude"] = self._classify_crude(result["markets"].get("Brent", {}))
        
        self._cache = result
        self._cache_at = time.time()
        return result
    
    def _classify_risk(self, markets):
        """Aggregate risk score."""
        risk_on = 0
        risk_off = 0
        
        for name in ["Dow", "SP500", "Nasdaq", "Nikkei", "HangSeng", "FTSE", "DAX"]:
            m = markets.get(name, {})
            if m.get("status") != "OK":
                continue
            cp = m.get("change_1d_pct", 0)
            if cp > 0.3:
                risk_on += 1
            elif cp < -0.3:
                risk_off += 1
        
        # USDINR up = risk-off for India
        fx = markets.get("USDINR", {})
        if fx.get("status") == "OK":
            if fx.get("change_1d_pct", 0) > 0.3:
                risk_off += 1
            elif fx.get("change_1d_pct", 0) < -0.3:
                risk_on += 1
        
        if risk_on > risk_off:
            sentiment = "RISK_ON"
        elif risk_off > risk_on:
            sentiment = "RISK_OFF"
        else:
            sentiment = "NEUTRAL"
        
        total = risk_on + risk_off
        confidence = round(max(risk_on, risk_off) / total, 2) if total > 0 else 0.0
        
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "risk_on_count": risk_on,
            "risk_off_count": risk_off,
        }
    
    def _classify_crude(self, brent):
        if brent.get("status") != "OK":
            return {"status": "EVIDENCE_UNAVAILABLE"}
        
        price = brent.get("value", 0)
        pct = brent.get("percentile_30d", 50)
        
        # Absolute regime for India
        if price >= 100:
            regime = "EXTREME"
            india_pressure = "HIGH"
        elif price >= 85:
            regime = "HIGH"
            india_pressure = "ELEVATED"
        elif price >= 70:
            regime = "NORMAL"
            india_pressure = "MODERATE"
        else:
            regime = "LOW"
            india_pressure = "LOW"
        
        return {
            "status": "OK",
            "brent_price": round(price, 2),
            "change_1d_pct": brent.get("change_1d_pct"),
            "change_5d_pct": brent.get("change_5d_pct"),
            "percentile_30d": pct,
            "regime": regime,
            "india_macro_pressure": india_pressure,
        }
    
    def describe(self):
        """One-line summary."""
        if not self._cache:
            self.fetch()
        if self._cache.get("status") != "OK":
            return "EXTERNAL_UNAVAILABLE"
        
        r = self._cache["risk"]
        c = self._cache["crude"]
        
        crude_str = f"Brent=${c.get('brent_price', 0):.0f}({c.get('regime', '?')})"
        
        return f"RISK={r['sentiment']} (conf={r['confidence']}) | {crude_str} | coverage={self._cache['coverage']}"


if __name__ == "__main__":
    eng = ExternalIntelEngine()
    data = eng.fetch()
    print(f"Status: {data['status']}")
    print(f"Coverage: {data.get('coverage')}")
    print()
    print("Risk:", data.get("risk"))
    print("Crude:", data.get("crude"))
    print()
    print("Individual markets:")
    for name, m in data.get("markets", {}).items():
        if m.get("status") == "OK":
            print(f"  {name:10s} {m['value']:>10.3f}  1d={m['change_1d_pct']:+.2f}%  pct={m.get('percentile_30d')}")
        else:
            print(f"  {name:10s} {m.get('status')}")
    print()
    print(f"Summary: {eng.describe()}")
