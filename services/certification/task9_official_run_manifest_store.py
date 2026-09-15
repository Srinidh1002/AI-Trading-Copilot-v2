"""Durable keyed Task 9 official-run manifest authority."""
from __future__ import annotations

import json
from pathlib import Path

from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperRunManifestV1,
)


class Task9OfficialRunManifestStore:
    def __init__(
        self,
        root: str | Path,
    ) -> None:
        self.root = Path(root)

    def _path(
        self,
        official_run_id: str,
    ) -> Path:
        if (
            type(official_run_id) is not str
            or not official_run_id.strip()
            or "/" in official_run_id
            or "\\" in official_run_id
        ):
            raise ValueError("official_run_id")

        return (
            self.root
            / "official-run-manifests"
            / f"{official_run_id.strip()}.json"
        )

    @staticmethod
    def _restore(
        value: object,
    ) -> Task9LivePaperRunManifestV1:
        if type(value) is not dict:
            raise ValueError(
                "invalid Task 9 official run manifest"
            )

        try:
            from datetime import date, datetime

            return Task9LivePaperRunManifestV1(
                official_run_id=value["official_run_id"],
                official_start_at=datetime.fromisoformat(
                    value["official_start_at"]
                ),
                run_classification=value["run_classification"],
                execution_mode=value["execution_mode"],
                broker_order_submission=value[
                    "broker_order_submission"
                ],
                live_execution_eligible=value[
                    "live_execution_eligible"
                ],
                runtime_config_snapshot_id=value.get(
                    "runtime_config_snapshot_id"
                ),
                runtime_config_sha256=value.get(
                    "runtime_config_sha256"
                ),
                campaign_id=value.get("campaign_id"),
                market_date=(
                    date.fromisoformat(value["market_date"])
                    if value.get("market_date") is not None
                    else None
                ),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "invalid Task 9 official run manifest"
            ) from exc

    def get(
        self,
        official_run_id: str,
    ) -> Task9LivePaperRunManifestV1 | None:
        path = self._path(
            official_run_id
        )

        if not path.exists():
            return None

        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "invalid Task 9 official run manifest"
            ) from exc

        value = self._restore(raw)

        if (
            value.official_run_id
            != official_run_id.strip()
        ):
            raise ValueError(
                "Task 9 official run manifest identity mismatch"
            )

        return value

    read = get

    def save(
        self,
        value: Task9LivePaperRunManifestV1,
    ) -> Task9LivePaperRunManifestV1:
        if (
            type(value)
            is not Task9LivePaperRunManifestV1
        ):
            raise TypeError("value")

        path = self._path(
            value.official_run_id
        )

        current = self.get(
            value.official_run_id
        )

        if current is not None:
            if current != value:
                raise ValueError(
                    "conflicting Task 9 official run manifest"
                )

            return current

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_name(
            path.name + ".tmp"
        )

        try:
            temporary.write_text(
                json.dumps(
                    value.to_dict(),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
                encoding="utf-8",
            )

            replace_task9_atomic_file(
                temporary,
                path,
            )

        finally:
            temporary.unlink(
                missing_ok=True
            )

        durable = self.get(
            value.official_run_id
        )

        if durable != value:
            raise ValueError(
                "Task 9 official run manifest verification failed"
            )

        return durable

    persist = save


__all__ = (
    "Task9OfficialRunManifestStore",
)
