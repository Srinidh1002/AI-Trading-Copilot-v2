"""Strictly confirmed causal double-top and double-bottom observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from services.x3.structure_v1 import PriceStructureV1


@dataclass(frozen=True, slots=True)
class ChartFormationV1:
    name: str
    direction: str
    first_pivot_index: int
    second_pivot_index: int
    neckline: float
    confirmed_at: datetime
    source_candle_ids: tuple[str, ...]
    schema_version: str = "X3_CHART_FORMATION_V1"


def detect_chart_formations_v1(
    candles, structure: PriceStructureV1, *, tolerance_ratio: float = 0.005
):
    """Confirmation is the *current* candle breaking the intervening neckline.

    Both pivots must already be confirmed, and the two pivot highs/lows must
    be within a fixed, documented relative tolerance. An unbroken candidate
    is deliberately not labelled a confirmed chart formation.
    """
    if (
        not isinstance(tolerance_ratio, (int, float))
        or isinstance(tolerance_ratio, bool)
        or not math.isfinite(tolerance_ratio)
        or not 0 <= tolerance_ratio <= 0.10
    ):
        raise ValueError("invalid tolerance_ratio")
    cs = tuple(candles)
    if not cs or not isinstance(structure, PriceStructureV1):
        return ()
    last = cs[-1]
    if len(cs) < 5:
        return ()
    result = []
    if len(structure.high_points) >= 2:
        first, second = structure.high_points[-2:]
        if (
            second.candle_index < len(cs) - 1
            and second.confirmed_at < last.end_at
            and abs(first.price - second.price) / max(first.price, second.price) <= tolerance_ratio
        ):
            valley = [
                x
                for x in structure.low_points
                if first.candle_index < x.candle_index < second.candle_index
            ]
            if valley:
                neckline = min(x.price for x in valley)
                if cs[-2].close_price >= neckline and last.close_price < neckline:
                    result.append(
                        ChartFormationV1(
                            "DOUBLE_TOP_CONFIRMED",
                            "BEARISH",
                            first.candle_index,
                            second.candle_index,
                            neckline,
                            last.end_at,
                            (first.source_candle_id, second.source_candle_id, last.candle_id),
                        )
                    )
    if len(structure.low_points) >= 2:
        first, second = structure.low_points[-2:]
        if (
            second.candle_index < len(cs) - 1
            and second.confirmed_at < last.end_at
            and abs(first.price - second.price) / max(first.price, second.price) <= tolerance_ratio
        ):
            crest = [
                x
                for x in structure.high_points
                if first.candle_index < x.candle_index < second.candle_index
            ]
            if crest:
                neckline = max(x.price for x in crest)
                if cs[-2].close_price <= neckline and last.close_price > neckline:
                    result.append(
                        ChartFormationV1(
                            "DOUBLE_BOTTOM_CONFIRMED",
                            "BULLISH",
                            first.candle_index,
                            second.candle_index,
                            neckline,
                            last.end_at,
                            (first.source_candle_id, second.source_candle_id, last.candle_id),
                        )
                    )
    return tuple(result)
