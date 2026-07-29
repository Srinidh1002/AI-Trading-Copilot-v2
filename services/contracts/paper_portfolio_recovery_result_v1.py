"""Immutable public recovery result for P8 portfolio state."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .paper_portfolio_persistence_snapshot_v1 import PaperPortfolioPersistenceSnapshotV1

_STATUSES = frozenset({"RECOVERED", "BLOCKED", "CORRUPT"})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
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


@dataclass(frozen=True, slots=True)
class PaperPortfolioRecoveryResultV1:
    portfolio_id: str
    status: str
    recovered_at: datetime
    persistence_snapshot: PaperPortfolioPersistenceSnapshotV1 | None = None
    reconciliation_codes: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "portfolio_id", _text(self.portfolio_id, "portfolio_id"))
        if self.status not in _STATUSES:
            raise ValueError("unsupported recovery status")
        object.__setattr__(self, "recovered_at", _aware(self.recovered_at, "recovered_at"))
        if self.persistence_snapshot is not None and type(
            self.persistence_snapshot
        ) is not PaperPortfolioPersistenceSnapshotV1:
            raise TypeError("persistence_snapshot has wrong type")
        for name in ("reconciliation_codes", "blockers", "warnings"):
            object.__setattr__(self, name, _diagnostics(getattr(self, name), name))

        if self.status == "RECOVERED":
            if self.persistence_snapshot is None or self.blockers:
                raise ValueError("RECOVERED requires snapshot and no blockers")
            if self.persistence_snapshot.portfolio_id != self.portfolio_id:
                raise ValueError("recovered portfolio identity mismatch")
        elif self.status == "BLOCKED":
            if not self.blockers:
                raise ValueError("BLOCKED requires blockers")
        else:
            if self.persistence_snapshot is not None:
                raise ValueError("CORRUPT must not expose an admissible snapshot")
            if not self.blockers and not self.reconciliation_codes:
                raise ValueError("CORRUPT requires diagnostic evidence")

        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only recovery result required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "status": self.status,
            "recovered_at": self.recovered_at.isoformat(),
            "persistence_snapshot": (
                None if self.persistence_snapshot is None else self.persistence_snapshot.to_dict()
            ),
            "reconciliation_codes": list(self.reconciliation_codes),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
