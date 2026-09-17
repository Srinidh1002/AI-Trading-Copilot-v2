"""Immutable PAPER-only input for P8 portfolio admission."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from .integrated_three_target_trade_plan_result_v1 import IntegratedThreeTargetTradePlanResultV1
from .paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from .paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


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
class PaperPortfolioAdmissionInputV1:
    admission_request_id: str
    admission_idempotency_key: str
    portfolio_event_id: str
    portfolio_id: str
    requested_reservation_id: str
    evaluated_at: datetime
    trading_day_id: str
    integrated_trade_plan_result: IntegratedThreeTargetTradePlanResultV1
    current_portfolio_snapshot: PaperPortfolioSnapshotV1
    portfolio_policy: PaperPortfolioPolicyV1
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "admission_request_id",
            "admission_idempotency_key",
            "portfolio_event_id",
            "portfolio_id",
            "requested_reservation_id",
            "trading_day_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))

        if type(self.integrated_trade_plan_result) is not IntegratedThreeTargetTradePlanResultV1:
            raise TypeError("integrated_trade_plan_result must be exact IntegratedThreeTargetTradePlanResultV1")
        if type(self.current_portfolio_snapshot) is not PaperPortfolioSnapshotV1:
            raise TypeError("current_portfolio_snapshot must be exact PaperPortfolioSnapshotV1")
        if type(self.portfolio_policy) is not PaperPortfolioPolicyV1:
            raise TypeError("portfolio_policy must be exact PaperPortfolioPolicyV1")

        if self.current_portfolio_snapshot.portfolio_id != self.portfolio_id:
            raise ValueError("portfolio identity mismatch")
        if self.current_portfolio_snapshot.trading_day_id != self.trading_day_id:
            raise ValueError("trading day mismatch")
        if self.current_portfolio_snapshot.portfolio_policy_id != self.portfolio_policy.portfolio_policy_id:
            raise ValueError("portfolio policy mismatch")

        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only admission input required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "admission_idempotency_key": self.admission_idempotency_key,
            "portfolio_id": self.portfolio_id,
            "requested_reservation_id": self.requested_reservation_id,
            "trading_day_id": self.trading_day_id,
            "integrated_trade_plan_result": self.integrated_trade_plan_result.to_dict(),
            "current_portfolio_snapshot": self.current_portfolio_snapshot.semantic_dict(),
            "portfolio_policy": self.portfolio_policy.semantic_dict(),
            "metadata": _plain(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    @property
    def semantic_payload_hash(self) -> str:
        payload = json.dumps(
            self.semantic_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission_request_id": self.admission_request_id,
            "admission_idempotency_key": self.admission_idempotency_key,
            "portfolio_event_id": self.portfolio_event_id,
            "portfolio_id": self.portfolio_id,
            "requested_reservation_id": self.requested_reservation_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "trading_day_id": self.trading_day_id,
            "integrated_trade_plan_result": self.integrated_trade_plan_result.to_dict(),
            "current_portfolio_snapshot": self.current_portfolio_snapshot.to_dict(),
            "portfolio_policy": self.portfolio_policy.to_dict(),
            "metadata": _plain(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
