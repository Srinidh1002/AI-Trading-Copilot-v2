"""Immutable PAPER-only input for P8 portfolio lifecycle updates."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

from .paper_portfolio_snapshot_v1 import PaperPortfolioSnapshotV1
from .paper_trade_persistence_snapshot_v1 import PaperTradePersistenceSnapshotV1
from .paper_trade_entry_evaluation_result_v1 import PaperTradeEntryEvaluationResultV1
from .paper_trade_position_evaluation_result_v1 import PaperTradePositionEvaluationResultV1

_UPDATE_TYPES = frozenset(
    {
        "ENTRY_ACTIVATION",
        "POSITION_UPDATE",
        "TERMINAL_RELEASE",
        "PENDING_RELEASE",
        "DAY_ROLLOVER",
        "RECONCILIATION",
    }
)


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
        return MappingProxyType(
            dict(sorted((_text(k, "metadata key"), _freeze(v)) for k, v in value.items()))
        )
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
class PaperPortfolioUpdateInputV1:
    update_request_id: str
    update_idempotency_key: str
    portfolio_event_id: str
    portfolio_id: str
    source_snapshot_id: str
    requested_result_snapshot_id: str
    requested_event_sequence: int
    evaluated_at: datetime
    trading_day_id: str
    update_type: str
    current_portfolio_snapshot: PaperPortfolioSnapshotV1
    paper_trade_persistence_snapshot: PaperTradePersistenceSnapshotV1
    paper_trade_entry_result: PaperTradeEntryEvaluationResultV1 | None = None
    paper_trade_position_result: PaperTradePositionEvaluationResultV1 | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "update_request_id",
            "update_idempotency_key",
            "portfolio_event_id",
            "portfolio_id",
            "source_snapshot_id",
            "requested_result_snapshot_id",
            "trading_day_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if type(self.requested_event_sequence) is not int or isinstance(
            self.requested_event_sequence, bool
        ):
            raise TypeError("requested_event_sequence must be an exact int")
        if self.requested_event_sequence < 0:
            raise ValueError("requested_event_sequence must be nonnegative")
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        if self.update_type not in _UPDATE_TYPES:
            raise ValueError("unsupported update_type")

        if type(self.current_portfolio_snapshot) is not PaperPortfolioSnapshotV1:
            raise TypeError("current_portfolio_snapshot must be exact PaperPortfolioSnapshotV1")
        if type(self.paper_trade_persistence_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError(
                "paper_trade_persistence_snapshot must be exact PaperTradePersistenceSnapshotV1"
            )
        if self.paper_trade_entry_result is not None and type(
            self.paper_trade_entry_result
        ) is not PaperTradeEntryEvaluationResultV1:
            raise TypeError("paper_trade_entry_result has wrong type")
        if self.paper_trade_position_result is not None and type(
            self.paper_trade_position_result
        ) is not PaperTradePositionEvaluationResultV1:
            raise TypeError("paper_trade_position_result has wrong type")

        if self.current_portfolio_snapshot.portfolio_id != self.portfolio_id:
            raise ValueError("portfolio identity mismatch")
        if self.current_portfolio_snapshot.portfolio_snapshot_id != self.source_snapshot_id:
            raise ValueError("source_snapshot_id mismatch")
        if self.current_portfolio_snapshot.trading_day_id != self.trading_day_id:
            raise ValueError("trading day mismatch")
        if self.requested_event_sequence != self.current_portfolio_snapshot.event_sequence + 1:
            raise ValueError("requested_event_sequence must be the strict next sequence")

        if self.update_type == "ENTRY_ACTIVATION":
            if self.paper_trade_entry_result is None:
                raise ValueError("ENTRY_ACTIVATION requires paper_trade_entry_result")
            if self.paper_trade_position_result is not None:
                raise ValueError("ENTRY_ACTIVATION cannot include position result")
        elif self.update_type in {"POSITION_UPDATE", "TERMINAL_RELEASE"}:
            if self.paper_trade_position_result is None:
                raise ValueError(f"{self.update_type} requires paper_trade_position_result")
        elif self.update_type in {"PENDING_RELEASE", "DAY_ROLLOVER", "RECONCILIATION"}:
            if self.paper_trade_entry_result is not None or self.paper_trade_position_result is not None:
                raise ValueError(f"{self.update_type} does not accept P7 evaluation results")

        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only update input required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "update_idempotency_key": self.update_idempotency_key,
            "portfolio_id": self.portfolio_id,
            "source_snapshot_id": self.source_snapshot_id,
            "requested_result_snapshot_id": self.requested_result_snapshot_id,
            "requested_event_sequence": self.requested_event_sequence,
            "trading_day_id": self.trading_day_id,
            "update_type": self.update_type,
            "current_portfolio_snapshot": self.current_portfolio_snapshot.semantic_dict(),
            "paper_trade_persistence_snapshot": self.paper_trade_persistence_snapshot.to_dict(),
            "paper_trade_entry_result": (
                None if self.paper_trade_entry_result is None else self.paper_trade_entry_result.to_dict()
            ),
            "paper_trade_position_result": (
                None if self.paper_trade_position_result is None else self.paper_trade_position_result.to_dict()
            ),
            "metadata": _plain(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    @property
    def semantic_payload_hash(self) -> str:
        payload = json.dumps(
            self.semantic_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "update_request_id": self.update_request_id,
            "update_idempotency_key": self.update_idempotency_key,
            "portfolio_event_id": self.portfolio_event_id,
            "portfolio_id": self.portfolio_id,
            "source_snapshot_id": self.source_snapshot_id,
            "requested_result_snapshot_id": self.requested_result_snapshot_id,
            "requested_event_sequence": self.requested_event_sequence,
            "evaluated_at": self.evaluated_at.isoformat(),
            "trading_day_id": self.trading_day_id,
            "update_type": self.update_type,
            "current_portfolio_snapshot": self.current_portfolio_snapshot.to_dict(),
            "paper_trade_persistence_snapshot": self.paper_trade_persistence_snapshot.to_dict(),
            "paper_trade_entry_result": (
                None if self.paper_trade_entry_result is None else self.paper_trade_entry_result.to_dict()
            ),
            "paper_trade_position_result": (
                None if self.paper_trade_position_result is None else self.paper_trade_position_result.to_dict()
            ),
            "metadata": _plain(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
