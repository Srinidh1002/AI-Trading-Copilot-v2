"""Canonical Task 9 live-collector session-state resolver.

The collector consumes the same typed post-CAS session authority as the
certification runtime. It does not own or infer trading policy.
"""

from __future__ import annotations

from datetime import date, datetime, time

from services.bse_holiday_calendar import get_bse_holiday_calendar
from services.certification.task9_market_session_evaluator import (
    evaluate_task9_market_session,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    build_task9_market_session_policy,
)
from services.nse_holiday_calendar import get_nse_holiday_calendar


_EXPECTED_SEGMENTS = {
    "NIFTY": Task9MarketSegment.NFO_OPTIONS,
    "SENSEX": Task9MarketSegment.BFO_OPTIONS,
}


def build_task9_live_collector_session_resolver(
    *,
    nfo_new_entry_cutoff: time,
    bfo_new_entry_cutoff: time,
):
    """Build the canonical session resolver used by the live collector."""

    if type(nfo_new_entry_cutoff) is not time:
        raise TypeError("nfo_new_entry_cutoff")

    if type(bfo_new_entry_cutoff) is not time:
        raise TypeError("bfo_new_entry_cutoff")

    policy = build_task9_market_session_policy(
        policy_id="task9-live-collector-session-policy",
        policy_version="1",
        calendar_authority_ref="local-exchange-holiday-calendars",
        nfo_new_entry_cutoff=nfo_new_entry_cutoff,
        bfo_new_entry_cutoff=bfo_new_entry_cutoff,
    )

    def resolve(
        *,
        market: str,
        evaluated_at: datetime,
        market_date: date,
    ):
        if market not in _EXPECTED_SEGMENTS:
            raise ValueError("market")

        if (
            not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None
        ):
            raise ValueError("evaluated_at")

        if type(market_date) is not date:
            raise ValueError("market_date")

        if market_date.weekday() >= 5:
            calendar_state = "NON_TRADING_DAY"
        elif market == "NIFTY":
            calendar_state = (
                "NON_TRADING_DAY"
                if get_nse_holiday_calendar().is_holiday(
                    market_date
                )
                else "TRADING_DAY"
            )
        else:
            calendar_state = (
                "NON_TRADING_DAY"
                if get_bse_holiday_calendar().is_holiday(
                    market_date
                )
                else "TRADING_DAY"
            )

        aggregate = evaluate_task9_market_session(
            policy=policy,
            evaluated_at=evaluated_at,
            market_date=market_date,
            calendar_state=calendar_state,
        )

        expected = _EXPECTED_SEGMENTS[market]

        matches = tuple(
            state
            for state in aggregate.states
            if state.segment is expected
        )

        if len(matches) != 1:
            raise ValueError(
                "TASK9_COLLECTOR_SESSION_STATE_INVALID"
            )

        return matches[0]

    return resolve


__all__ = (
    "build_task9_live_collector_session_resolver",
)
