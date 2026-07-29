from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)


_STAGE_ORDER = (
    "DATA",
    "SESSION",
    "ANALYSIS",
    "OPPORTUNITY",
    "P6_PLAN",
    "P8_ADMISSION",
    "P7_LIFECYCLE",
    "P8_PORTFOLIO_UPDATE",
    "PERSISTENCE",
)
_STATUSES = frozenset(
    {
        "COMPLETED",
        "COMPLETED_NO_ACTION",
        "BLOCKED",
        "FAILED",
        "DUPLICATE_NO_CHANGE",
    }
)


@dataclass(frozen=True, slots=True)
class PaperOrchestrationCycleResultV1:
    cycle_result_id: str
    cycle_id: str
    cycle_idempotency_key: str
    cycle_input_semantic_hash: str
    cycle_status: str
    terminal_stage: str
    started_at: datetime
    completed_at: datetime
    stage_results: tuple[PaperOrchestrationStageResultV1, ...]
    paper_actions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duplicate_of_cycle_result_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "paper_orchestration_cycle_result.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "paper_orchestration_cycle_result.v1":
            raise ValueError("unsupported schema_version")
        for name in (
            "cycle_result_id",
            "cycle_id",
            "cycle_idempotency_key",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")

        value = str(self.cycle_input_semantic_hash).strip().lower()
        if len(value) != 64 or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise ValueError(
                "cycle_input_semantic_hash must be a SHA-256 digest"
            )
        object.__setattr__(self, "cycle_input_semantic_hash", value)

        status = str(self.cycle_status).strip().upper()
        terminal_stage = str(self.terminal_stage).strip().upper()
        if status not in _STATUSES:
            raise ValueError("cycle_status is unsupported")
        if terminal_stage not in _STAGE_ORDER:
            raise ValueError("terminal_stage is unsupported")
        object.__setattr__(self, "cycle_status", status)
        object.__setattr__(self, "terminal_stage", terminal_stage)

        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("cycle timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")

        if not isinstance(self.stage_results, tuple):
            raise TypeError("stage_results must be a tuple")
        if not self.stage_results:
            raise ValueError("stage_results cannot be empty")

        seen: set[str] = set()
        previous_index = -1
        for stage_result in self.stage_results:
            if not isinstance(
                stage_result,
                PaperOrchestrationStageResultV1,
            ):
                raise TypeError(
                    "stage_results must contain "
                    "PaperOrchestrationStageResultV1 values"
                )
            if stage_result.cycle_id != self.cycle_id:
                raise ValueError("stage result cycle identity mismatch")
            if stage_result.stage in seen:
                raise ValueError("duplicate stage result")
            seen.add(stage_result.stage)
            current_index = _STAGE_ORDER.index(stage_result.stage)
            if current_index <= previous_index:
                raise ValueError("stage results must follow stage order")
            previous_index = current_index

        if self.stage_results[-1].stage != terminal_stage:
            raise ValueError(
                "terminal_stage must match the final stage result"
            )

        if status == "FAILED" and not any(
            item.status == "FAILED" for item in self.stage_results
        ):
            raise ValueError("FAILED cycle requires a failed stage")
        if status == "BLOCKED" and not any(
            item.status == "BLOCKED" for item in self.stage_results
        ):
            raise ValueError("BLOCKED cycle requires a blocked stage")
        if status == "DUPLICATE_NO_CHANGE":
            if self.duplicate_of_cycle_result_id is None:
                raise ValueError(
                    "duplicate cycle result identity is required"
                )
            if any(self.paper_actions):
                raise ValueError(
                    "duplicate no-change cycle cannot contain PAPER actions"
                )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("P9 is not eligible for live execution")

        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_result_id": self.cycle_result_id,
            "cycle_id": self.cycle_id,
            "cycle_idempotency_key": self.cycle_idempotency_key,
            "cycle_input_semantic_hash": self.cycle_input_semantic_hash,
            "cycle_status": self.cycle_status,
            "terminal_stage": self.terminal_stage,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "stage_results": [
                item.to_dict() for item in self.stage_results
            ],
            "paper_actions": list(self.paper_actions),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "duplicate_of_cycle_result_id": (
                self.duplicate_of_cycle_result_id
            ),
            "metadata": dict(sorted(self.metadata.items())),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("cycle_result_id")
        result.pop("started_at")
        result.pop("completed_at")
        for stage in result["stage_results"]:
            stage.pop("stage_result_id")
            stage.pop("started_at")
            stage.pop("completed_at")
        return result

    def semantic_hash(self) -> str:
        payload = json.dumps(
            self.semantic_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
