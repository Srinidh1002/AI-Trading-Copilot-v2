"""Restart-safe durable store for content-addressed Task 9 config snapshots."""
from __future__ import annotations

import json
from pathlib import Path

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
from services.contracts.task9_runtime_config_snapshot_v1 import Task9RuntimeConfigSnapshotV1


class Task9RuntimeConfigSnapshotStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, snapshot_id: str) -> Path:
        if type(snapshot_id) is not str or not snapshot_id.strip() or "/" in snapshot_id or "\\" in snapshot_id:
            raise ValueError("snapshot_id")
        return self.root / "runtime-config-snapshots" / f"{snapshot_id}.json"

    def save(self, snapshot: Task9RuntimeConfigSnapshotV1) -> Task9RuntimeConfigSnapshotV1:
        if type(snapshot) is not Task9RuntimeConfigSnapshotV1:
            raise TypeError("snapshot")
        path = self._path(snapshot.snapshot_id)
        document = snapshot.to_dict()
        if path.exists():
            existing = self.get(snapshot.snapshot_id)
            if existing != snapshot:
                raise ValueError("conflicting Task 9 runtime config snapshot")
            return existing
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.tmp")
        try:
            temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False), encoding="utf-8")
            replace_task9_atomic_file(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return snapshot

    def get(self, snapshot_id: str) -> Task9RuntimeConfigSnapshotV1 | None:
        path = self._path(snapshot_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return Task9RuntimeConfigSnapshotV1.from_dict(value)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("invalid Task 9 runtime config snapshot") from exc
