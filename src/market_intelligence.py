"""Market Intelligence - Multi-timeframe, Global, VIX, FII/DII"""
import time
import requests
from datetime import datetime, timedelta

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

try:
    import pandas as pd
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


class MarketIntelligence:
    INDEX_TOKENS = {
        "NIFTY": {"exchange": "NSE", "token": "99926000"},
        "SENSEX": {"exchange": "BSE", "token": "99919000"},
        "INDIA_VIX": {"exchange": "NSE", "token": "99926017"},
    }
    
    GLOBAL_SYMBOLS = {
        "Dow": "^DJI", "SP500": "^GSPC", "Nasdaq": "^IXIC",
        "Nikkei": "^N225", "HangSeng": "^HSI",
        "Crude": "CL=F", "USDINR": "USDINR=X",
    }
    
    def __init__(self, obj, market="NIFTY", rate_limiter=None):
        self.obj = obj
        self.market = market
        self.rate_limiter = rate_limiter  # Optional centralized limiter
        self._cache = {}
        self._cache_time = {}
        self.cache_ttl = {
            "technicals": 600,
            "global": 1800,
            "vix": 300,
            "fii_dii": 3600,
            "candles_ONE_HOUR": 1800,
            "candles_FIFTEEN_MINUTE": 900,
            "candles_FIVE_MINUTE": 600,
        }
    
    def _fresh(self, key):
        if key not in self._cache_time:
            return False
        age = time.time() - self._cache_time[key]
        return age < self.cache_ttl.get(key, 300)
    
    def _store(self, key, val):
        self._cache[key] = val
        self._cache_time[key] = time.time()
    
    def _mark_failed(self, interval):
        self._cache_time["fail_" + interval] = time.time()
    
    def _recently_failed(self, interval):
        key = "fail_" + interval
        if key not in self._cache_time:
            return False
        return (time.time() - self._cache_time[key]) < 120
    
    def get_candles(self, interval, days_back=3):
        if self._recently_failed(interval):
            return pd.DataFrame()
        
        cache_key = "candles_" + interval
        if self._fresh(cache_key):
            return self._cache[cache_key]
        
        idx = self.INDEX_TOKENS[self.market]
        from_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M")
        to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # STRICT market identity - no cross-market fallback allowed
        attempts = [(idx["exchange"], idx["token"])]
        
        for exch, tok in attempts:
            try:
                if self.rate_limiter:
                    self.rate_limiter.wait_if_needed("get_candle_data")
                result = self.obj.getCandleData({
                    "exchange": exch,
                    "symboltoken": tok,
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date,
                })
                if result:
                    data = result.get("data")
                    n = len(data) if data else 0
                    print(f"    [debug] {interval} @{exch}: rows={n}")
                    if data and n > 0:
                        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        df["timestamp"] = pd.to_datetime(df["timestamp"])
                        for col in ["open", "high", "low", "close", "volume"]:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                        self._store(cache_key, df)
                        return df
            except Exception as e:
                err = str(e)
                # RULE 9: normalized error code; raw provider message preserved separately
                _el = err.lower()
                if "rate" in _el or "limit" in _el or "ab1021" in _el:
                    _norm = "RATE_LIMITED"
                elif "parse" in _el or "json" in _el or "decode" in _el:
                    _norm = "PARSE_FAILURE"
                elif "empty" in _el or "no data" in _el:
                    _norm = "EMPTY_RESPONSE"
                else:
                    _norm = "PROVIDER_ERROR"
                print(f"    [debug] {interval} @{exch}: {_norm} | provider_msg={err[:100]!r}")
                if "Access denied" in err or "AB1021" in err:
                    self._mark_failed(interval)
                    return pd.DataFrame()
            time.sleep(1.0)
        
        self._mark_failed(interval)
        return pd.DataFrame()
    
    def get_multi_timeframe_technicals(self):
        if self._fresh("technicals"):
            return self._cache["technicals"]
        
        if not TA_AVAILABLE:
            return {"error": "ta not available", "consensus": "UNKNOWN"}
        
        result = {}
        # 3 timeframes only (dropped 1m - too volatile + rate limited)
        timeframes = [
            ("1h", "ONE_HOUR", 10),
            ("15m", "FIFTEEN_MINUTE", 5),
            ("5m", "FIVE_MINUTE", 3),
        ]
        
        for tf_name, tf_interval, lookback in timeframes:
            try:
                df = self.get_candles(tf_interval, days_back=lookback)
                if df.empty or len(df) < 20:
                    result[tf_name] = {"trend": "UNKNOWN"}
                    continue
                
                close = df["close"]
                high = df["high"]
                low = df["low"]
                
                ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
                ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1] if len(df) >= 50 else None
                rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
                
                current = close.iloc[-1]
                
                if ema50 and current > ema20 > ema50:
                    trend = "UP"
                elif ema50 and current < ema20 < ema50:
                    trend = "DOWN"
                else:
                    trend = "FLAT"
                
                result[tf_name] = {
                    "current": float(current),
                    "ema20": float(ema20),
                    "ema50": float(ema50) if ema50 else None,
                    "rsi": float(rsi),
                    "trend": trend,
                }
            except Exception as e:
                result[tf_name] = {"trend": "UNKNOWN", "error": str(e)[:40]}
        
        # Consensus with 3 timeframes
        real = [r.get("trend") for r in result.values() 
                if isinstance(r, dict) and r.get("trend") in ("UP", "DOWN", "FLAT")]
        
        if len(real) < 2:
            result["consensus"] = "INSUFFICIENT_DATA"
        else:
            up = real.count("UP")
            down = real.count("DOWN")
            if up >= 2 and down == 0:
                result["consensus"] = "BULLISH"
            elif down >= 2 and up == 0:
                result["consensus"] = "BEARISH"
            elif up > down:
                result["consensus"] = "WEAK_BULLISH"
            elif down > up:
                result["consensus"] = "WEAK_BEARISH"
            else:
                result["consensus"] = "MIXED"
        
        self._store("technicals", result)
        return result
    
    def get_global_markets(self):
        if self._fresh("global"):
            return self._cache["global"]
        
        if not YF_AVAILABLE:
            return {"sentiment": "UNKNOWN"}
        
        result = {}
        for name, symbol in self.GLOBAL_SYMBOLS.items():
            try:
                hist = yf.Ticker(symbol).history(period="2d", interval="1d")
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])
                    curr = float(hist["Close"].iloc[-1])
                    result[name] = {"price": curr, "change_pct": ((curr - prev) / prev) * 100}
            except Exception:
                pass
        
        risk_on = sum(1 for n in ["Dow", "SP500", "Nasdaq", "Nikkei", "HangSeng"]
                      if n in result and result[n]["change_pct"] > 0.3)
        risk_off = sum(1 for n in ["Dow", "SP500", "Nasdaq", "Nikkei", "HangSeng"]
                       if n in result and result[n]["change_pct"] < -0.3)
        
        if risk_on > risk_off:
            result["sentiment"] = "RISK_ON"
        elif risk_off > risk_on:
            result["sentiment"] = "RISK_OFF"
        else:
            result["sentiment"] = "NEUTRAL"
        
        self._store("global", result)
        return result
    
    def get_india_vix(self):
        if self._fresh("vix"):
            return self._cache["vix"]
        
        try:
            vix = self.INDEX_TOKENS["INDIA_VIX"]
            data = self.obj.ltpData(vix["exchange"], "INDIA VIX", vix["token"])
            if data and data.get("data"):
                ltp = float(data["data"].get("ltp", 0))
                close = float(data["data"].get("close", 0))
                if ltp > 0 and close > 0:
                    change = ((ltp - close) / close) * 100
                    regime = "HIGH" if ltp > 20 else ("LOW" if ltp < 13 else "NORMAL")
                    result = {"vix": ltp, "change_pct": change, "regime": regime}
                    self._store("vix", result)
                    return result
        except Exception:
            pass
        return {"vix": None, "regime": "UNKNOWN"}
    
    def get_fii_dii(self):
        if self._fresh("fii_dii"):
            return self._cache["fii_dii"]
        
        result = {"fii_net": None, "dii_net": None, "bias": "UNKNOWN"}
        try:
            headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            r = requests.get("https://www.nseindia.com/api/fiidiiTradeReact", headers=headers, timeout=5)
            if r.status_code == 200:
                for row in r.json():
                    cat = row.get("category", "")
                    try:
                        net = float(str(row.get("netValue", "0")).replace(",", ""))
                    except Exception:
                        net = 0
                    if "FII" in cat.upper():
                        result["fii_net"] = net
                    elif "DII" in cat.upper():
                        result["dii_net"] = net
                
                combined = (result["fii_net"] or 0) + (result["dii_net"] or 0)
                if combined > 500:
                    result["bias"] = "BULLISH"
                elif combined < -500:
                    result["bias"] = "BEARISH"
                else:
                    result["bias"] = "NEUTRAL"
        except Exception:
            pass
        
        self._store("fii_dii", result)
        return result
    
    def get_full_context(self):
        return {
            "technicals": self.get_multi_timeframe_technicals(),
            "global": self.get_global_markets(),
            "vix": self.get_india_vix(),
            "fii_dii": self.get_fii_dii(),
        }
