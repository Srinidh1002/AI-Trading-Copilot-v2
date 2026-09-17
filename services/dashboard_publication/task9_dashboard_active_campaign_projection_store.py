"""Durable Task 9 dashboard active-campaign projection store."""
from __future__ import annotations

import json
import os
from pathlib import Path

from services.certification.task9_atomic_file_replace import (
    replace_task9_atomic_file,
)
from services.contracts.task9_dashboard_active_campaign_projection_v1 import (
    Task9DashboardActiveCampaignProjectionV1,
)


_FILENAME = (
    "task9-dashboard-active-campaign.json"
)


class Task9DashboardActiveCampaignProjectionStore:
    def __init__(
        self,
        persistence_root,
    ) -> None:
        self.root = Path(
            persistence_root
        )

        self.path = (
            self.root
            / _FILENAME
        )

    def get(
        self,
    ) -> Task9DashboardActiveCampaignProjectionV1 | None:
        if not self.path.exists():
            return None

        try:
            raw = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            return (
                Task9DashboardActiveCampaignProjectionV1.from_dict(
                    raw
                )
            )

        except (
            OSError,
            ValueError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "invalid Task 9 dashboard active campaign projection"
            ) from exc

    def save(
        self,
        value: Task9DashboardActiveCampaignProjectionV1,
    ) -> Task9DashboardActiveCampaignProjectionV1:
        if (
            type(value)
            is not Task9DashboardActiveCampaignProjectionV1
        ):
            raise TypeError("value")

        current = self.get()

        if current is not None:
            current_identity = (
                current.campaign_id,
                current.active_market_date,
                current.active_official_run_id,
                current.runtime_config_snapshot_id,
                current.runtime_config_sha256,
            )

            next_identity = (
                value.campaign_id,
                value.active_market_date,
                value.active_official_run_id,
                value.runtime_config_snapshot_id,
                value.runtime_config_sha256,
            )

            if current_identity == next_identity:
                return current

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
                    value.to_dict(),
                    handle,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )

                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            replace_task9_atomic_file(
                temporary,
                self.path,
            )

        finally:
            temporary.unlink(
                missing_ok=True
            )

        return value


__all__ = (
    "Task9DashboardActiveCampaignProjectionStore",
)
