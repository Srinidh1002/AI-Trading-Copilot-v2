from __future__ import annotations

from collections.abc import MutableMapping

from services.dashboard_publication import (
    DashboardPublicationSnapshotV1,
)
from services.dashboard_publication.dashboard_publication_registry import (
    get_registered_dashboard_publication_snapshot,
)

from .dashboard_read_model_state import (
    OPPORTUNITY_STATE_KEY,
    PAPER_POSITION_STATE_KEY,
    TRADE_PLAN_STATE_KEY,
)


PUBLICATION_ID_STATE_KEY = "dashboard_publication_id"
PUBLICATION_SEQUENCE_STATE_KEY = "dashboard_publication_sequence"
PUBLICATION_STATUS_STATE_KEY = "dashboard_publication_status"
PUBLICATION_FRESHNESS_STATE_KEY = "dashboard_publication_freshness"
PUBLICATION_PUBLISHED_AT_STATE_KEY = "dashboard_publication_published_at"
PUBLICATION_SOURCE_UPDATED_AT_STATE_KEY = (
    "dashboard_publication_source_updated_at"
)
PUBLICATION_ATTEMPT_STATUS_STATE_KEY = (
    "dashboard_publication_attempt_status"
)
PUBLICATION_ATTEMPT_ERROR_STATE_KEY = (
    "dashboard_publication_attempt_error"
)
PUBLICATION_FAILED_ATTEMPT_COUNT_STATE_KEY = (
    "dashboard_publication_failed_attempt_count"
)


def synchronize_dashboard_publication(
    state: MutableMapping[str, object],
    snapshot: DashboardPublicationSnapshotV1,
) -> bool:
    """Copy the latest immutable publication into dashboard session state.

    Returns True only when a newer publication sequence is applied.
    Failed or empty snapshots never clear existing read models.
    """

    if not isinstance(state, MutableMapping):
        raise TypeError("state must be a mutable mapping")
    if type(snapshot) is not DashboardPublicationSnapshotV1:
        raise TypeError(
            "snapshot must be exact DashboardPublicationSnapshotV1"
        )

    state[PUBLICATION_ATTEMPT_STATUS_STATE_KEY] = (
        snapshot.last_attempt_status
    )
    state[PUBLICATION_ATTEMPT_ERROR_STATE_KEY] = (
        snapshot.last_attempt_error
    )
    state[PUBLICATION_FAILED_ATTEMPT_COUNT_STATE_KEY] = (
        snapshot.failed_attempt_count
    )

    envelope = snapshot.latest_envelope
    if envelope is None:
        return False

    current_sequence = state.get(PUBLICATION_SEQUENCE_STATE_KEY)
    if current_sequence is not None:
        if (
            type(current_sequence) is not int
            or isinstance(current_sequence, bool)
        ):
            raise TypeError(
                "dashboard publication sequence state must be an exact int"
            )
        if envelope.publication_sequence <= current_sequence:
            return False

    state[OPPORTUNITY_STATE_KEY] = envelope.opportunity
    state[TRADE_PLAN_STATE_KEY] = envelope.trade_plan
    state[PAPER_POSITION_STATE_KEY] = envelope.paper_position

    state[PUBLICATION_ID_STATE_KEY] = envelope.publication_id
    state[PUBLICATION_SEQUENCE_STATE_KEY] = envelope.publication_sequence
    state[PUBLICATION_STATUS_STATE_KEY] = envelope.publication_status
    state[PUBLICATION_FRESHNESS_STATE_KEY] = envelope.freshness_status
    state[PUBLICATION_PUBLISHED_AT_STATE_KEY] = envelope.published_at
    state[PUBLICATION_SOURCE_UPDATED_AT_STATE_KEY] = (
        envelope.source_updated_at
    )

    return True



def synchronize_registered_dashboard_publication(
    state: MutableMapping[str, object],
) -> bool:
    """Synchronize from the process-local registered publication store."""

    snapshot = get_registered_dashboard_publication_snapshot()
    if snapshot is None:
        return False
    return synchronize_dashboard_publication(state, snapshot)
