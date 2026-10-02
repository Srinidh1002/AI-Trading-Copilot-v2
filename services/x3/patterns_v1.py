"""Completed-candle shape/pattern observations with no implied trade action."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CandlePatternV1:
    name: str
    direction: str
    confirmation: str
    candle_ids: tuple[str, ...]
    available_at: datetime
    dependency_id: str
    schema_version: str = "X3_CANDLE_PATTERN_V1"


def detect_candlestick_patterns_v1(
    candles, *, context: str = "UNKNOWN"
) -> tuple[CandlePatternV1, ...]:
    """Shapes are NON_DIRECTIONAL until their contextual rule is met."""
    cs = tuple(candles)
    if not cs:
        return ()
    c = cs[-1]
    span = c.high_price - c.low_price
    body = abs(c.close_price - c.open_price)
    upper = c.high_price - max(c.open_price, c.close_price)
    lower = min(c.open_price, c.close_price) - c.low_price
    out = []

    def emit(name, direction="NON_DIRECTIONAL", confirmation="SHAPE", indices=(-1,)):
        picked = tuple(cs[i] for i in indices)
        out.append(
            CandlePatternV1(
                name,
                direction,
                confirmation,
                tuple(x.candle_id for x in picked),
                picked[-1].end_at,
                "candlestick_ohlc",
            )
        )

    if span > 0 and body / span <= 0.10:
        emit("DOJI")
    if (
        span > 0
        and lower >= max(2 * body, 0.5 * span)
        and upper <= 0.15 * span
        and body / span <= 0.35
    ):
        emit("HAMMER_SHAPE")
    if (
        span > 0
        and upper >= max(2 * body, 0.5 * span)
        and lower <= 0.15 * span
        and body / span <= 0.35
    ):
        emit("SHOOTING_STAR_SHAPE")
    if len(cs) >= 2:
        p = cs[-2]
        if (
            p.close_price < p.open_price
            and c.close_price > c.open_price
            and c.open_price <= p.close_price
            and c.close_price >= p.open_price
        ):
            emit("BULLISH_ENGULFING", "BULLISH", "COMPLETED", (-2, -1))
        if (
            p.close_price > p.open_price
            and c.close_price < c.open_price
            and c.open_price >= p.close_price
            and c.close_price <= p.open_price
        ):
            emit("BEARISH_ENGULFING", "BEARISH", "COMPLETED", (-2, -1))
        if c.high_price < p.high_price and c.low_price > p.low_price:
            emit("INSIDE_BAR", indices=(-2, -1))
        if c.high_price > p.high_price and c.low_price < p.low_price:
            emit("OUTSIDE_BAR", indices=(-2, -1))
        pspan, pbody = p.high_price - p.low_price, abs(p.close_price - p.open_price)
        plower = min(p.open_price, p.close_price) - p.low_price
        pupper = p.high_price - max(p.open_price, p.close_price)
        if (
            context == "DOWNTREND"
            and pspan > 0
            and plower >= max(2 * pbody, 0.5 * pspan)
            and pupper <= 0.15 * pspan
            and c.close_price > p.high_price
        ):
            emit("HAMMER_CONFIRMED", "BULLISH", "NEXT_CANDLE", (-2, -1))
        if (
            context == "UPTREND"
            and pspan > 0
            and pupper >= max(2 * pbody, 0.5 * pspan)
            and plower <= 0.15 * pspan
            and c.close_price < p.low_price
        ):
            emit("SHOOTING_STAR_CONFIRMED", "BEARISH", "NEXT_CANDLE", (-2, -1))
    if len(cs) >= 3:
        a, b, d = cs[-3:]
        if (
            a.close_price < a.open_price
            and abs(b.close_price - b.open_price) < 0.4 * abs(a.close_price - a.open_price)
            and d.close_price > d.open_price
            and d.close_price > (a.open_price + a.close_price) / 2
        ):
            emit("MORNING_STAR", "BULLISH", "THREE_CANDLES", (-3, -2, -1))
        if (
            a.close_price > a.open_price
            and abs(b.close_price - b.open_price) < 0.4 * abs(a.close_price - a.open_price)
            and d.close_price < d.open_price
            and d.close_price < (a.open_price + a.close_price) / 2
        ):
            emit("EVENING_STAR", "BEARISH", "THREE_CANDLES", (-3, -2, -1))
    return tuple(sorted(out, key=lambda x: x.name))
