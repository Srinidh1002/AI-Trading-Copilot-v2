"""Enhanced VIX - Level + change + percentile + regime."""
import json
import time
from datetime import datetime, timedelta


class EnhancedVIX:
    INDEX_TOKEN = "99926017"
    EXCHANGE = "NSE"
    
    def __init__(self, obj, rate_limiter=None):
        self.obj = obj
        self.rate_limiter = rate_limiter
        self._cache = None
        self._cache_at = None
        self.cache_ttl = 300
    
    def fetch(self, force=False):
        if not force and self._cache and (time.time() - self._cache_at) < self.cache_ttl:
            return self._cache
        
        result = {"status": "EVIDENCE_UNAVAILABLE"}
        
        try:
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed("ltp_data")
            
            data = self.obj.ltpData(self.EXCHANGE, "INDIA VIX", self.INDEX_TOKEN)
            if not data or not data.get("data"):
                return result
            
            ltp = float(data["data"].get("ltp", 0))
            close = float(data["data"].get("close", 0))
            if ltp <= 0 or close <= 0:
                return result
            
            change_1d_pct = ((ltp - close) / close) * 100
            
            # Fetch 30-day daily candles for percentile
            percentile = None
            change_5d = None
            try:
                if self.rate_limiter:
                    self.rate_limiter.wait_if_needed("get_candle_data")
                
                from_date = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d 09:15")
                to_date = datetime.now().strftime("%Y-%m-%d 15:30")
                
                candles = self.obj.getCandleData({
                    "exchange": self.EXCHANGE,
                    "symboltoken": self.INDEX_TOKEN,
                    "interval": "ONE_DAY",
                    "fromdate": from_date,
                    "todate": to_date,
                })
                
                if candles and candles.get("data") and len(candles["data"]) >= 5:
                    closes = [float(row[4]) for row in candles["data"]]
                    # Percentile in available window
                    rank = sum(1 for c in closes if c < ltp) / len(closes) * 100
                    percentile = round(rank, 1)
                    if len(closes) >= 6:
                        c5 = closes[-6]
                        change_5d = ((ltp - c5) / c5) * 100
            except Exception:
                pass
            
            # Regime
            if ltp > 20:
                regime = "HIGH"
            elif ltp < 13:
                regime = "LOW"
            else:
                regime = "NORMAL"
            
            # Trend of VIX
            if change_1d_pct > 5:
                trend = "SPIKING"
            elif change_1d_pct > 1:
                trend = "RISING"
            elif change_1d_pct < -5:
                trend = "COLLAPSING"
            elif change_1d_pct < -1:
                trend = "FALLING"
            else:
                trend = "STABLE"
            
            result = {
                "status": "OK",
                "vix": round(ltp, 2),
                "prev_close": round(close, 2),
                "change_1d_pct": round(change_1d_pct, 2),
                "change_5d_pct": round(change_5d, 2) if change_5d is not None else None,
                "percentile_45d": percentile,
                "regime": regime,
                "trend": trend,
            }
            self._cache = result
            self._cache_at = time.time()
            return result
        except Exception as e:
            result["error"] = str(e)[:50]
            return result
    
    def describe(self):
        r = self.fetch()
        if r.get("status") != "OK":
            return "VIX_UNAVAILABLE"
        return f"{r['vix']} ({r['regime']}) {r['change_1d_pct']:+.2f}% trend={r['trend']}"


if __name__ == "__main__":
    print("EnhancedVIX module loaded OK")
    print(f"Index token: {EnhancedVIX.INDEX_TOKEN}")
