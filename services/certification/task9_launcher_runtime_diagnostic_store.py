"""Append-only durable authority for sanitized launcher diagnostics."""
from __future__ import annotations
import json
import os
from pathlib import Path
from services.contracts.task9_launcher_runtime_diagnostic_v1 import Task9LauncherRuntimeDiagnosticV1


class Task9LauncherRuntimeDiagnosticStore:
    def __init__(self, root): self.path = Path(root) / "launcher-runtime-diagnostics.jsonl"
    def append(self, value: Task9LauncherRuntimeDiagnosticV1):
        if type(value) is not Task9LauncherRuntimeDiagnosticV1: raise TypeError("diagnostic")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = value.to_dict(); line = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if self.path.exists():
            for existing in self.path.read_text(encoding="utf-8").splitlines():
                if existing and json.loads(existing).get("diagnostic_id") == value.diagnostic_id:
                    if json.loads(existing) != payload: raise ValueError("TASK9_LAUNCHER_DIAGNOSTIC_CONFLICT")
                    return value
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n"); handle.flush(); os.fsync(handle.fileno())
        return value
