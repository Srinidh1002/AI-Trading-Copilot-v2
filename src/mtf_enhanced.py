"""MTF Enhanced - Full indicator suite per timeframe.
Adds MACD, ADX/DI, Bollinger, ATR beyond existing EMA/RSI.
"""
import time
import pandas as pd

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False


def compute_indicators(df):
    """Compute full indicator set from OHLCV dataframe.
    Returns dict with all values, or {'status': 'INSUFFICIENT_DATA'} if too short.
    """
    if not TA_AVAILABLE:
        return {"status": "TA_LIB_UNAVAILABLE"}
    
    if df is None or len(df) < 26:
        return {"status": "INSUFFICIENT_DATA", "rows": len(df) if df is not None else 0}
    
    try:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        
        # Trend
        ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
        ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator() if len(df) >= 50 else None
        
        ema20_val = float(ema20.iloc[-1])
        ema20_slope = float(ema20.iloc[-1] - ema20.iloc[-3]) if len(ema20) >= 3 else 0
        ema50_val = float(ema50.iloc[-1]) if ema50 is not None else None
        ema50_slope = float(ema50.iloc[-1] - ema50.iloc[-3]) if ema50 is not None and len(ema50) >= 3 else 0
        
        # Momentum
        rsi = float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1])
        
        macd_obj = ta.trend.MACD(close)
        macd = float(macd_obj.macd().iloc[-1])
        macd_sig = float(macd_obj.macd_signal().iloc[-1])
        macd_hist = float(macd_obj.macd_diff().iloc[-1])
        
        # Strength
        adx_val = None
        di_plus = None
        di_minus = None
        if len(df) >= 14:
            adx_obj = ta.trend.ADXIndicator(high, low, close, window=14)
            adx_val = float(adx_obj.adx().iloc[-1])
            di_plus = float(adx_obj.adx_pos().iloc[-1])
            di_minus = float(adx_obj.adx_neg().iloc[-1])
        
        # Volatility
        atr = float(ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1])
        atr_pct = (atr / float(close.iloc[-1])) * 100
        
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = float(bb.bollinger_hband().iloc[-1])
        bb_mid = float(bb.bollinger_mavg().iloc[-1])
        bb_lower = float(bb.bollinger_lband().iloc[-1])
        bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0
        
        current = float(close.iloc[-1])
        
        # Determine trend
        if ema50_val and current > ema20_val > ema50_val:
            trend = "UP"
        elif ema50_val and current < ema20_val < ema50_val:
            trend = "DOWN"
        else:
            trend = "FLAT"
        
        # Momentum direction
        if macd_hist > 0 and rsi > 50:
            momentum = "UP"
        elif macd_hist < 0 and rsi < 50:
            momentum = "DOWN"
        else:
            momentum = "MIXED"
        
        # Strength classification
        strength = "WEAK"
        if adx_val is not None:
            if adx_val > 30:
                strength = "STRONG"
            elif adx_val > 20:
                strength = "MODERATE"
        
        return {
            "status": "OK",
            "rows": len(df),
            "current": current,
            "ema20": ema20_val,
            "ema20_slope": ema20_slope,
            "ema50": ema50_val,
            "ema50_slope": ema50_slope,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_sig,
            "macd_hist": macd_hist,
            "adx": adx_val,
            "di_plus": di_plus,
            "di_minus": di_minus,
            "atr": atr,
            "atr_pct": atr_pct,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "bb_width": bb_width,
            "trend": trend,
            "momentum": momentum,
            "strength": strength,
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)[:60]}


def timeframe_decision(ind):
    """Convert indicator dict to (decision, confidence)."""
    if not ind or ind.get("status") != "OK":
        return ("UNKNOWN", 0.0)
    
    votes = []
    
    # Trend
    if ind["trend"] == "UP":
        votes.append(("UP", 0.35))
    elif ind["trend"] == "DOWN":
        votes.append(("DOWN", 0.35))
    
    # Momentum
    if ind["momentum"] == "UP":
        votes.append(("UP", 0.25))
    elif ind["momentum"] == "DOWN":
        votes.append(("DOWN", 0.25))
    
    # RSI extremes
    if ind["rsi"] < 30:
        votes.append(("DOWN", 0.15))
    elif ind["rsi"] > 70:
        votes.append(("UP", 0.15))
    
    # ADX strength confirms direction
    if ind.get("adx") and ind["adx"] > 25:
        if ind.get("di_plus") and ind.get("di_minus"):
            if ind["di_plus"] > ind["di_minus"]:
                votes.append(("UP", 0.15))
            else:
                votes.append(("DOWN", 0.15))
    
    # Tally
    up_score = sum(w for d, w in votes if d == "UP")
    down_score = sum(w for d, w in votes if d == "DOWN")
    total = up_score + down_score
    
    if total < 0.3:
        return ("FLAT", 0.0)
    
    if up_score > down_score * 1.5:
        return ("UP", min(1.0, up_score / total))
    elif down_score > up_score * 1.5:
        return ("DOWN", min(1.0, down_score / total))
    else:
        return ("MIXED", 0.3)


if __name__ == "__main__":
    import numpy as np
    # Generate synthetic data
    np.random.seed(42)
    n = 100
    prices = 23000 + np.cumsum(np.random.randn(n) * 5)
    df = pd.DataFrame({
        "open": prices - 2,
        "high": prices + 5,
        "low": prices - 5,
        "close": prices,
        "volume": np.random.randint(1000, 5000, n),
    })
    
    ind = compute_indicators(df)
    print(f"Status: {ind.get('status')}")
    if ind.get("status") == "OK":
        print(f"Trend: {ind['trend']} | Momentum: {ind['momentum']} | Strength: {ind['strength']}")
        adx_str = f"{ind['adx']:.1f}" if ind['adx'] else "N/A"
        ema50_str = f"{ind['ema50']:.2f}" if ind['ema50'] else "N/A"
        print(f"RSI: {ind['rsi']:.1f} | ADX: {adx_str}")
        print(f"EMA20: {ind['ema20']:.2f} | EMA50: {ema50_str}")
        dec, conf = timeframe_decision(ind)
        print(f"Decision: {dec} (confidence {conf:.2f})")
