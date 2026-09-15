"""Produce Task 9 WebSocket readiness from durable collector evidence.

Authority:
- collector ownership lock
- persisted validated Task9 WebSocket ticks

No provider or socket call occurs here.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from services.certification.task9_live_websocket_collector import (
    Task9LiveStreamCollectorLock,
)
from services.contracts.task9_websocket_runtime_proof_v1 import (
    Task9WebsocketRuntimeProbeStatus,
    Task9WebsocketRuntimeProofV1,
)
from services.market.task9_live_tick_stream import (
    Task9LiveTickJournal,
)


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def _lock_state(
    live_stream_root: Path,
) -> tuple[bool, bool]:
    path = (
        live_stream_root
        / Task9LiveStreamCollectorLock.filename
    )

    if not path.exists():
        return False, False

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return True, False

    if (
        type(value) is not dict
        or set(value)
        != {
            "pid",
            "acquired_at",
            "ownership_token",
        }
    ):
        return True, False

    try:
        pid = int(value["pid"])
        acquired_at = datetime.fromisoformat(
            value["acquired_at"]
        )
    except (
        TypeError,
        ValueError,
    ):
        return True, False

    token = value.get(
        "ownership_token"
    )

    valid = (
        pid > 0
        and acquired_at.tzinfo is not None
        and acquired_at.utcoffset() is not None
        and type(token) is str
        and bool(token.strip())
    )

    return True, valid


def produce_task9_websocket_runtime_proof(
    *,
    live_stream_root,
    market_date,
    observed_at: datetime,
    maximum_tick_age_seconds: float,
) -> Task9WebsocketRuntimeProofV1:
    """Read durable collector facts and fail closed."""

    observed_at = _aware(
        observed_at,
        "observed_at",
    )

    if maximum_tick_age_seconds <= 0:
        raise ValueError(
            "maximum_tick_age_seconds"
        )

    root = Path(
        live_stream_root
    )

    lock_present, lock_valid = (
        _lock_state(root)
    )

    try:
        # Task9RuntimeConfigV1 exposes market_date at the startup boundary
        # as its canonical ISO date representation, while
        # Task9LiveTickJournal intentionally owns a date-typed API.
        #
        # Normalize only those two exact supported forms. Everything else
        # continues to fail closed through the existing INVALID proof path.
        from datetime import date as _date

        if type(market_date) is _date:
            journal_market_date = market_date
        elif type(market_date) is str:
            journal_market_date = _date.fromisoformat(
                market_date
            )
        else:
            raise TypeError(
                "market_date"
            )

        ticks = Task9LiveTickJournal(
            root
        ).load(
            journal_market_date
        )
    except Exception:
        return Task9WebsocketRuntimeProofV1(
            proof_id=(
                "task9-websocket-runtime:"
                f"{market_date}:"
                f"{observed_at.isoformat()}"
            ),
            observed_at=observed_at,
            status=(
                Task9WebsocketRuntimeProbeStatus.INVALID
            ),
            collector_lock_present=lock_present,
            collector_lock_valid=lock_valid,
            nifty_tick_received_at=None,
            sensex_tick_received_at=None,
            nifty_provider_timestamp=None,
            sensex_provider_timestamp=None,
            maximum_tick_age_seconds=(
                maximum_tick_age_seconds
            ),
            source_ref=None,
            sanitized_reason=(
                "TASK9_WEBSOCKET_JOURNAL_INVALID"
            ),
        )

    latest = {}

    for market in (
        "NIFTY",
        "SENSEX",
    ):
        # This proof is an as-of observation at ``observed_at``.
        #
        # The live collector continues appending while startup performs
        # unrelated provider acquisition. Rows received after observed_at
        # therefore belong to a later state and must not make the frozen
        # startup snapshot look "future".
        #
        # Provider timestamps on rows that were already received by the
        # snapshot remain fully validated below; a provider timestamp later
        # than observed_at still fails closed.
        candidates = tuple(
            tick
            for tick in ticks
            if (
                tick.market == market
                and tick.received_at <= observed_at
            )
        )

        if candidates:
            latest[market] = max(
                candidates,
                key=lambda item: (
                    item.received_at,
                    item.provider_timestamp,
                ),
            )
        else:
            latest[market] = None

    nifty = latest["NIFTY"]
    sensex = latest["SENSEX"]

    reasons = []

    if not lock_present:
        reasons.append(
            "COLLECTOR_LOCK_MISSING"
        )
    elif not lock_valid:
        reasons.append(
            "COLLECTOR_LOCK_INVALID"
        )

    for market, tick in (
        ("NIFTY", nifty),
        ("SENSEX", sensex),
    ):
        if tick is None:
            reasons.append(
                f"{market}_WEBSOCKET_TICK_MISSING"
            )
            continue

        age = (
            observed_at
            - tick.received_at
        ).total_seconds()

        provider_age = (
            observed_at
            - tick.provider_timestamp
        ).total_seconds()

        if age < 0 or provider_age < 0:
            reasons.append(
                f"{market}_WEBSOCKET_TIMESTAMP_FUTURE"
            )
            continue

        if age > maximum_tick_age_seconds:
            reasons.append(
                f"{market}_WEBSOCKET_TICK_STALE"
            )

        if provider_age > maximum_tick_age_seconds:
            reasons.append(
                f"{market}_WEBSOCKET_PROVIDER_STALE"
            )

    ready = not reasons

    return Task9WebsocketRuntimeProofV1(
        proof_id=(
            "task9-websocket-runtime:"
            f"{market_date}:"
            f"{observed_at.isoformat()}"
        ),
        observed_at=observed_at,
        status=(
            Task9WebsocketRuntimeProbeStatus.READY
            if ready
            else Task9WebsocketRuntimeProbeStatus.NOT_READY
        ),
        collector_lock_present=lock_present,
        collector_lock_valid=lock_valid,
        nifty_tick_received_at=(
            nifty.received_at
            if nifty is not None
            else None
        ),
        sensex_tick_received_at=(
            sensex.received_at
            if sensex is not None
            else None
        ),
        nifty_provider_timestamp=(
            nifty.provider_timestamp
            if nifty is not None
            else None
        ),
        sensex_provider_timestamp=(
            sensex.provider_timestamp
            if sensex is not None
            else None
        ),
        maximum_tick_age_seconds=(
            maximum_tick_age_seconds
        ),
        source_ref=(
            "task9-live-websocket-collector"
            if ready
            else None
        ),
        sanitized_reason=(
            None
            if ready
            else "|".join(reasons)
        ),
    )


__all__ = (
    "produce_task9_websocket_runtime_proof",
)
