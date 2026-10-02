"""Prior-session OHLC levels, classic floor pivots and opening-gap evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class SessionLevelsV1:
    previous_session_date: str | None
    previous_high: float | None
    previous_low: float | None
    previous_close: float | None
    pivot_point: float | None
    resistance_1: float | None
    support_1: float | None
    opening_gap_percent: float | None
    as_of: datetime | None
    blockers: tuple[str, ...] = ()
    schema_version: str = "X3_SESSION_LEVELS_V1"


def calculate_session_levels_v1(candles) -> SessionLevelsV1:
    """Use only completed, validated candles (caller enforces source quality).

    The latest India trading date is the current observed session. The most
    recent *earlier observed* trading date is used as the prior session; the
    upstream calendar must establish that no required session is missing.
    """
    cs = tuple(candles)
    if not cs:
        return SessionLevelsV1(
            None, None, None, None, None, None, None, None, None, ("empty_history",)
        )
    by_date = {}
    for c in cs:
        session_date = c.start_at.astimezone(IST).date()
        by_date.setdefault(session_date, []).append(c)
    dates = sorted(by_date)
    if len(dates) < 2:
        return SessionLevelsV1(
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            cs[-1].end_at,
            ("previous_session_unavailable",),
        )
    previous = by_date[dates[-2]]
    current = by_date[dates[-1]]
    high = max(c.high_price for c in previous)
    low = min(c.low_price for c in previous)
    close = previous[-1].close_price
    pivot = (high + low + close) / 3.0
    gap = 100.0 * (current[0].open_price / close - 1.0)
    return SessionLevelsV1(
        dates[-2].isoformat(),
        high,
        low,
        close,
        pivot,
        2 * pivot - low,
        2 * pivot - high,
        gap,
        cs[-1].end_at,
    )
