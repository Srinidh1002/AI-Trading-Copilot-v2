"""Atomic JSON-backed repository for active PAPER positions."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)


class JsonPaperPositionRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def list_all(self) -> tuple[ActivePaperPositionV1, ...]:
        values = self._read_raw()
        return tuple(
            self._decode(item)
            for item in sorted(
                values,
                key=lambda item: item["position_id"],
            )
        )

    def list_active(self) -> tuple[ActivePaperPositionV1, ...]:
        return tuple(
            item
            for item in self.list_all()
            if item.lifecycle_state
            in {"OPEN", "PARTIALLY_EXITED"}
        )

    def get(
        self,
        position_id: str,
    ) -> ActivePaperPositionV1 | None:
        for item in self.list_all():
            if item.position_id == position_id:
                return item
        return None

    def save(
        self,
        position: ActivePaperPositionV1,
    ) -> None:
        if type(position) is not ActivePaperPositionV1:
            raise TypeError("position")

        positions = {
            item.position_id: item
            for item in self.list_all()
        }

        for existing in positions.values():
            if (
                existing.position_id != position.position_id
                and existing.lifecycle_state
                in {"OPEN", "PARTIALLY_EXITED"}
                and position.lifecycle_state
                in {"OPEN", "PARTIALLY_EXITED"}
                and (
                    existing.recommendation_id
                    == position.recommendation_id
                    or existing.contract == position.contract
                )
            ):
                raise ValueError(
                    "duplicate active recommendation or contract"
                )

        current = positions.get(position.position_id)
        if (
            current is not None
            and position.updated_at < current.updated_at
        ):
            raise ValueError("stale position update")
        positions[position.position_id] = position
        self._write_atomic(
            tuple(
                positions[key]
                for key in sorted(positions)
            )
        )

    def _read_raw(self) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        try:
            value = json.loads(
                self._path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                "invalid PAPER position repository"
            ) from exc
        if not isinstance(value, list):
            raise ValueError(
                "invalid PAPER position repository"
            )
        return value

    def _write_atomic(
        self,
        positions: tuple[ActivePaperPositionV1, ...],
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(
            self._path.suffix + ".tmp"
        )
        payload = [
            self._encode(item)
            for item in positions
        ]
        temp.write_text(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        os.replace(temp, self._path)

    @staticmethod
    def _encode(
        position: ActivePaperPositionV1,
    ) -> dict[str, object]:
        value = asdict(position)
        value["opened_at"] = position.opened_at.isoformat()
        value["updated_at"] = position.updated_at.isoformat()
        value["processed_event_ids"] = list(
            position.processed_event_ids
        )
        value["warnings"] = list(position.warnings)
        return value

    @staticmethod
    def _decode(
        value: dict[str, object],
    ) -> ActivePaperPositionV1:
        if not isinstance(value, dict):
            raise ValueError("invalid stored position")
        decoded = dict(value)
        decoded.pop("SCHEMA_VERSION", None)
        decoded["opened_at"] = datetime.fromisoformat(
            str(decoded["opened_at"])
        )
        decoded["updated_at"] = datetime.fromisoformat(
            str(decoded["updated_at"])
        )
        decoded["processed_event_ids"] = tuple(
            decoded.get("processed_event_ids", ())
        )
        decoded["warnings"] = tuple(
            decoded.get("warnings", ())
        )
        return ActivePaperPositionV1(**decoded)
