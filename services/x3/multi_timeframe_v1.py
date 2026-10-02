"""Unweighted, causal multi-timeframe research assembly (no strategy)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from services.x3.contracts_v1 import X3MultiTimeframeResultV1
from services.x3.pipeline_v1 import build_x3_timeframe_v1


def build_x3_multi_timeframe_v1(
    *,
    market: str,
    instrument_id: str,
    series_by_timeframe: Mapping,
    quality_by_timeframe: Mapping,
    as_of: datetime,
    required_timeframes: tuple[str, ...] = ("5m", "15m", "1h", "1d"),
    standard=None,
) -> X3MultiTimeframeResultV1:
    if (
        not isinstance(series_by_timeframe, Mapping)
        or not isinstance(quality_by_timeframe, Mapping)
        or not isinstance(required_timeframes, tuple)
        or not required_timeframes
        or len(set(required_timeframes)) != len(required_timeframes)
    ):
        raise ValueError("invalid timeframe inputs")
    results = []
    for tf in required_timeframes:
        series = series_by_timeframe.get(tf)
        if series is None:
            continue
        if getattr(series, "timeframe", None) != tf:
            raise ValueError("timeframe identity mismatch")
        results.append(
            build_x3_timeframe_v1(
                market=market,
                instrument_id=instrument_id,
                series=series,
                as_of=as_of,
                source_quality=quality_by_timeframe.get(tf, "UNVERIFIED"),
                standard=standard,
            )
        )
    observed = tuple(x.timeframe for x in results)
    missing = tuple(x for x in required_timeframes if x not in observed)
    states = {
        f.state
        for r in results
        if not r.blockers
        for f in r.families
        if f.family in {"TREND", "MOMENTUM", "STRUCTURE"} and f.state in {"BULLISH", "BEARISH"}
    }
    if len(states) > 1:
        alignment = "CONFLICT"
    elif missing or any(r.blockers for r in results):
        alignment = "UNKNOWN"
    elif len(states) == 1:
        alignment = states.pop()
    else:
        alignment = "NON_DIRECTIONAL"
    return X3MultiTimeframeResultV1(
        market,
        instrument_id,
        as_of,
        required_timeframes,
        tuple(results),
        missing,
        alignment,
    )
