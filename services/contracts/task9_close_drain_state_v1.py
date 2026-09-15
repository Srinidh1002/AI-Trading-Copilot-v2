from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from enum import Enum
from typing import ClassVar


class Task9CloseDrainStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class Task9CloseDrainItemKind(str, Enum):
    ABSTENTION = "ABSTENTION"
    PAPER_TRADE = "PAPER_TRADE"


class Task9CloseDrainItemStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    return tuple(
        dict.fromkeys(
            _text(item, name)
            for item in value
        )
    )


@dataclass(frozen=True, slots=True)
class Task9CloseDrainItemV1:
    prediction_id: str
    market: str
    kind: Task9CloseDrainItemKind
    status: Task9CloseDrainItemStatus
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prediction_id",
            _text(self.prediction_id, "prediction_id"),
        )

        market = _text(self.market, "market").upper()
        if market not in {"NIFTY", "SENSEX"}:
            raise ValueError("market")
        object.__setattr__(self, "market", market)

        if type(self.kind) is not Task9CloseDrainItemKind:
            raise TypeError("kind")
        if type(self.status) is not Task9CloseDrainItemStatus:
            raise TypeError("status")

        reasons = _messages(
            self.reason_codes,
            "reason_codes",
        )
        object.__setattr__(
            self,
            "reason_codes",
            reasons,
        )

        if (
            self.status is Task9CloseDrainItemStatus.COMPLETE
            and reasons
        ):
            raise ValueError(
                "complete close-drain item cannot have reasons"
            )

        if (
            self.status
            in {
                Task9CloseDrainItemStatus.PENDING,
                Task9CloseDrainItemStatus.BLOCKED,
            }
            and not reasons
        ):
            raise ValueError(
                "incomplete close-drain item requires reason"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "prediction_id": self.prediction_id,
            "market": self.market,
            "kind": self.kind.value,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class Task9CloseDrainStateV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_close_drain_state.v1"
    )

    official_run_id: str
    market_date: date
    evaluated_at: datetime
    status: Task9CloseDrainStatus
    session_phases: tuple[tuple[str, str], ...]
    items: tuple[Task9CloseDrainItemV1, ...]
    reason_codes: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "official_run_id",
            _text(
                self.official_run_id,
                "official_run_id",
            ),
        )

        if type(self.market_date) is not date:
            raise TypeError("market_date")

        object.__setattr__(
            self,
            "evaluated_at",
            _aware(
                self.evaluated_at,
                "evaluated_at",
            ),
        )

        if type(self.status) is not Task9CloseDrainStatus:
            raise TypeError("status")

        if type(self.session_phases) is not tuple:
            raise TypeError("session_phases")

        expected_markets = ("NIFTY", "SENSEX")
        actual_markets = tuple(
            item[0]
            for item in self.session_phases
        )
        if actual_markets != expected_markets:
            raise ValueError("session_phases")

        for market, phase in self.session_phases:
            _text(market, "session market")
            _text(phase, "session phase")

        if type(self.items) is not tuple:
            raise TypeError("items")
        if any(
            type(item) is not Task9CloseDrainItemV1
            for item in self.items
        ):
            raise TypeError("items")

        ordered_items = tuple(
            sorted(
                self.items,
                key=lambda item: (
                    item.market,
                    item.prediction_id,
                    item.kind.value,
                ),
            )
        )
        if self.items != ordered_items:
            raise ValueError(
                "close-drain items must be deterministic"
            )

        if len({
            item.prediction_id
            for item in self.items
        }) != len(self.items):
            raise ValueError(
                "duplicate close-drain prediction"
            )

        reasons = _messages(
            self.reason_codes,
            "reason_codes",
        )
        object.__setattr__(
            self,
            "reason_codes",
            reasons,
        )

        if (
            self.status
            in {
                Task9CloseDrainStatus.COMPLETE,
                Task9CloseDrainStatus.NOT_REQUIRED,
            }
            and reasons
        ):
            raise ValueError(
                "terminal clean drain state cannot have reasons"
            )

        if (
            self.status
            in {
                Task9CloseDrainStatus.PENDING,
                Task9CloseDrainStatus.BLOCKED,
            }
            and not reasons
        ):
            raise ValueError(
                "incomplete drain state requires reasons"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "Task9 close-drain must remain PAPER-only"
            )

    @property
    def finalization_allowed(self) -> bool:
        return self.status is Task9CloseDrainStatus.COMPLETE

    @property
    def pending_prediction_ids(self) -> tuple[str, ...]:
        return tuple(
            item.prediction_id
            for item in self.items
            if item.status
            is Task9CloseDrainItemStatus.PENDING
        )

    @property
    def blocked_prediction_ids(self) -> tuple[str, ...]:
        return tuple(
            item.prediction_id
            for item in self.items
            if item.status
            is Task9CloseDrainItemStatus.BLOCKED
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "official_run_id": self.official_run_id,
            "market_date": self.market_date.isoformat(),
            "evaluated_at": self.evaluated_at.isoformat(),
            "status": self.status.value,
            "session_phases": [
                [market, phase]
                for market, phase
                in self.session_phases
            ],
            "items": [
                item.to_dict()
                for item in self.items
            ],
            "reason_codes": list(self.reason_codes),
            "execution_mode": self.execution_mode,
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
            "schema_version": self.schema_version,
        }
