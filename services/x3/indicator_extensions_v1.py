"""Pure missing X3 indicators; no broker, clock, or provider dependencies.

Conventions: stochastic returns smoothed (K, D); CCI uses population mean
absolute deviation; Williams %R is -100..0; Aroon requires period+1
candles and resolves tied extrema in favor of the latest observation;
MFI uses the previous typical price and the most recent ``period`` flows;
ROC is in percent, momentum is in price units, volume change is percent.
All functions return None for invalid or unavailable inputs and never fill gaps.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def _series(values: Iterable[float]) -> tuple[float, ...] | None:
    try:
        seq = tuple(values)
    except (TypeError, ValueError):
        return None
    if not seq or any(
        isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in seq
    ):
        return None
    return tuple(float(v) for v in seq)


def _period(n: int) -> bool:
    return isinstance(n, int) and not isinstance(n, bool) and n > 0


def _ohlc(highs, lows, closes):
    h, low, c = _series(highs), _series(lows), _series(closes)
    if h is None or low is None or c is None or not (len(h) == len(low) == len(c)):
        return None
    if any(lo <= 0 or hi < max(lo, cl) or cl <= 0 for hi, lo, cl in zip(h, low, c)):
        return None
    return h, low, c


def calculate_stochastic(highs, lows, closes, period: int = 14, smooth: int = 3):
    """Fast stochastic K and simple moving-average D (0..100)."""
    valid = _ohlc(highs, lows, closes)
    if valid is None or not _period(period) or not _period(smooth):
        return None
    h, low, c = valid
    if len(c) < period + smooth - 1:
        return None
    ks = []
    for end in range(len(c) - smooth + 1, len(c) + 1):
        hi, lo = max(h[end - period : end]), min(low[end - period : end])
        ks.append(50.0 if hi == lo else 100.0 * (c[end - 1] - lo) / (hi - lo))
    return ks[-1], sum(ks) / len(ks)


def calculate_cci(highs, lows, closes, period: int = 20):
    valid = _ohlc(highs, lows, closes)
    if valid is None or not _period(period):
        return None
    h, low, c = valid
    if len(c) < period:
        return None
    tp = tuple((a + b + d) / 3.0 for a, b, d in zip(h, low, c))[-period:]
    mean = sum(tp) / period
    mad = sum(abs(v - mean) for v in tp) / period
    return 0.0 if mad == 0.0 else (tp[-1] - mean) / (0.015 * mad)


def calculate_williams_r(highs, lows, closes, period: int = 14):
    valid = _ohlc(highs, lows, closes)
    if valid is None or not _period(period):
        return None
    h, low, c = valid
    if len(c) < period:
        return None
    hi, lo = max(h[-period:]), min(low[-period:])
    return -50.0 if hi == lo else -100.0 * (hi - c[-1]) / (hi - lo)


def calculate_aroon(highs, lows, period: int = 14):
    """(aroon_up, aroon_down); last period+1 candles, latest tie wins."""
    h, low = _series(highs), _series(lows)
    if h is None or low is None or len(h) != len(low) or not _period(period):
        return None
    if len(h) < period + 1 or any(x <= 0 or y <= 0 or x < y for x, y in zip(h, low)):
        return None
    hh, ll = h[-period - 1 :], low[-period - 1 :]
    last_high = max(i for i, v in enumerate(hh) if v == max(hh))
    last_low = max(i for i, v in enumerate(ll) if v == min(ll))
    return 100.0 * last_high / period, 100.0 * last_low / period


def calculate_mfi(highs, lows, closes, volumes, period: int = 14):
    valid = _ohlc(highs, lows, closes)
    v = _series(volumes)
    if valid is None or v is None or not _period(period):
        return None
    h, low, c = valid
    if len(c) != len(v) or len(c) < period + 1 or any(q < 0 for q in v):
        return None
    if sum(v[-period:]) == 0:
        return None
    tp = tuple((a + b + d) / 3.0 for a, b, d in zip(h, low, c))
    pos = neg = 0.0
    for i in range(len(tp) - period, len(tp)):
        flow = tp[i] * v[i]
        if tp[i] > tp[i - 1]:
            pos += flow
        elif tp[i] < tp[i - 1]:
            neg += flow
    if pos == 0.0 and neg == 0.0:
        return 50.0
    if neg == 0.0:
        return 100.0
    if pos == 0.0:
        return 0.0
    return 100.0 * pos / (pos + neg)


def calculate_roc(closes, period: int = 12):
    c = _series(closes)
    if c is None or not _period(period) or len(c) < period + 1:
        return None
    if c[-period - 1] <= 0:
        return None
    return 100.0 * (c[-1] / c[-period - 1] - 1.0)


def calculate_momentum(closes, period: int = 10):
    c = _series(closes)
    if c is None or not _period(period) or len(c) < period + 1:
        return None
    return c[-1] - c[-period - 1]


def calculate_volume_change(volumes):
    v = _series(volumes)
    if v is None or len(v) < 2 or v[-2] <= 0 or v[-1] < 0:
        return None
    return 100.0 * (v[-1] / v[-2] - 1.0)


__all__ = [
    "calculate_stochastic",
    "calculate_cci",
    "calculate_williams_r",
    "calculate_aroon",
    "calculate_mfi",
    "calculate_roc",
    "calculate_momentum",
    "calculate_volume_change",
]
