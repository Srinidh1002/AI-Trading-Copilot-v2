"""
Indicator Engine

Single source of truth for all technical indicators.
Every analysis engine must use this file.

Author: Saaura AI Trading Copilot
"""

from services.indicators.rsi_engine import calculate_rsi
from services.indicators.macd_engine import calculate_macd
from services.indicators.ema_engine import calculate_ema
from services.indicators.adx_engine import calculate_adx
from services.indicators.atr_engine import calculate_atr
from services.indicators.vwap_engine import calculate_vwap


def calculate_indicators(df):
    """
    Calculate all technical indicators.

    Parameters
    ----------
    df : pandas.DataFrame

    Returns
    -------
    dict
    """

    ema = calculate_ema(df)
    rsi = calculate_rsi(df)
    macd = calculate_macd(df)
    adx = calculate_adx(df)
    atr = calculate_atr(df)
    vwap = calculate_vwap(df)

    return {
        "ema": ema,
        "rsi": rsi,
        "macd": macd,
        "adx": adx,
        "atr": atr,
        "vwap": vwap,
    }