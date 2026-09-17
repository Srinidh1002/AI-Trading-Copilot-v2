"""Pure technical-indicator primitives.

EMA is seeded with the first simple moving average. RSI uses Wilder's initial
average gain/loss and subsequent Wilder smoothing. MACD aligns its signal EMA
to the complete fast/slow MACD sequence. ATR uses a simple-average seed then
Wilder smoothing; ADX follows the same Wilder seed/smoothing convention.
Bollinger bands use population standard deviation.  Every function returns
``None`` when complete history is unavailable; no values are interpolated.
"""
from __future__ import annotations

import math


def _series(values: object) -> tuple[float, ...] | None:
    try: values = tuple(values)  # type: ignore[arg-type]
    except TypeError: return None
    if not values or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values): return None
    return tuple(float(value) for value in values)


def _period(period: object) -> int | None:
    return period if isinstance(period, int) and not isinstance(period, bool) and period > 0 else None


def _ema_series(values: tuple[float, ...], period: int) -> tuple[float, ...] | None:
    if len(values) < period: return None
    current = sum(values[:period]) / period
    out = [current]; multiplier = 2.0 / (period + 1)
    for value in values[period:]:
        current = (value - current) * multiplier + current
        out.append(current)
    return tuple(out)


def calculate_sma(values: object, period: object) -> float | None:
    values, period = _series(values), _period(period)
    return None if values is None or period is None or len(values) < period else sum(values[-period:]) / period


def calculate_ema(values: object, period: object) -> float | None:
    values, period = _series(values), _period(period)
    result = None if values is None or period is None else _ema_series(values, period)
    return None if result is None else result[-1]


def calculate_rsi(values: object, period: object) -> float | None:
    values, period = _series(values), _period(period)
    if values is None or period is None or len(values) < period + 1: return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]; losses = [max(-change, 0.0) for change in changes]
    gain, loss = sum(gains[:period]) / period, sum(losses[:period]) / period
    for index in range(period, len(gains)):
        gain = (gain * (period - 1) + gains[index]) / period
        loss = (loss * (period - 1) + losses[index]) / period
    if loss == 0.0: return 100.0 if gain > 0.0 else 50.0
    return 100.0 - (100.0 / (1.0 + gain / loss))


def calculate_macd(values: object, fast_period: object, slow_period: object, signal_period: object) -> tuple[float, float, float] | None:
    values, fast, slow, signal = _series(values), _period(fast_period), _period(slow_period), _period(signal_period)
    if values is None or fast is None or slow is None or signal is None or fast >= slow: return None
    fast_values, slow_values = _ema_series(values, fast), _ema_series(values, slow)
    if fast_values is None or slow_values is None: return None
    # Both sequences end at the same candle; drop leading fast-only values.
    macd = tuple(fast_values[len(fast_values) - len(slow_values) + index] - slow_values[index] for index in range(len(slow_values)))
    signal_values = _ema_series(macd, signal)
    if signal_values is None: return None
    line, signal_line = macd[-1], signal_values[-1]
    return line, signal_line, line - signal_line


def calculate_true_range(highs: object, lows: object, closes: object) -> tuple[float, ...] | None:
    highs, lows, closes = _series(highs), _series(lows), _series(closes)
    if highs is None or lows is None or closes is None or len(highs) != len(lows) or len(lows) != len(closes) or any(high < low for high, low in zip(highs, lows)): return None
    return tuple(high - low if index == 0 else max(high - low, abs(high - closes[index - 1]), abs(low - closes[index - 1])) for index, (high, low) in enumerate(zip(highs, lows)))


def calculate_atr(highs: object, lows: object, closes: object, period: object) -> float | None:
    ranges, period = calculate_true_range(highs, lows, closes), _period(period)
    if ranges is None or period is None or len(ranges) < period: return None
    atr = sum(ranges[:period]) / period
    for value in ranges[period:]: atr = (atr * (period - 1) + value) / period
    return atr


def calculate_adx(highs: object, lows: object, closes: object, period: object) -> float | None:
    highs, lows, closes, period = _series(highs), _series(lows), _series(closes), _period(period)
    if highs is None or lows is None or closes is None or period is None or len(highs) != len(lows) or len(lows) != len(closes) or len(highs) < period * 2 + 1 or any(high < low for high, low in zip(highs, lows)): return None
    tr = calculate_true_range(highs, lows, closes)
    assert tr is not None
    plus = [0.0]; minus = [0.0]
    for index in range(1, len(highs)):
        up, down = highs[index] - highs[index - 1], lows[index - 1] - lows[index]
        plus.append(up if up > down and up > 0 else 0.0); minus.append(down if down > up and down > 0 else 0.0)
    atr, p_dm, m_dm = sum(tr[1:period + 1]) / period, sum(plus[1:period + 1]) / period, sum(minus[1:period + 1]) / period
    dx: list[float] = []
    for index in range(period + 1, len(highs)):
        atr = (atr * (period - 1) + tr[index]) / period; p_dm = (p_dm * (period - 1) + plus[index]) / period; m_dm = (m_dm * (period - 1) + minus[index]) / period
        if atr == 0:
            dx.append(0.0)
        else:
            plus_di, minus_di = 100.0 * p_dm / atr, 100.0 * m_dm / atr
            denominator = plus_di + minus_di
            dx.append(0.0 if denominator == 0 else 100.0 * abs(plus_di - minus_di) / denominator)
    if len(dx) < period: return None
    adx = sum(dx[:period]) / period
    for value in dx[period:]: adx = (adx * (period - 1) + value) / period
    return adx


def calculate_bollinger_bands(values: object, period: object, stddev: object) -> tuple[float, float, float] | None:
    values, period = _series(values), _period(period)
    if values is None or period is None or isinstance(stddev, bool) or not isinstance(stddev, (int, float)) or not math.isfinite(stddev) or stddev <= 0 or len(values) < period: return None
    sample = values[-period:]; middle = sum(sample) / period
    deviation = math.sqrt(sum((value - middle) ** 2 for value in sample) / period)
    return middle - float(stddev) * deviation, middle, middle + float(stddev) * deviation


def calculate_vwap(highs: object, lows: object, closes: object, volumes: object) -> float | None:
    highs, lows, closes, volumes = _series(highs), _series(lows), _series(closes), _series(volumes)
    if highs is None or lows is None or closes is None or volumes is None or len(highs) != len(lows) or len(lows) != len(closes) or len(closes) != len(volumes) or any(value < 0 for value in volumes) or any(high < low for high, low in zip(highs, lows)): return None
    total = sum(volumes)
    return None if total <= 0 else sum(((high + low + close) / 3.0) * volume for high, low, close, volume in zip(highs, lows, closes, volumes)) / total


def calculate_volume_average(volumes: object, period: object) -> float | None:
    volumes, period = _series(volumes), _period(period)
    return None if volumes is None or period is None or len(volumes) < period or any(value < 0 for value in volumes) else sum(volumes[-period:]) / period
