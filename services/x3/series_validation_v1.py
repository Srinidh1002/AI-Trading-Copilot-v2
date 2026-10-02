"""Strict as-of candle admission; existing upstream quality must be supplied."""

from __future__ import annotations

import math
from datetime import datetime

_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 1440}


def admitted_candles_v1(series, *, as_of: datetime, source_quality: str):
    """Return (complete candles, blockers, warnings), never fetch missing candles.

    READY is an assertion from the upstream data-quality authority, not
    something this helper can certify. Same-session gaps fail closed. Across
    sessions require the caller's upstream READY verdict and retain a warning.
    """
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if not isinstance(source_quality, str):
        raise ValueError("source_quality required")
    if source_quality not in {"READY", "READY_WITH_WARNINGS"}:
        return (), ("source_quality_not_ready",), ()
    if (
        series is None
        or not getattr(series, "series_id", None)
        or getattr(series, "timeframe", None) not in _MINUTES
    ):
        return (), ("invalid_series",), ()
    if getattr(series, "blockers", ()):
        return (), tuple(series.blockers), ()
    try:
        candles = tuple(series.candles)
    except (TypeError, AttributeError):
        return (), ("missing_candles",), ()
    if not candles:
        return (), ("empty_series",), ()
    warnings = list(getattr(series, "warnings", ()))
    if source_quality == "READY_WITH_WARNINGS":
        warnings.append("upstream_ready_with_warnings")
    completed = []
    providers = set()
    prev = None
    for i, c in enumerate(candles):
        start, end = getattr(c, "start_at", None), getattr(c, "end_at", None)
        if (
            not isinstance(start, datetime)
            or not isinstance(end, datetime)
            or start.tzinfo is None
            or end.tzinfo is None
            or start >= end
            or end > as_of
        ):
            return (), ("invalid_or_future_candle",), ()
        if prev is not None:
            if start <= prev.start_at or start < prev.end_at:
                return (), ("duplicate_or_overlapping_candle",), ()
            diff = (start - prev.start_at).total_seconds()
            interval = _MINUTES[series.timeframe] * 60
            if diff > interval + 1 and start.date() == prev.start_at.date():
                return (), ("unverified_same_session_gap",), ()
            if diff > interval + 1 and start.date() != prev.start_at.date():
                warnings.append("cross_session_gap_checked_by_upstream")
        if (
            getattr(c, "timeframe", series.timeframe) != series.timeframe
            or getattr(c, "underlying_symbol", getattr(series, "underlying_symbol", None))
            != getattr(series, "underlying_symbol", None)
            or getattr(c, "exchange", getattr(series, "exchange", None))
            != getattr(series, "exchange", None)
        ):
            return (), ("candle_series_identity_mismatch",), ()
        provenance = getattr(c, "provenance", None)
        provider = getattr(provenance, "provider", None)
        if not isinstance(provider, str) or not provider.strip():
            return (), ("source_provenance_missing",), ()
        providers.add(provider.upper().strip())
        if len(providers) > 1:
            return (), ("mixed_source_providers",), ()
        vals = tuple(
            getattr(c, x, None)
            for x in ("open_price", "high_price", "low_price", "close_price", "volume")
        )
        if (
            any(
                not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                for v in vals
            )
            or min(vals[:4]) <= 0
            or vals[4] < 0
            or vals[1] < max(vals[0], vals[2], vals[3])
            or vals[2] > min(vals[0], vals[1], vals[3])
        ):
            return (), ("invalid_ohlcv",), ()
        if not isinstance(getattr(c, "is_complete", None), bool):
            return (), ("invalid_completion_state",), ()
        if not c.is_complete:
            if i != len(candles) - 1:
                return (), ("incomplete_middle_candle",), ()
            warnings.append("latest_incomplete_candle_excluded")
        else:
            completed.append(c)
        prev = c
    if not completed:
        return (), ("no_completed_candles",), tuple(sorted(set(warnings)))
    return tuple(completed), (), tuple(sorted(set(warnings)))
