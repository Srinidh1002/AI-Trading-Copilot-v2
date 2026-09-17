from __future__ import annotations

from datetime import date, datetime

from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemStatus,
    Task9CloseDrainItemV1,
    Task9CloseDrainStateV1,
    Task9CloseDrainStatus,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)


_MARKET_SEGMENTS = {
    "NIFTY": Task9MarketSegment.NFO_OPTIONS,
    "SENSEX": Task9MarketSegment.BFO_OPTIONS,
}


def evaluate_task9_close_drain(
    *,
    official_run_id: str,
    market_date: date,
    evaluated_at: datetime,
    session_states: tuple[
        Task9SegmentSessionStateV1,
        Task9SegmentSessionStateV1,
    ],
    items: tuple[Task9CloseDrainItemV1, ...],
) -> Task9CloseDrainStateV1:
    if (
        type(official_run_id) is not str
        or not official_run_id.strip()
    ):
        raise ValueError("official_run_id")

    if type(market_date) is not date:
        raise TypeError("market_date")

    if (
        not isinstance(evaluated_at, datetime)
        or evaluated_at.tzinfo is None
        or evaluated_at.utcoffset() is None
    ):
        raise ValueError("evaluated_at")

    if (
        type(session_states) is not tuple
        or len(session_states) != 2
    ):
        raise ValueError(
            "exact NIFTY/SENSEX canonical session authority required"
        )

    states_by_market = {}

    for state in session_states:
        if type(state) is not Task9SegmentSessionStateV1:
            raise TypeError("session state")

        market = next(
            (
                market
                for market, segment
                in _MARKET_SEGMENTS.items()
                if state.segment is segment
            ),
            None,
        )
        if market is None:
            raise ValueError(
                "unsupported close-drain segment"
            )

        if market in states_by_market:
            raise ValueError(
                "duplicate close-drain session market"
            )

        if state.market_date != market_date:
            raise ValueError(
                "close-drain session date mismatch"
            )

        states_by_market[market] = state

    if set(states_by_market) != set(_MARKET_SEGMENTS):
        raise ValueError(
            "exact NIFTY/SENSEX canonical session authority required"
        )

    if type(items) is not tuple:
        raise TypeError("items")
    if any(
        type(item) is not Task9CloseDrainItemV1
        for item in items
    ):
        raise TypeError("items")

    ordered_items = tuple(
        sorted(
            items,
            key=lambda item: (
                item.market,
                item.prediction_id,
                item.kind.value,
            ),
        )
    )

    phases = tuple(
        (
            market,
            states_by_market[market].phase.value,
        )
        for market in ("NIFTY", "SENSEX")
    )

    closed = tuple(
        states_by_market[market].phase
        is Task9SessionPhase.CLOSED
        for market in ("NIFTY", "SENSEX")
    )

    # Session finalization is a two-market boundary.
    # Before both canonical F&O segments are CLOSED,
    # no close drain or final archival is authorized.
    if not all(closed):
        return Task9CloseDrainStateV1(
            official_run_id=official_run_id,
            market_date=market_date,
            evaluated_at=evaluated_at,
            status=Task9CloseDrainStatus.NOT_REQUIRED,
            session_phases=phases,
            items=ordered_items,
        )

    blocked = tuple(
        item
        for item in ordered_items
        if item.status
        is Task9CloseDrainItemStatus.BLOCKED
    )
    if blocked:
        reasons = tuple(
            dict.fromkeys(
                reason
                for item in blocked
                for reason in item.reason_codes
            )
        )
        return Task9CloseDrainStateV1(
            official_run_id=official_run_id,
            market_date=market_date,
            evaluated_at=evaluated_at,
            status=Task9CloseDrainStatus.BLOCKED,
            session_phases=phases,
            items=ordered_items,
            reason_codes=reasons,
        )

    pending = tuple(
        item
        for item in ordered_items
        if item.status
        is Task9CloseDrainItemStatus.PENDING
    )
    if pending:
        reasons = tuple(
            dict.fromkeys(
                reason
                for item in pending
                for reason in item.reason_codes
            )
        )
        return Task9CloseDrainStateV1(
            official_run_id=official_run_id,
            market_date=market_date,
            evaluated_at=evaluated_at,
            status=Task9CloseDrainStatus.PENDING,
            session_phases=phases,
            items=ordered_items,
            reason_codes=reasons,
        )

    return Task9CloseDrainStateV1(
        official_run_id=official_run_id,
        market_date=market_date,
        evaluated_at=evaluated_at,
        status=Task9CloseDrainStatus.COMPLETE,
        session_phases=phases,
        items=ordered_items,
    )
