"""Immutable ordered evidence window for one prediction."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.prediction_observation_v1 import (
    PredictionObservationV1,
)


_TERMINAL_EVENTS = {
    "T3",
    "STOP",
    "EARLY_EXIT",
    "INVALIDATED",
    "SESSION_CLOSE",
    "EXPIRY",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _optional_aware(
    value: object,
    name: str,
) -> datetime | None:
    if value is None:
        return None
    return _aware(value, name)


def _optional_positive(
    value: object,
    name: str,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class PredictionObservationWindowV1:
    """One deterministic projection over ordered supplied evidence."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_observation_window.v1"
    )

    window_id: str
    prediction_id: str
    parent_cycle_id: str
    underlying_symbol: str
    exchange: str
    window_started_at: datetime
    validity_window_ends_at: datetime
    entry_window_ends_at: datetime
    observations: tuple[PredictionObservationV1, ...]
    observation_count: int
    data_gap_count: int
    first_data_gap_at: datetime | None
    entry_occurred: bool
    entry_at: datetime | None
    entry_premium: float | None
    highest_option_premium: float | None
    highest_option_premium_at: datetime | None
    lowest_option_premium: float | None
    lowest_option_premium_at: datetime | None
    highest_underlying_price: float | None
    highest_underlying_price_at: datetime | None
    lowest_underlying_price: float | None
    lowest_underlying_price_at: datetime | None
    first_event_type: str | None
    first_event_at: datetime | None
    terminal_event_type: str | None
    terminal_event_at: datetime | None
    session_closed: bool
    session_closed_at: datetime | None
    expiry_reached: bool
    expiry_reached_at: datetime | None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "window_id",
            "prediction_id",
            "parent_cycle_id",
            "underlying_symbol",
            "exchange",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        started = _aware(
            self.window_started_at,
            "window_started_at",
        )
        validity_end = _aware(
            self.validity_window_ends_at,
            "validity_window_ends_at",
        )
        entry_end = _aware(
            self.entry_window_ends_at,
            "entry_window_ends_at",
        )
        if not (
            started
            <= entry_end
            <= validity_end
        ):
            raise ValueError(
                "window boundary ordering"
            )

        if type(self.observations) is not tuple:
            raise TypeError("observations")
        if any(
            type(item) is not PredictionObservationV1
            for item in self.observations
        ):
            raise TypeError("observations")

        if (
            type(self.observation_count) is not int
            or isinstance(self.observation_count, bool)
            or self.observation_count < 0
            or self.observation_count != len(self.observations)
        ):
            raise ValueError("observation_count")

        if (
            type(self.data_gap_count) is not int
            or isinstance(self.data_gap_count, bool)
            or self.data_gap_count < 0
        ):
            raise ValueError("data_gap_count")

        for name in (
            "entry_occurred",
            "session_closed",
            "expiry_reached",
            "live_execution_eligible",
            "broker_order_submission",
            "read_only",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        for name in (
            "first_data_gap_at",
            "entry_at",
            "highest_option_premium_at",
            "lowest_option_premium_at",
            "highest_underlying_price_at",
            "lowest_underlying_price_at",
            "first_event_at",
            "terminal_event_at",
            "session_closed_at",
            "expiry_reached_at",
        ):
            object.__setattr__(
                self,
                name,
                _optional_aware(
                    getattr(self, name),
                    name,
                ),
            )

        for name in (
            "entry_premium",
            "highest_option_premium",
            "lowest_option_premium",
            "highest_underlying_price",
            "lowest_underlying_price",
        ):
            object.__setattr__(
                self,
                name,
                _optional_positive(
                    getattr(self, name),
                    name,
                ),
            )

        if self.entry_occurred:
            if (
                self.entry_at is None
                or self.entry_premium is None
            ):
                raise ValueError(
                    "entry occurrence requires time and premium"
                )
        elif (
            self.entry_at is not None
            or self.entry_premium is not None
        ):
            raise ValueError(
                "entry fields require entry occurrence"
            )

        pairs = (
            (
                self.highest_option_premium,
                self.highest_option_premium_at,
            ),
            (
                self.lowest_option_premium,
                self.lowest_option_premium_at,
            ),
            (
                self.highest_underlying_price,
                self.highest_underlying_price_at,
            ),
            (
                self.lowest_underlying_price,
                self.lowest_underlying_price_at,
            ),
        )
        if any(
            (value is None) != (occurred_at is None)
            for value, occurred_at in pairs
        ):
            raise ValueError(
                "price extrema require matching timestamps"
            )

        for label_name, time_name in (
            ("first_event_type", "first_event_at"),
            ("terminal_event_type", "terminal_event_at"),
        ):
            label = getattr(self, label_name)
            occurred_at = getattr(self, time_name)
            if (label is None) != (occurred_at is None):
                raise ValueError(
                    f"{label_name} requires matching timestamp"
                )
            if label is not None:
                object.__setattr__(
                    self,
                    label_name,
                    _text(label, label_name).upper(),
                )

        if (
            self.terminal_event_type is not None
            and self.terminal_event_type
            not in _TERMINAL_EVENTS
        ):
            raise ValueError("terminal_event_type")

        if self.session_closed != (
            self.session_closed_at is not None
        ):
            raise ValueError("session closure coherence")
        if self.expiry_reached != (
            self.expiry_reached_at is not None
        ):
            raise ValueError("expiry coherence")
        if self.data_gap_count == 0:
            if self.first_data_gap_at is not None:
                raise ValueError("data-gap coherence")
        elif self.first_data_gap_at is None:
            raise ValueError("data-gap coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only read-only observation window"
            )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        for name in (
            "window_started_at",
            "validity_window_ends_at",
            "entry_window_ends_at",
            "first_data_gap_at",
            "entry_at",
            "highest_option_premium_at",
            "lowest_option_premium_at",
            "highest_underlying_price_at",
            "lowest_underlying_price_at",
            "first_event_at",
            "terminal_event_at",
            "session_closed_at",
            "expiry_reached_at",
        ):
            item = getattr(self, name)
            value[name] = (
                item.isoformat()
                if item is not None
                else None
            )
        value["observations"] = [
            item.to_dict()
            for item in self.observations
        ]
        return value

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
