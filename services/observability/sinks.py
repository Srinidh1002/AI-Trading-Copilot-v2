from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
from typing import Protocol
from services.contracts.audit_event_v1 import AuditEventV1

class AuditSink(Protocol):
    def emit(self, event: AuditEventV1) -> None: ...

class NoOpAuditSink:
    def emit(self, event: AuditEventV1) -> None: return None

class InMemoryAuditSink:
    def __init__(self) -> None: self._events: list[AuditEventV1] = []; self._lock = Lock()
    @property
    def events(self) -> tuple[AuditEventV1, ...]:
        with self._lock: return tuple(self._events)
    def emit(self, event: AuditEventV1) -> None:
        with self._lock: self._events.append(event)
    def clear(self) -> None:
        with self._lock: self._events.clear()

class JsonLinesAuditSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        raw = str(path)
        if not raw or raw.startswith("\\\\") or "://" in raw or self.path.exists() and self.path.is_dir(): raise ValueError("Audit JSONL path is invalid.")
    def emit(self, event: AuditEventV1) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream: stream.write(event.to_json() + "\n"); stream.flush()
