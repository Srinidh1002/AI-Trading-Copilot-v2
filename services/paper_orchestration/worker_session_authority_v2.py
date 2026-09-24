"""Unified session authority for the five-market PAPER supervisor.

Dispatches to the exchange-authoritative calendar for each market type:
  * COMMODITY (MCX) -> src/mcx/mcx_calendar.get_session
  * INDEX NIFTY     -> services/market_session_guard + services/nse_holiday_calendar
  * INDEX SENSEX    -> services/market_session_guard + services/bse_holiday_calendar

Fails closed with calendar_authoritative=False for unknown market types,
unknown calendar years, or any exception from the underlying authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time as dtime

_INDEX_CLOSE = dtime(15, 30)
_INDEX_CALENDAR_YEAR = 2026


@dataclass(frozen=True)
class SessionAuthority:
    session_open: bool
    new_entries_allowed: bool
    position_management_allowed: bool
    close_time: dtime | None
    calendar_authoritative: bool
    status: str
    note: str


def _mcx_authority(now):
    try:
        from mcx.mcx_calendar import get_session
    except Exception as exc:
        return SessionAuthority(
            False,
            False,
            False,
            None,
            False,
            "MCX_CALENDAR_IMPORT_FAILED",
            type(exc).__name__,
        )
    try:
        r = get_session(now)
    except Exception as exc:
        return SessionAuthority(
            False,
            False,
            False,
            None,
            False,
            "MCX_CALENDAR_RAISED",
            type(exc).__name__,
        )
    return SessionAuthority(
        session_open=bool(r.get("session_open")),
        new_entries_allowed=bool(r.get("new_entries_allowed")),
        position_management_allowed=bool(r.get("position_management_allowed")),
        close_time=r.get("close_time"),
        calendar_authoritative=bool(r.get("calendar_authoritative", False)),
        status=str(r.get("status", "UNKNOWN")),
        note=str(r.get("note", "")),
    )


def _index_authority(now, spec_name):
    if now.year != _INDEX_CALENDAR_YEAR:
        return SessionAuthority(
            False,
            False,
            False,
            _INDEX_CLOSE,
            False,
            "CALENDAR_YEAR_UNKNOWN",
            f"NSE/BSE holiday data not loaded for {now.year}",
        )
    try:
        from services.market_session_guard import evaluate_market_session

        if spec_name == "NIFTY":
            from services.nse_holiday_calendar import get_nse_holiday_calendar

            cal = get_nse_holiday_calendar()
        elif spec_name == "SENSEX":
            from services.bse_holiday_calendar import get_bse_holiday_calendar

            cal = get_bse_holiday_calendar()
        else:
            return SessionAuthority(
                False,
                False,
                False,
                _INDEX_CLOSE,
                False,
                "INDEX_MARKET_UNKNOWN",
                f"no calendar source for {spec_name}",
            )
    except Exception as exc:
        return SessionAuthority(
            False,
            False,
            False,
            _INDEX_CLOSE,
            False,
            "INDEX_CALENDAR_IMPORT_FAILED",
            type(exc).__name__,
        )
    try:
        r = evaluate_market_session(now=now, holiday_calendar=cal)
    except Exception as exc:
        return SessionAuthority(
            False,
            False,
            False,
            _INDEX_CLOSE,
            False,
            "INDEX_CALENDAR_RAISED",
            type(exc).__name__,
        )

    market_open = bool(r.get("market_open"))
    reasons = list(r.get("reasons") or [])

    # market_session_guard treats MARKET_CLOSE_TIME inclusively (<=), so 15:30
    # is reported SESSION_VALID. The supervisor needs close exclusive: at 15:30
    # the cooperative stop path must run. Clamp here, independent of the guard.
    try:
        _now_t = now.timetz().replace(tzinfo=None)
    except Exception:
        _now_t = None
    if _now_t is not None and _now_t >= _INDEX_CLOSE:
        market_open = False
        reasons = reasons + ["INDEX_CLOSE_EXCLUSIVE_1530"]

    return SessionAuthority(
        session_open=market_open,
        new_entries_allowed=market_open,
        position_management_allowed=market_open,
        close_time=_INDEX_CLOSE,
        calendar_authoritative=True,
        status=str(r.get("status", "UNKNOWN")),
        note="; ".join(reasons) if reasons else str(r.get("status", "")),
    )


def authority_for(spec, now):
    """Return SessionAuthority for one WorkerSpecV2 at now (timezone-aware IST)."""
    if spec.market_type == "COMMODITY":
        return _mcx_authority(now)
    if spec.market_type == "INDEX":
        return _index_authority(now, spec.name)
    return SessionAuthority(
        False,
        False,
        False,
        None,
        False,
        "MARKET_TYPE_UNKNOWN",
        f"{spec.market_type}",
    )
