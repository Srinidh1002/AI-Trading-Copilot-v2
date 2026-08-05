"""Pure deterministic ordered prediction-observation tracker."""
from __future__ import annotations

from datetime import datetime

from services.contracts.prediction_observation_v1 import (
    PredictionObservationV1,
)
from services.contracts.prediction_observation_window_v1 import (
    PredictionObservationWindowV1,
)
from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)


_TERMINAL_EVENTS = {
    "STOP",
    "EARLY_EXIT",
    "INVALIDATED",
    "SESSION_CLOSE",
    "EXPIRY",
}


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _extreme(
    observations: tuple[PredictionObservationV1, ...],
    field: str,
    *,
    highest: bool,
) -> tuple[float | None, datetime | None]:
    available = tuple(
        item
        for item in observations
        if getattr(item, field) is not None
    )
    if not available:
        return None, None

    selected = (
        max(
            available,
            key=lambda item: (
                getattr(item, field),
                -item.sequence_number,
            ),
        )
        if highest
        else min(
            available,
            key=lambda item: (
                getattr(item, field),
                item.sequence_number,
            ),
        )
    )
    return (
        getattr(selected, field),
        selected.observed_at,
    )


def build_prediction_observation_window(
    *,
    prediction: PredictionRecordV1,
    observations: tuple[PredictionObservationV1, ...],
    validity_window_ends_at: datetime,
    entry_window_ends_at: datetime,
) -> PredictionObservationWindowV1:
    """Build one immutable summary from explicitly sequenced evidence."""

    if type(prediction) is not PredictionRecordV1:
        raise TypeError("prediction")
    if type(observations) is not tuple:
        raise TypeError("observations")
    if any(
        type(item) is not PredictionObservationV1
        for item in observations
    ):
        raise TypeError("observations")

    validity_end = _aware(
        validity_window_ends_at,
        "validity_window_ends_at",
    )
    entry_end = _aware(
        entry_window_ends_at,
        "entry_window_ends_at",
    )
    if not (
        prediction.completed_at
        <= entry_end
        <= validity_end
    ):
        raise ValueError(
            "window boundary ordering"
        )

    ordered = tuple(
        sorted(
            observations,
            key=lambda item: item.sequence_number,
        )
    )

    expected_sequences = tuple(
        range(1, len(ordered) + 1)
    )
    if tuple(
        item.sequence_number
        for item in ordered
    ) != expected_sequences:
        raise ValueError(
            "observation sequence must be contiguous from one"
        )

    observation_ids = tuple(
        item.observation_id
        for item in ordered
    )
    if len(set(observation_ids)) != len(observation_ids):
        raise ValueError(
            "duplicate observation_id"
        )

    previous_at = prediction.completed_at
    for item in ordered:
        if (
            item.prediction_id
            != prediction.prediction_id
            or item.parent_cycle_id
            != prediction.parent_cycle_id
            or item.underlying_symbol
            != prediction.underlying_symbol
            or item.exchange
            != prediction.exchange
        ):
            raise ValueError(
                "prediction observation identity mismatch"
            )
        if item.observed_at < previous_at:
            raise ValueError(
                "observation timestamps must be nondecreasing"
            )
        if item.observed_at > validity_end:
            raise ValueError(
                "observation exceeds validity window"
            )
        expected_within_entry_window = (
            item.data_available
            and item.observed_at <= entry_end
        )
        if (
            item.within_entry_window
            != expected_within_entry_window
        ):
            raise ValueError(
                "within_entry_window mismatch"
            )
        previous_at = item.observed_at

    entry_items = tuple(
        item
        for item in ordered
        if item.event_type == "ENTRY"
    )
    if len(entry_items) > 1:
        raise ValueError(
            "entry can occur at most once"
        )
    entry = (
        entry_items[0]
        if entry_items
        else None
    )

    event_items = tuple(
        item
        for item in ordered
        if item.event_type != "NONE"
    )
    first_event = (
        event_items[0]
        if event_items
        else None
    )

    terminal_items = tuple(
        item
        for item in ordered
        if item.event_type in _TERMINAL_EVENTS
    )
    terminal_timestamps = {
        item.observed_at
        for item in terminal_items
    }
    if len(terminal_timestamps) > 1:
        raise ValueError(
            "terminal events can occur at only one timestamp"
        )
    terminal = (
        terminal_items[0]
        if terminal_items
        else None
    )

    if terminal is not None:
        if any(
            item.observed_at > terminal.observed_at
            for item in ordered
        ):
            raise ValueError(
                "observations cannot follow terminal event"
            )

    gaps = tuple(
        item
        for item in ordered
        if item.event_type == "DATA_GAP"
    )
    session_close = next(
        (
            item
            for item in ordered
            if item.event_type == "SESSION_CLOSE"
        ),
        None,
    )
    expiry = next(
        (
            item
            for item in ordered
            if item.event_type == "EXPIRY"
        ),
        None,
    )

    high_option, high_option_at = _extreme(
        ordered,
        "option_premium",
        highest=True,
    )
    low_option, low_option_at = _extreme(
        ordered,
        "option_premium",
        highest=False,
    )
    high_underlying, high_underlying_at = _extreme(
        ordered,
        "underlying_price",
        highest=True,
    )
    low_underlying, low_underlying_at = _extreme(
        ordered,
        "underlying_price",
        highest=False,
    )

    return PredictionObservationWindowV1(
        window_id=(
            f"prediction-window:{prediction.prediction_id}:"
            f"{validity_end.isoformat()}"
        ),
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        window_started_at=prediction.completed_at,
        validity_window_ends_at=validity_end,
        entry_window_ends_at=entry_end,
        observations=ordered,
        observation_count=len(ordered),
        data_gap_count=len(gaps),
        first_data_gap_at=(
            gaps[0].observed_at
            if gaps
            else None
        ),
        entry_occurred=entry is not None,
        entry_at=(
            entry.observed_at
            if entry is not None
            else None
        ),
        entry_premium=(
            entry.option_premium
            if entry is not None
            else None
        ),
        highest_option_premium=high_option,
        highest_option_premium_at=high_option_at,
        lowest_option_premium=low_option,
        lowest_option_premium_at=low_option_at,
        highest_underlying_price=high_underlying,
        highest_underlying_price_at=high_underlying_at,
        lowest_underlying_price=low_underlying,
        lowest_underlying_price_at=low_underlying_at,
        first_event_type=(
            first_event.event_type
            if first_event is not None
            else None
        ),
        first_event_at=(
            first_event.observed_at
            if first_event is not None
            else None
        ),
        terminal_event_type=(
            terminal.event_type
            if terminal is not None
            else None
        ),
        terminal_event_at=(
            terminal.observed_at
            if terminal is not None
            else None
        ),
        session_closed=session_close is not None,
        session_closed_at=(
            session_close.observed_at
            if session_close is not None
            else None
        ),
        expiry_reached=expiry is not None,
        expiry_reached_at=(
            expiry.observed_at
            if expiry is not None
            else None
        ),
    )
