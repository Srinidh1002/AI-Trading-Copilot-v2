"""Immutable PAPER-only portfolio snapshot for P8."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from .paper_capital_reservation_v1 import PaperCapitalReservationV1
from .paper_portfolio_exposure_v1 import PaperPortfolioExposureV1
from .paper_portfolio_lock_state_v1 import PaperPortfolioLockStateV1
from .paper_portfolio_position_reference_v1 import PaperPortfolioPositionReferenceV1


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _number(value: object, name: str, *, nonnegative: bool = False) -> float:
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


def _typed_tuple(value: object, expected_type: type, name: str) -> tuple[Any, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")
    if any(type(item) is not expected_type for item in value):
        raise TypeError(f"{name} contains an invalid item type")
    return value


@dataclass(frozen=True, slots=True)
class PaperPortfolioSnapshotV1:
    portfolio_snapshot_id: str
    portfolio_id: str
    portfolio_policy_id: str
    trading_day_id: str
    starting_capital: float
    available_cash: float
    reserved_capital: float
    deployed_capital: float
    committed_capital: float
    realized_net_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_equity: float
    portfolio_return_fraction: float
    capital_utilization_fraction: float
    open_position_count: int
    pending_plan_count: int
    concurrent_trade_count: int
    aggregate_active_risk: float
    aggregate_pending_risk: float
    aggregate_committed_risk: float
    reservations: tuple[PaperCapitalReservationV1, ...]
    position_references: tuple[PaperPortfolioPositionReferenceV1, ...]
    exposure: PaperPortfolioExposureV1
    lock_state: PaperPortfolioLockStateV1
    event_sequence: int
    created_at: datetime
    updated_at: datetime
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "portfolio_snapshot_id",
            "portfolio_id",
            "portfolio_policy_id",
            "trading_day_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        object.__setattr__(self, "starting_capital", _number(self.starting_capital, "starting_capital", nonnegative=True))
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")

        for name in (
            "reserved_capital",
            "deployed_capital",
            "committed_capital",
            "total_equity",
            "capital_utilization_fraction",
            "aggregate_active_risk",
            "aggregate_pending_risk",
            "aggregate_committed_risk",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name, nonnegative=True))
        for name in (
            "available_cash",
            "realized_net_pnl",
            "unrealized_pnl",
            "total_pnl",
            "portfolio_return_fraction",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))

        for name in (
            "open_position_count",
            "pending_plan_count",
            "concurrent_trade_count",
            "event_sequence",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name))

        object.__setattr__(
            self,
            "reservations",
            _typed_tuple(self.reservations, PaperCapitalReservationV1, "reservations"),
        )
        object.__setattr__(
            self,
            "position_references",
            _typed_tuple(
                self.position_references,
                PaperPortfolioPositionReferenceV1,
                "position_references",
            ),
        )
        if type(self.exposure) is not PaperPortfolioExposureV1:
            raise TypeError("exposure must be an exact PaperPortfolioExposureV1")
        if type(self.lock_state) is not PaperPortfolioLockStateV1:
            raise TypeError("lock_state must be an exact PaperPortfolioLockStateV1")

        reservation_ids = [item.reservation_id for item in self.reservations]
        if len(reservation_ids) != len(set(reservation_ids)):
            raise ValueError("duplicate reservation_id")
        plan_ids = [item.trade_plan_id for item in self.reservations]
        if len(plan_ids) != len(set(plan_ids)):
            raise ValueError("duplicate trade_plan_id")
        position_ids = [item.position_id for item in self.position_references]
        if len(position_ids) != len(set(position_ids)):
            raise ValueError("duplicate position_id")

        for reservation in self.reservations:
            if reservation.portfolio_id != self.portfolio_id:
                raise ValueError("reservation portfolio mismatch")
        reservation_by_id = {item.reservation_id: item for item in self.reservations}
        for reference in self.position_references:
            if reference.portfolio_id != self.portfolio_id:
                raise ValueError("position reference portfolio mismatch")
            reservation = reservation_by_id.get(reference.reservation_id)
            if reservation is None:
                raise ValueError("position reference has no reservation")
            if reservation.position_id != reference.position_id:
                raise ValueError("reservation position mismatch")

        reserved_expected = math.fsum(
            item.remaining_capital_amount
            for item in sorted(self.reservations, key=lambda x: x.reservation_id)
            if item.reservation_status == "PENDING_HOLD"
        )
        deployed_expected = math.fsum(
            item.remaining_capital_amount
            for item in sorted(self.reservations, key=lambda x: x.reservation_id)
            if item.reservation_status == "ACTIVE"
        )
        active_risk_expected = math.fsum(
            item.remaining_risk_amount
            for item in sorted(self.reservations, key=lambda x: x.reservation_id)
            if item.reservation_status == "ACTIVE"
        )
        pending_risk_expected = math.fsum(
            item.remaining_risk_amount
            for item in sorted(self.reservations, key=lambda x: x.reservation_id)
            if item.reservation_status == "PENDING_HOLD"
        )
        realized_expected = math.fsum(
            item.realized_net_pnl
            for item in sorted(self.position_references, key=lambda x: x.position_id)
        )
        unrealized_expected = math.fsum(
            item.unrealized_pnl
            for item in sorted(self.position_references, key=lambda x: x.position_id)
            if not item.is_terminal
        )

        expected_pairs = (
            ("reserved_capital", self.reserved_capital, reserved_expected),
            ("deployed_capital", self.deployed_capital, deployed_expected),
            ("committed_capital", self.committed_capital, reserved_expected + deployed_expected),
            ("aggregate_active_risk", self.aggregate_active_risk, active_risk_expected),
            ("aggregate_pending_risk", self.aggregate_pending_risk, pending_risk_expected),
            ("aggregate_committed_risk", self.aggregate_committed_risk, active_risk_expected + pending_risk_expected),
            ("realized_net_pnl", self.realized_net_pnl, realized_expected),
            ("unrealized_pnl", self.unrealized_pnl, unrealized_expected),
            ("total_pnl", self.total_pnl, realized_expected + unrealized_expected),
            ("total_equity", self.total_equity, self.starting_capital + self.total_pnl),
            ("available_cash", self.available_cash, self.total_equity - self.committed_capital),
            ("portfolio_return_fraction", self.portfolio_return_fraction, self.total_pnl / self.starting_capital),
            ("capital_utilization_fraction", self.capital_utilization_fraction, self.committed_capital / self.starting_capital),
        )
        for name, supplied, expected in expected_pairs:
            if not math.isclose(supplied, expected, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f"{name} mismatch")

        open_expected = sum(1 for item in self.position_references if not item.is_terminal)
        pending_expected = sum(1 for item in self.reservations if item.reservation_status == "PENDING_HOLD")
        if self.open_position_count != open_expected:
            raise ValueError("open_position_count mismatch")
        if self.pending_plan_count != pending_expected:
            raise ValueError("pending_plan_count mismatch")
        if self.concurrent_trade_count != open_expected + pending_expected:
            raise ValueError("concurrent_trade_count mismatch")

        if self.lock_state.trading_day_id != self.trading_day_id:
            raise ValueError("lock_state trading day mismatch")

        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _aware(self.updated_at, "updated_at"))
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")

        for name in ("blockers", "decision_reasons", "warnings"):
            object.__setattr__(self, name, _diagnostics(getattr(self, name), name))
        object.__setattr__(self, "provenance", _freeze(self.provenance))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only snapshot required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["reservations"] = [item.to_dict() for item in self.reservations]
        result["position_references"] = [item.to_dict() for item in self.position_references]
        result["exposure"] = self.exposure.to_dict()
        result["lock_state"] = self.lock_state.to_dict()
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        for name in ("blockers", "decision_reasons", "warnings"):
            result[name] = list(result[name])
        result["provenance"] = _plain(self.provenance)
        result["metadata"] = _plain(self.metadata)
        return result

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("portfolio_snapshot_id")
        result.pop("created_at")
        result.pop("updated_at")
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
