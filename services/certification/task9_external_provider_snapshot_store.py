"""Durable Task 9 external-provider state store."""

from __future__ import annotations

import json
import os
from pathlib import Path

from services.contracts.task9_external_provider_state_v1 import (
    Task9ExternalProviderSnapshotV1,
)


class Task9ExternalProviderSnapshotStore:
    filename = (
        "task9-external-provider-snapshot.json"
    )

    def __init__(
        self,
        root,
    ):
        self.root = Path(root)

    @property
    def path(self):
        return (
            self.root
            / "provider-capabilities"
            / self.filename
        )

    def save(
        self,
        snapshot: Task9ExternalProviderSnapshotV1,
    ):
        if (
            type(snapshot)
            is not Task9ExternalProviderSnapshotV1
        ):
            raise TypeError("snapshot")

        payload = snapshot.to_dict()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.path.with_name(
            self.path.name + ".tmp"
        )

        try:
            with temporary.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                json.dump(
                    payload,
                    handle,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary,
                self.path,
            )

        finally:
            temporary.unlink(
                missing_ok=True
            )

        return snapshot

    def load_dict(self):
        if not self.path.exists():
            return None

        try:
            value = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "TASK9_EXTERNAL_PROVIDER_SNAPSHOT_CORRUPT"
            ) from exc

        if type(value) is not dict:
            raise ValueError(
                "TASK9_EXTERNAL_PROVIDER_SNAPSHOT_CORRUPT"
            )

        return value


__all__ = (
    "Task9ExternalProviderSnapshotStore",
)
