"""MCX multi-timeframe technicals on the active futures contract.
Mirrors the NIFTY/SENSEX mtf_enhanced.py concept, adapted for MCX.
READ-ONLY. No trades. No state writes.
"""
import os
import sys
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    import pandas as pd
    import ta
    TA_OK = True
except ImportError:
    TA_OK = False


# Interval: (Angel interval string, lookback days)
TIMEFRAMES = {
    "5m":  ("FIVE_MINUTE", 3),
    "15m": ("FIFTEEN_MINUTE", 5),
    "1h":  ("ONE_HOUR", 10),
}


def _fetch_candles(obj, token, exchange, interval, days):
    now = datetime.now()
    frm = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
    to = now.strftime("%Y-%m-%d %H:%M")
    try:
        resp = obj.getCandleData({
            "exchange": exchange,
            "symboltoken": str(token),
            "interval": interval,
            "fromdate": frm,
            "todate": to,
        })
    except Exception as e:
        return None, str(e)[:80]
    if not resp or not resp.get("data"):
        return None, "empty"
    try:
        df = pd.DataFrame(resp["data"],
                          columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna().reset_index(drop=True)
        return df, None
    except Exception as e:
        return None, f"parse: {str(e)[:60]}"


def _analyze(df):
    if df is None or len(df) < 26:
        return {"status": "INSUFFICIENT_DATA", "rows": 0 if df is None else len(df)}
    close = df["close"]
    high = df["high"]
    low = df["low"]

    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    try:
        adx = ta.trend.ADXIndicator(high, low, close, window=14).adx().iloc[-1]
    except Exception:
        adx = None
    try:
        macd = ta.trend.MACD(close).macd_diff().iloc[-1]
    except Exception:
        macd = None

    trend = "FLAT"
    if ema20 > ema50 and close.iloc[-1] > ema20:
        trend = "UP"
    elif ema20 < ema50 and close.iloc[-1] < ema20:
        trend = "DOWN"

    return {
        "status": "OK",
        "rows": len(df),
        "last_close": float(close.iloc[-1]),
        "ema20": float(ema20),
        "ema50": float(ema50),
        "rsi": round(float(rsi), 1) if rsi == rsi else None,
        "adx": round(float(adx), 1) if adx == adx and adx is not None else None,
        "macd_diff": round(float(macd), 4) if macd == macd and macd is not None else None,
        "trend": trend,
    }


def compute_mtf(obj, token, exchange="MCX"):
    if not TA_OK:
        return {"status": "TA_UNAVAILABLE"}
    out = {"status": "OK", "exchange": exchange, "token": str(token),
           "fetched_at": datetime.now().isoformat(timespec="seconds"), "timeframes": {}}

    for label, (interval, days) in TIMEFRAMES.items():
        df, err = _fetch_candles(obj, token, exchange, interval, days)
        if df is None:
            out["timeframes"][label] = {"status": "FETCH_FAILED", "err": err}
            continue
        out["timeframes"][label] = _analyze(df)

    # Aggregate trend
    trends = [v.get("trend") for v in out["timeframes"].values()
              if v.get("status") == "OK"]
    up = trends.count("UP")
    down = trends.count("DOWN")
    if up >= 2 and down == 0:
        out["aggregate_trend"] = "BULLISH"
    elif down >= 2 and up == 0:
        out["aggregate_trend"] = "BEARISH"
    elif up > down:
        out["aggregate_trend"] = "WEAK_BULLISH"
    elif down > up:
        out["aggregate_trend"] = "WEAK_BEARISH"
    else:
        out["aggregate_trend"] = "MIXED"

    return out


def print_mtf(mtf):
    print(f"\nMCX MTF  token={mtf.get('token')}  ({mtf.get('fetched_at')})")
    if mtf.get("status") != "OK":
        print(f"  status={mtf['status']}")
        return
    for label, v in mtf["timeframes"].items():
        if v.get("status") == "OK":
            print(f"  {label:<4} rows={v['rows']:<4} trend={v['trend']:<6} "
                  f"RSI={v['rsi']}  ADX={v['adx']}  ema20={v['ema20']:.2f} ema50={v['ema50']:.2f}")
        else:
            print(f"  {label:<4} {v.get('status')}  {v.get('err','')}")
    print(f"  AGGREGATE: {mtf.get('aggregate_trend')}")
