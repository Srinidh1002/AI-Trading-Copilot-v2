"""Causal confirmed swings, structure and breakout/retest observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SwingPointV1:
    kind: str
    candle_index: int
    price: float
    pivot_at: datetime
    confirmed_at: datetime
    source_candle_id: str


@dataclass(frozen=True, slots=True)
class PriceStructureV1:
    state: str
    high_points: tuple[SwingPointV1, ...]
    low_points: tuple[SwingPointV1, ...]
    last_support: float | None
    last_resistance: float | None
    breakout_state: str
    breakout_reference: float | None
    blockers: tuple[str, ...] = ()
    schema_version: str = "X3_PRICE_STRUCTURE_V1"


def analyze_price_structure_v1(
    candles, *, lookback: int = 2, tick_size: float = 0.0
) -> PriceStructureV1:
    """Only pivots with *both* closed left/right windows are visible.

    A pivot at i is timestamped confirmed_at=candles[i+lookback].end_at.
    A retest or failure requires a *later* completed candle than breakout.
    """
    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 1:
        raise ValueError("lookback must be positive")
    if (
        not isinstance(tick_size, (int, float))
        or isinstance(tick_size, bool)
        or not math.isfinite(tick_size)
        or tick_size < 0
    ):
        raise ValueError("tick_size must be non-negative")
    cs = tuple(candles)
    if len(cs) < 2 * lookback + 1:
        return PriceStructureV1(
            "UNKNOWN", (), (), None, None, "NONE", None, ("insufficient_history",)
        )
    highs, lows = [], []
    for i in range(lookback, len(cs) - lookback):
        c = cs[i]
        left_right = cs[i - lookback : i] + cs[i + 1 : i + lookback + 1]
        if all(c.high_price > x.high_price for x in left_right):
            highs.append(
                SwingPointV1(
                    "HIGH", i, c.high_price, c.end_at, cs[i + lookback].end_at, c.candle_id
                )
            )
        if all(c.low_price < x.low_price for x in left_right):
            lows.append(
                SwingPointV1("LOW", i, c.low_price, c.end_at, cs[i + lookback].end_at, c.candle_id)
            )
    high_points, low_points = tuple(highs), tuple(lows)
    if len(highs) >= 2 and len(lows) >= 2:
        hh, hl = highs[-1].price > highs[-2].price, lows[-1].price > lows[-2].price
        lh, ll = highs[-1].price < highs[-2].price, lows[-1].price < lows[-2].price
        state = (
            "BULLISH"
            if hh and hl
            else "BEARISH"
            if lh and ll
            else "CONFLICT"
            if (hh and ll) or (lh and hl)
            else "NON_DIRECTIONAL"
        )
    else:
        state = "UNKNOWN"
    support = lows[-1].price if lows else None
    resistance = highs[-1].price if highs else None
    last = cs[-1]
    # Detect events against a level only after its pivot has been confirmed.
    # Retain an already-observed breakout even if its own candle subsequently
    # becomes a *new* confirmed pivot. The newest pivot must not erase history.
    up_events = []
    down_events = []
    for pivot in highs:
        for i in range(pivot.candle_index + lookback + 1, len(cs)):
            if (
                cs[i - 1].close_price <= pivot.price + tick_size
                and cs[i].close_price > pivot.price + tick_size
            ):
                up_events.append((i, pivot.price))
    for pivot in lows:
        for i in range(pivot.candle_index + lookback + 1, len(cs)):
            if (
                cs[i - 1].close_price >= pivot.price - tick_size
                and cs[i].close_price < pivot.price - tick_size
            ):
                down_events.append((i, pivot.price))
    up_index, up_level = max(
        up_events, default=(None, None), key=lambda x: x[0] if x[0] is not None else -1
    )
    down_index, down_level = max(
        down_events, default=(None, None), key=lambda x: x[0] if x[0] is not None else -1
    )
    breakout_state, ref = "NONE", None
    if up_index is not None and (down_index is None or up_index >= down_index):
        ref = up_level
        if up_index == len(cs) - 1:
            breakout_state = "UP_BREAK"
        elif last.close_price < up_level - tick_size:
            breakout_state = "UP_FAILURE"
        elif any(
            x.low_price <= up_level + tick_size and x.close_price >= up_level
            for x in cs[up_index + 1 :]
        ):
            breakout_state = "UP_RETEST"
        else:
            breakout_state = "UP_BREAK_PENDING_RETEST"
    elif down_index is not None:
        ref = down_level
        if down_index == len(cs) - 1:
            breakout_state = "DOWN_BREAK"
        elif last.close_price > down_level + tick_size:
            breakout_state = "DOWN_FAILURE"
        elif any(
            x.high_price >= down_level - tick_size and x.close_price <= down_level
            for x in cs[down_index + 1 :]
        ):
            breakout_state = "DOWN_RETEST"
        else:
            breakout_state = "DOWN_BREAK_PENDING_RETEST"
    return PriceStructureV1(
        state, high_points, low_points, support, resistance, breakout_state, ref
    )
