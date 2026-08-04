from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping
from services.contracts.paper_orchestration_failure_v1 import PaperOrchestrationFailureV1

_STAGES=frozenset({"DATA","SESSION","ANALYSIS","OPPORTUNITY","P6_PLAN","P8_ADMISSION","P7_LIFECYCLE","P8_PORTFOLIO_UPDATE","PERSISTENCE"})
_STATUSES=frozenset({"NOT_RUN","COMPLETED","NO_ACTION","BLOCKED","FAILED","DUPLICATE_NO_CHANGE"})

@dataclass(frozen=True, slots=True)
class PaperOrchestrationStageResultV1:
    stage_result_id: str
    cycle_id: str
    stage: str
    status: str
    started_at: datetime
    completed_at: datetime
    source_result_type: str | None = None
    source_result_id: str | None = None
    source_semantic_hash: str | None = None
    paper_action_occurred: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    failure: PaperOrchestrationFailureV1 | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "paper_orchestration_stage_result.v1"

    def __post_init__(self):
        if self.schema_version != "paper_orchestration_stage_result.v1":
            raise ValueError("unsupported schema_version")
        if not self.stage_result_id or not self.cycle_id:
            raise ValueError("identity")
        stage, status = str(self.stage).upper(), str(self.status).upper()
        if stage not in _STAGES or status not in _STATUSES:
            raise ValueError("stage/status")
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("timestamps")
        if self.completed_at < self.started_at:
            raise ValueError("time order")
        if self.failure is not None and (status != "FAILED" or self.failure.stage != stage):
            raise ValueError("failure mismatch")
        if status == "FAILED" and self.failure is None:
            raise ValueError("failure required")
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self):
        return {
            "stage_result_id": self.stage_result_id,
            "cycle_id": self.cycle_id,
            "stage": self.stage,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "source_result_type": self.source_result_type,
            "source_result_id": self.source_result_id,
            "source_semantic_hash": self.source_semantic_hash,
            "paper_action_occurred": self.paper_action_occurred,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "failure": self.failure.to_dict() if self.failure else None,
            "metadata": dict(sorted(self.metadata.items())),
            "schema_version": self.schema_version,
        }

    def semantic_hash(self):
        value=self.to_dict()
        value.pop("stage_result_id"); value.pop("started_at"); value.pop("completed_at")
        payload=json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
