"""FII/DII Fetcher - Properly labeled as previous-session flows."""
import time
from datetime import datetime

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


class FIIDIIEngine:
    def __init__(self, cache_ttl=1800):
        self.cache_ttl = cache_ttl
        self._cache = None
        self._cache_at = None
    
    def fetch(self, force=False):
        if not force and self._cache and (time.time() - self._cache_at) < self.cache_ttl:
            return self._cache
        
        result = {
            "status": "EVIDENCE_UNAVAILABLE",
            "type": "PREVIOUS_SESSION_CASH_FLOW",  # Explicit label
            "trade_date": None,
            "fii_cash_net": None,
            "dii_cash_net": None,
            "combined_net": None,
            "bias": "UNKNOWN",
        }
        
        if not REQUESTS_OK:
            return result
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/",
            }
            r = requests.get(
                "https://www.nseindia.com/api/fiidiiTradeReact",
                headers=headers,
                timeout=8,
            )
            if r.status_code != 200:
                return result
            
            data = r.json()
            for row in data:
                cat = row.get("category", "").upper()
                try:
                    net = float(str(row.get("netValue", "0")).replace(",", ""))
                except Exception:
                    net = 0
                
                if "FII" in cat or "FPI" in cat:
                    result["fii_cash_net"] = net
                elif "DII" in cat:
                    result["dii_cash_net"] = net
                
                # Trade date from first row
                if not result["trade_date"]:
                    result["trade_date"] = row.get("date")
            
            fii = result["fii_cash_net"] or 0
            dii = result["dii_cash_net"] or 0
            combined = fii + dii
            result["combined_net"] = round(combined, 2)
            
            if combined > 500:
                result["bias"] = "BULLISH"
            elif combined < -500:
                result["bias"] = "BEARISH"
            else:
                result["bias"] = "NEUTRAL"
            
            result["status"] = "OK"
            self._cache = result
            self._cache_at = time.time()
            return result
        except Exception as e:
            result["error"] = str(e)[:50]
            return result
    
    def describe(self):
        r = self.fetch()
        if r.get("status") != "OK":
            return f"FII/DII UNAVAILABLE"
        return (f"PREV_SESSION[{r['trade_date']}] "
                f"FII=₹{r['fii_cash_net']:.0f}Cr DII=₹{r['dii_cash_net']:.0f}Cr "
                f"combined=₹{r['combined_net']:.0f}Cr bias={r['bias']}")


if __name__ == "__main__":
    eng = FIIDIIEngine()
    r = eng.fetch()
    print(f"Status: {r.get('status')}")
    if r.get("status") == "OK":
        print(f"Trade Date: {r['trade_date']}")
        print(f"FII net: ₹{r['fii_cash_net']:.0f} Cr")
        print(f"DII net: ₹{r['dii_cash_net']:.0f} Cr")
        print(f"Combined: ₹{r['combined_net']:.0f} Cr")
        print(f"Bias: {r['bias']}")
        print()
        print(f"Summary: {eng.describe()}")
    else:
        print(f"Error: {r.get('error')}")
