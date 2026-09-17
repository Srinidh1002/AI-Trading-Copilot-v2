"""Durable audit for a Task 9 parent cycle rejected before trusted handoff."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file


_REASON = "STALE_PARENT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class Task9SkippedParentEvidenceCycleV1:
    official_run_id: str
    observed_at: datetime
    retained_provider_incident_ids: tuple[str, ...] = ()
    reason_code: str = _REASON
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if type(self.official_run_id) is not str or not self.official_run_id.strip():
            raise ValueError("official_run_id")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None:
            raise ValueError("observed_at")
        if self.reason_code != _REASON:
            raise ValueError("reason_code")
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("Task 9 skipped parent evidence must remain PAPER-only")
        if (
            type(self.retained_provider_incident_ids) is not tuple
            or any(
                type(item) is not str
                or not item.startswith("task9-provider-incident:")
                for item in self.retained_provider_incident_ids
            )
        ):
            raise ValueError("retained_provider_incident_ids")

    def to_dict(self) -> dict[str, object]:
        return {
            "official_run_id": self.official_run_id,
            "observed_at": self.observed_at.isoformat(),
            "reason_code": self.reason_code,
            "retained_provider_incident_ids": list(self.retained_provider_incident_ids),
            "execution_mode": self.execution_mode,
            "broker_order_submission": self.broker_order_submission,
            "live_execution_eligible": self.live_execution_eligible,
        }


class Task9SkippedParentEvidenceCycleStore:
    """Append-only, idempotent non-counting audit records."""

    def __init__(self, persistence_root: str | Path) -> None:
        self.root = Path(persistence_root) / "task9-skipped-parent-evidence-cycles"

    def save(self, value: Task9SkippedParentEvidenceCycleV1) -> None:
        if type(value) is not Task9SkippedParentEvidenceCycleV1:
            raise TypeError("value")
        document = value.to_dict()
        identity = ":".join((value.official_run_id, value.observed_at.isoformat(), value.reason_code))
        path = self.root / f"{hashlib.sha256(identity.encode('utf-8')).hexdigest()}.json"
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("invalid skipped parent evidence cycle") from exc
            if existing != document:
                raise ValueError("conflicting skipped parent evidence cycle")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False),
                encoding="utf-8",
            )
            replace_task9_atomic_file(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


__all__ = (
    "Task9SkippedParentEvidenceCycleStore",
    "Task9SkippedParentEvidenceCycleV1",
)
