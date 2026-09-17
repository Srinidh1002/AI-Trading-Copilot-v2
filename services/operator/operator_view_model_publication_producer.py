"""Produce and publish the certified operator dashboard view model."""
from __future__ import annotations

from collections.abc import MutableMapping

from dashboard.dashboard_publication_sync import (
    synchronize_operator_view_model_publication,
)
from services.contracts.operator_application_view_model_v1 import (
    OperatorApplicationViewModelV1,
)
from services.contracts.operator_snapshot_runtime_input_v1 import (
    OperatorSnapshotRuntimeInputV1,
)
from services.operator.operator_application_view_model_projector import (
    project_operator_application_view_model,
)
from services.operator.operator_snapshot_runtime import (
    run_operator_snapshot_runtime,
)


def produce_and_publish_operator_view_model(
    *,
    publication_sequence: int,
    snapshot_id: str,
    view_model_id: str,
    runtime_input: OperatorSnapshotRuntimeInputV1,
    dashboard_state: MutableMapping[str, object],
) -> OperatorApplicationViewModelV1:
    """Run the certified operator pipeline and publish the resulting view."""

    if type(runtime_input) is not OperatorSnapshotRuntimeInputV1:
        raise TypeError("runtime_input")
    if not isinstance(dashboard_state, MutableMapping):
        raise TypeError("dashboard_state")

    snapshot = run_operator_snapshot_runtime(
        snapshot_id=snapshot_id,
        runtime_input=runtime_input,
    )
    view_model = project_operator_application_view_model(
        view_model_id=view_model_id,
        snapshot=snapshot,
    )

    synchronize_operator_view_model_publication(
        dashboard_state,
        publication_sequence=publication_sequence,
        view_model=view_model,
    )
    return view_model
