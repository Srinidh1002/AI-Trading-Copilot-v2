"""Immutable ordered observation for one retained prediction."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar


_IDENTITIES = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}
_EVENT_TYPES = {
    "NONE",
    "ENTRY",
    "T1",
    "T2",
    "T3",
    "TERMINAL_T1",
    "TERMINAL_T2",
    "TERMINAL_T3",
    "STOP",
    "EARLY_EXIT",
    "INVALIDATED",
    "SESSION_CLOSE",
    "EXPIRY",
    "DATA_GAP",
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
class PredictionObservationV1:
    """One supplied evidence point in an explicit sequence."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_observation.v1"
    )

    observation_id: str
    prediction_id: str
    parent_cycle_id: str
    underlying_symbol: str
    exchange: str
    sequence_number: int
    observed_at: datetime
    underlying_price: float | None
    option_premium: float | None
    event_type: str = "NONE"
    within_entry_window: bool = False
    data_available: bool = True
    source_observation_id: str | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "prediction_id",
            "parent_cycle_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        identity = (
            _text(
                self.underlying_symbol,
                "underlying_symbol",
            ).upper(),
            _text(
                self.exchange,
                "exchange",
            ).upper(),
        )
        if identity not in _IDENTITIES:
            raise ValueError("market identity")
        object.__setattr__(
            self,
            "underlying_symbol",
            identity[0],
        )
        object.__setattr__(
            self,
            "exchange",
            identity[1],
        )

        if (
            type(self.sequence_number) is not int
            or isinstance(self.sequence_number, bool)
            or self.sequence_number <= 0
        ):
            raise ValueError("sequence_number")

        object.__setattr__(
            self,
            "observed_at",
            _aware(self.observed_at, "observed_at"),
        )
        object.__setattr__(
            self,
            "underlying_price",
            _optional_positive(
                self.underlying_price,
                "underlying_price",
            ),
        )
        object.__setattr__(
            self,
            "option_premium",
            _optional_positive(
                self.option_premium,
                "option_premium",
            ),
        )

        event = _text(
            self.event_type,
            "event_type",
        ).upper()
        if event not in _EVENT_TYPES:
            raise ValueError("event_type")
        object.__setattr__(
            self,
            "event_type",
            event,
        )

        for name in (
            "within_entry_window",
            "data_available",
            "live_execution_eligible",
            "broker_order_submission",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if self.source_observation_id is not None:
            object.__setattr__(
                self,
                "source_observation_id",
                _text(
                    self.source_observation_id,
                    "source_observation_id",
                ),
            )

        if self.data_available:
            if self.underlying_price is None:
                raise ValueError(
                    "available observation requires underlying price"
                )
            if event == "DATA_GAP":
                raise ValueError(
                    "DATA_GAP requires unavailable evidence"
                )
        else:
            if (
                self.underlying_price is not None
                or self.option_premium is not None
                or event != "DATA_GAP"
                or self.within_entry_window
            ):
                raise ValueError(
                    "unavailable observation coherence"
                )

        if (
            event in {"ENTRY", "T1", "T2", "T3", "TERMINAL_T1", "TERMINAL_T2", "TERMINAL_T3", "STOP", "EARLY_EXIT"}
            and self.option_premium is None
        ):
            raise ValueError(
                "option lifecycle event requires option premium"
            )

        if event == "ENTRY" and not self.within_entry_window:
            raise ValueError(
                "ENTRY must occur within entry window"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only prediction observation"
            )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["observed_at"] = self.observed_at.isoformat()
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
