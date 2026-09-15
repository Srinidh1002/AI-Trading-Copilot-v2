"""Read-only adapter for durable Task 9 dashboard authorities."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerError,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)
from services.dashboard_publication.task9_dashboard_active_campaign_projection_store import (
    Task9DashboardActiveCampaignProjectionStore,
)

from .dashboard_application_view_v1 import DashboardApplicationViewV1
from .task9_external_provider_blocker_view import (
    read_task9_external_provider_blocker,
)


_MARKET_PROGRESS_BASE_FIELDS = {
    "market",
    "target_trade_count",
    "completed_live_paper_trades",
    "pending_entered_trades",
    "no_trade_completed",
    "no_trade_passed",
    "no_trade_failed",
    "target_reached",
    "remaining_trade_count",
}

_MARKET_PROGRESS_WAIT_FIELDS = {
    "wait_completed",
    "wait_passed",
    "wait_failed",
}


def _read_task9_official_run_id(persistence_root) -> str | None:
    """Read the existing run manifest without creating or changing it."""

    # Keep this read-only adapter aligned with the launcher manifest contract.
    path = Path(persistence_root) / "task9-live-paper-run.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if type(raw) is not dict or set(raw) != {
            "official_run_id",
            "official_start_at",
            "execution_mode",
            "broker_order_submission",
            "live_execution_eligible",
        }:
            return None
        official_run_id = raw["official_run_id"]
        official_start_at = datetime.fromisoformat(raw["official_start_at"])
        if (
            type(official_run_id) is not str
            or not official_run_id.strip()
            or official_start_at.tzinfo is None
            or official_start_at.utcoffset() is None
            or raw["execution_mode"] != "PAPER"
            or raw["broker_order_submission"] is not False
            or raw["live_execution_eligible"] is not False
        ):
            return None
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return official_run_id.strip()


def _read_current_task9_progress(root):
    """Read current mutable progress authority without mutating durable state."""

    path = (
        Path(root)
        / "task9-live-paper-certification-progress.json"
    )

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if (
            type(raw) is not dict
            or set(raw)
            != {
                "nifty",
                "sensex",
                "replay_excluded",
                "duplicate_excluded",
                "invalid_excluded",
                "unresolved",
                "certification_complete",
                "execution_mode",
                "live_execution_eligible",
                "broker_order_submission",
                "read_only",
                "schema_version",
            }
        ):
            return None

        def market(name):
            value = raw[name]

            if type(value) is not dict:
                raise ValueError(
                    "Task9 market progress"
                )

            fields = set(value)

            legacy_fields = (
                _MARKET_PROGRESS_BASE_FIELDS
            )

            current_fields = (
                _MARKET_PROGRESS_BASE_FIELDS
                | _MARKET_PROGRESS_WAIT_FIELDS
            )

            if fields == legacy_fields:
                wait_completed = 0
                wait_passed = 0
                wait_failed = 0
            elif fields == current_fields:
                wait_completed = value[
                    "wait_completed"
                ]
                wait_passed = value[
                    "wait_passed"
                ]
                wait_failed = value[
                    "wait_failed"
                ]
            else:
                raise ValueError(
                    "Task9 market progress"
                )

            result = Task9MarketProgressV1(
                market=value["market"],
                target_trade_count=(
                    value[
                        "target_trade_count"
                    ]
                ),
                completed_live_paper_trades=(
                    value[
                        "completed_live_paper_trades"
                    ]
                ),
                pending_entered_trades=(
                    value[
                        "pending_entered_trades"
                    ]
                ),
                no_trade_completed=(
                    value[
                        "no_trade_completed"
                    ]
                ),
                no_trade_passed=(
                    value[
                        "no_trade_passed"
                    ]
                ),
                no_trade_failed=(
                    value[
                        "no_trade_failed"
                    ]
                ),
                wait_completed=wait_completed,
                wait_passed=wait_passed,
                wait_failed=wait_failed,
            )

            if (
                value["target_reached"]
                is not result.target_reached
                or value[
                    "remaining_trade_count"
                ]
                != result.remaining_trade_count
            ):
                raise ValueError(
                    "Task9 derived progress"
                )

            return result

        return (
            Task9LivePaperCertificationProgressV1(
                nifty=market("nifty"),
                sensex=market("sensex"),
                replay_excluded=(
                    raw["replay_excluded"]
                ),
                duplicate_excluded=(
                    raw["duplicate_excluded"]
                ),
                invalid_excluded=(
                    raw["invalid_excluded"]
                ),
                unresolved=raw["unresolved"],
                certification_complete=(
                    raw[
                        "certification_complete"
                    ]
                ),
                execution_mode=(
                    raw["execution_mode"]
                ),
                live_execution_eligible=(
                    raw[
                        "live_execution_eligible"
                    ]
                ),
                broker_order_submission=(
                    raw[
                        "broker_order_submission"
                    ]
                ),
                read_only=raw["read_only"],
                schema_version=(
                    raw["schema_version"]
                ),
            )
        )

    except (
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def _active_campaign_matches_official_run(
    root: Path,
    *,
    official_run_id: str,
) -> bool:
    """Require durable active-campaign identity before exposing Task 9 progress."""

    try:
        projection = (
            Task9DashboardActiveCampaignProjectionStore(
                root
            ).get()
        )
    except (OSError, TypeError, ValueError):
        return False

    if projection is None:
        return False

    return (
        projection.active_official_run_id
        == official_run_id
    )


def recover_task9_durable_authorities(
    view: DashboardApplicationViewV1,
    *,
    persistence_root,
) -> DashboardApplicationViewV1:
    """Fill omitted dashboard projections from validated durable authority."""

    if type(view) is not DashboardApplicationViewV1:
        raise TypeError("view")

    root = Path(persistence_root)
    official_run_id = _read_task9_official_run_id(root)

    if official_run_id is None:
        return view

    campaign_matches = (
        _active_campaign_matches_official_run(
            root,
            official_run_id=official_run_id,
        )
    )

    progress = (
        view.task9_certification_progress
        if campaign_matches
        else None
    )

    if (
        campaign_matches
        and progress is None
    ):
        progress = _read_current_task9_progress(
            root
        )

    blocker = (
        view.external_provider_blocker
    )

    if blocker is None:
        try:
            blocker = (
                read_task9_external_provider_blocker(
                    persistence_root=root,
                    official_run_id=(
                        official_run_id
                    ),
                )
            )

        except (
            OSError,
            TypeError,
            ValueError,
            Task9ExternalProviderBlockerError,
        ):
            blocker = None

    if (
        progress
        is view.task9_certification_progress
        and blocker
        is view.external_provider_blocker
    ):
        return view

    return replace(
        view,
        task9_certification_progress=progress,
        external_provider_blocker=blocker,
    )
