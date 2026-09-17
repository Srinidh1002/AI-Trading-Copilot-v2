"""Immutable PAPER-only result of P8 portfolio admission."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from .paper_capital_reservation_v1 import PaperCapitalReservationV1
from .paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1

_STATUSES = frozenset({"APPROVED", "NO_CAPACITY", "BLOCKED"})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _number(value: object, name: str, *, nonnegative: bool = True) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _integer(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{name} must be an exact int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _diagnostics(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")
    result: list[str] = []
    for item in value:
        item = _text(item, name)
        if item not in result:
            result.append(item)
    return tuple(result)


def _freeze(value: object) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("metadata must be JSON-safe")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(dict(sorted((_text(k, "metadata key"), _freeze(v)) for k, v in value.items())))
    if type(value) in (tuple, list):
        return tuple(_freeze(item) for item in value)
    raise ValueError("metadata must be JSON-safe")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class PaperPortfolioAdmissionResultV1:
    admission_result_id: str
    admission_request_id: str
    admission_idempotency_key: str
    admission_payload_hash: str
    portfolio_event_id: str
    portfolio_id: str
    portfolio_policy_id: str
    trading_day_id: str
    integration_id: str
    trade_plan_id: str
    requested_reservation_id: str
    status: str
    approved: bool
    reservation_amount: float
    reserved_risk_amount: float
    projected_available_cash: float
    projected_reserved_capital: float
    projected_deployed_capital: float
    projected_committed_capital: float
    projected_concurrent_trade_count: int
    projected_aggregate_committed_risk: float
    evaluated_at: datetime
    resulting_reservation: PaperCapitalReservationV1 | None = None
    resulting_snapshot: PaperPortfolioSnapshotV1 | None = None
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "admission_result_id",
            "admission_request_id",
            "admission_idempotency_key",
            "admission_payload_hash",
            "portfolio_event_id",
            "portfolio_id",
            "portfolio_policy_id",
            "trading_day_id",
            "integration_id",
            "trade_plan_id",
            "requested_reservation_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        if self.status not in _STATUSES:
            raise ValueError("unsupported admission status")
        if type(self.approved) is not bool:
            raise TypeError("approved must be a bool")
        for name in (
            "reservation_amount",
            "reserved_risk_amount",
            "projected_reserved_capital",
            "projected_deployed_capital",
            "projected_committed_capital",
            "projected_aggregate_committed_risk",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        object.__setattr__(
            self,
            "projected_available_cash",
            _number(self.projected_available_cash, "projected_available_cash", nonnegative=False),
        )
        object.__setattr__(
            self,
            "projected_concurrent_trade_count",
            _integer(self.projected_concurrent_trade_count, "projected_concurrent_trade_count"),
        )
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))

        if self.resulting_reservation is not None and type(self.resulting_reservation) is not PaperCapitalReservationV1:
            raise TypeError("resulting_reservation must be exact PaperCapitalReservationV1")
        if self.resulting_snapshot is not None and type(self.resulting_snapshot) is not PaperPortfolioSnapshotV1:
            raise TypeError("resulting_snapshot must be exact PaperPortfolioSnapshotV1")

        for name in ("blockers", "decision_reasons", "warnings"):
            object.__setattr__(self, name, _diagnostics(getattr(self, name), name))

        if self.status == "APPROVED":
            if not self.approved:
                raise ValueError("APPROVED requires approved=True")
            if self.blockers or self.decision_reasons:
                raise ValueError("APPROVED cannot contain blockers or decision reasons")
            if self.resulting_reservation is None or self.resulting_snapshot is None:
                raise ValueError("APPROVED requires reservation and snapshot")
            if self.resulting_reservation.reservation_status != "PENDING_HOLD":
                raise ValueError("APPROVED requires a PENDING_HOLD reservation")
            if self.resulting_reservation.reservation_id != self.requested_reservation_id:
                raise ValueError("reservation identity mismatch")
            if self.resulting_snapshot.portfolio_id != self.portfolio_id:
                raise ValueError("snapshot portfolio mismatch")
        elif self.status == "NO_CAPACITY":
            if self.approved:
                raise ValueError("NO_CAPACITY requires approved=False")
            if self.blockers or not self.decision_reasons:
                raise ValueError("NO_CAPACITY requires decision reasons and no blockers")
            if self.resulting_reservation is not None or self.resulting_snapshot is not None:
                raise ValueError("NO_CAPACITY must not produce state")
        else:
            if self.approved:
                raise ValueError("BLOCKED requires approved=False")
            if not self.blockers:
                raise ValueError("BLOCKED requires blockers")
            if self.resulting_reservation is not None or self.resulting_snapshot is not None:
                raise ValueError("BLOCKED must not produce state")

        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only admission result required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["evaluated_at"] = self.evaluated_at.isoformat()
        result["resulting_reservation"] = (
            None if self.resulting_reservation is None else self.resulting_reservation.to_dict()
        )
        result["resulting_snapshot"] = (
            None if self.resulting_snapshot is None else self.resulting_snapshot.to_dict()
        )
        for name in ("blockers", "decision_reasons", "warnings"):
            result[name] = list(result[name])
        result["metadata"] = _plain(self.metadata)
        return result

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("admission_result_id")
        result.pop("evaluated_at")
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
