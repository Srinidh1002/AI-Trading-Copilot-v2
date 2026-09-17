"""Durable stores for Task 9 collector observability."""

from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts.task9_collector_observability_v1 import (
    Task9CollectorEventV1,
    Task9CollectorRunSummaryV1,
)


def _atomic_json(
    path: Path,
    value: object,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    try:
        with temporary.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            json.dump(
                value,
                handle,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )

            handle.flush()
            os.fsync(
                handle.fileno()
            )

        os.replace(
            temporary,
            path,
        )

    finally:
        temporary.unlink(
            missing_ok=True
        )


class Task9CollectorObservabilityStore:
    def __init__(
        self,
        root,
    ):
        self.root = Path(root)

    def _events_path(
        self,
        collector_run_id: str,
    ):
        return (
            self.root
            / "collector-observability"
            / collector_run_id
            / "events.jsonl"
        )

    def _summary_path(
        self,
        collector_run_id: str,
    ):
        return (
            self.root
            / "collector-observability"
            / collector_run_id
            / "summary.json"
        )

    def append_event(
        self,
        event: Task9CollectorEventV1,
    ):
        if (
            type(event)
            is not Task9CollectorEventV1
        ):
            raise TypeError("event")

        path = self._events_path(
            event.collector_run_id
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        serialized = json.dumps(
            event.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        with path.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(
                serialized + "\n"
            )

            handle.flush()
            os.fsync(
                handle.fileno()
            )

        return event

    def save_summary(
        self,
        summary: Task9CollectorRunSummaryV1,
    ):
        if (
            type(summary)
            is not Task9CollectorRunSummaryV1
        ):
            raise TypeError("summary")

        path = self._summary_path(
            summary.collector_run_id
        )

        payload = summary.to_dict()

        if path.exists():
            existing = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if existing != payload:
                raise ValueError(
                    "TASK9_COLLECTOR_SUMMARY_CONFLICT"
                )

            return summary

        _atomic_json(
            path,
            payload,
        )

        return summary


__all__ = (
    "Task9CollectorObservabilityStore",
)
