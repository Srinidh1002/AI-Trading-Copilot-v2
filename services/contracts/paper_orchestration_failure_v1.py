from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

_STAGES = frozenset({"DATA","SESSION","ANALYSIS","OPPORTUNITY","P6_PLAN","P8_ADMISSION","P7_LIFECYCLE","P8_PORTFOLIO_UPDATE","PERSISTENCE","RUNTIME"})

@dataclass(frozen=True, slots=True)
class PaperOrchestrationFailureV1:
    failure_code: str
    stage: str
    message: str
    retryable: bool
    fail_closed: bool = True
    exception_type: str | None = None
    source_component: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "paper_orchestration_failure.v1"

    def __post_init__(self):
        if self.schema_version != "paper_orchestration_failure.v1":
            raise ValueError("unsupported schema_version")
        if not isinstance(self.failure_code, str) or not self.failure_code.strip():
            raise ValueError("failure_code")
        if str(self.stage).upper() not in _STAGES:
            raise ValueError("stage")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("message")
        if type(self.retryable) is not bool or type(self.fail_closed) is not bool:
            raise TypeError("retry flags")
        if not self.fail_closed:
            raise ValueError("must fail closed")
        object.__setattr__(self, "stage", str(self.stage).upper())
        object.__setattr__(self, "failure_code", self.failure_code.strip().upper())
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self):
        return {
            "failure_code": self.failure_code,
            "stage": self.stage,
            "message": self.message,
            "retryable": self.retryable,
            "fail_closed": self.fail_closed,
            "exception_type": self.exception_type,
            "source_component": self.source_component,
            "metadata": dict(sorted(self.metadata.items())),
            "schema_version": self.schema_version,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
