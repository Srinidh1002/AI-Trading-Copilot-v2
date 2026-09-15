"""Task 9 dashboard active-campaign projection.

This is a read-only projection of canonical Task 9 campaign authority.
It is never allowed to originate or mutate campaign identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Task9DashboardActiveCampaignProjectionV1:
    campaign_id: str
    active_market_date: date
    active_official_run_id: str
    runtime_config_snapshot_id: str
    runtime_config_sha256: str
    projected_at: datetime

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_dashboard_active_campaign_projection.v1"
    )

    def __post_init__(self) -> None:
        for name in (
            "campaign_id",
            "active_official_run_id",
            "runtime_config_snapshot_id",
            "runtime_config_sha256",
        ):
            value = getattr(self, name)

            if (
                type(value) is not str
                or not value.strip()
            ):
                raise ValueError(name)

        if type(self.active_market_date) is not date:
            raise TypeError(
                "active_market_date"
            )

        if (
            not isinstance(
                self.projected_at,
                datetime,
            )
            or self.projected_at.tzinfo is None
            or self.projected_at.utcoffset() is None
        ):
            raise ValueError(
                "projected_at"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 dashboard campaign projection must remain PAPER-only"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "campaign_id": self.campaign_id,
            "active_market_date": (
                self.active_market_date.isoformat()
            ),
            "active_official_run_id": (
                self.active_official_run_id
            ),
            "runtime_config_snapshot_id": (
                self.runtime_config_snapshot_id
            ),
            "runtime_config_sha256": (
                self.runtime_config_sha256
            ),
            "projected_at": (
                self.projected_at.isoformat()
            ),
            "execution_mode": (
                self.execution_mode
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }

    @classmethod
    def from_dict(
        cls,
        value: object,
    ) -> "Task9DashboardActiveCampaignProjectionV1":
        if type(value) is not dict:
            raise ValueError(
                "dashboard active campaign projection"
            )

        expected = {
            "schema_version",
            "campaign_id",
            "active_market_date",
            "active_official_run_id",
            "runtime_config_snapshot_id",
            "runtime_config_sha256",
            "projected_at",
            "execution_mode",
            "broker_order_submission",
            "live_execution_eligible",
        }

        if set(value) != expected:
            raise ValueError(
                "dashboard active campaign projection fields"
            )

        if (
            value["schema_version"]
            != "task9_dashboard_active_campaign_projection.v1"
        ):
            raise ValueError(
                "dashboard active campaign projection schema"
            )

        return cls(
            campaign_id=value["campaign_id"],
            active_market_date=date.fromisoformat(
                value["active_market_date"]
            ),
            active_official_run_id=(
                value["active_official_run_id"]
            ),
            runtime_config_snapshot_id=(
                value["runtime_config_snapshot_id"]
            ),
            runtime_config_sha256=(
                value["runtime_config_sha256"]
            ),
            projected_at=datetime.fromisoformat(
                value["projected_at"]
            ),
            execution_mode=value["execution_mode"],
            broker_order_submission=(
                value["broker_order_submission"]
            ),
            live_execution_eligible=(
                value["live_execution_eligible"]
            ),
        )


__all__ = (
    "Task9DashboardActiveCampaignProjectionV1",
)
