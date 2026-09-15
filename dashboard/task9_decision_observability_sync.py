"""Read-only synchronization of Task 9 decision observability into dashboard state."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from dashboard.dashboard_read_model_state import (
    DECISION_OBSERVABILITY_STATE_KEY,
)
from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_decision_observability_projector import (
    build_task9_decision_observability,
)
from services.certification.task9_live_decision_audit import (
    Task9LiveDecisionAuditStore,
)
from services.dashboard_read_models.task9_decision_observability_view_v1 import (
    build_task9_decision_observability_dashboard_view,
)


def _clear(
    state: MutableMapping[str, object],
) -> bool:
    if DECISION_OBSERVABILITY_STATE_KEY not in state:
        return False

    state.pop(
        DECISION_OBSERVABILITY_STATE_KEY,
        None,
    )

    return True


def _latest_active_audit(
    *,
    campaign_root: str,
    active_official_run_id: str,
):
    audit_path = (
        Path(campaign_root)
        / "live-decision-audit.json"
    )

    if not audit_path.exists():
        return None

    store = Task9LiveDecisionAuditStore(
        audit_path
    )

    matches = tuple(
        audit
        for audit in store.list_all()
        if audit.official_run_id
        == active_official_run_id
    )

    if not matches:
        return None

    return max(
        matches,
        key=lambda audit: (
            audit.evaluated_at,
            audit.prediction_id,
        ),
    )


def synchronize_task9_decision_observability(
    state,
    *,
    registry_root,
) -> bool:
    """Project the latest audit for the authoritative active Task 9 run.

    This function:
    - performs no provider calls;
    - performs no broker calls;
    - writes no Task 9 certification authority;
    - creates no observability persistence;
    - mutates dashboard session state only.
    """

    if not isinstance(
        state,
        MutableMapping,
    ):
        raise TypeError(
            "state must be mutable mapping"
        )

    pointer = (
        Task9ActiveCampaignPointerStore(
            registry_root
        ).get()
    )

    if pointer is None:
        return _clear(state)

    audit = _latest_active_audit(
        campaign_root=pointer.campaign_root,
        active_official_run_id=(
            pointer.active_official_run_id
        ),
    )

    if audit is None:
        return _clear(state)

    observability = (
        build_task9_decision_observability(
            audit=audit,
        )
    )

    view = (
        build_task9_decision_observability_dashboard_view(
            observability
        )
    )

    current = state.get(
        DECISION_OBSERVABILITY_STATE_KEY
    )

    if current == view:
        return False

    state[
        DECISION_OBSERVABILITY_STATE_KEY
    ] = view

    return True


__all__ = (
    "synchronize_task9_decision_observability",
)
