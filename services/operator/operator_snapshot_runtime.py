"""Assemble a read-only operator application snapshot runtime."""
from __future__ import annotations

from services.contracts.operator_application_snapshot_v1 import (
    OperatorApplicationSnapshotV1,
)
from services.contracts.operator_snapshot_runtime_input_v1 import (
    OperatorSnapshotRuntimeInputV1,
)
from services.operator.operator_application_snapshot_projector import (
    project_operator_application_snapshot,
)


def run_operator_snapshot_runtime(
    *,
    snapshot_id: str,
    runtime_input: OperatorSnapshotRuntimeInputV1,
) -> OperatorApplicationSnapshotV1:
    """Project one certified runtime input into a read-only snapshot."""

    if type(runtime_input) is not OperatorSnapshotRuntimeInputV1:
        raise TypeError("runtime_input")

    return project_operator_application_snapshot(
        snapshot_id=snapshot_id,
        generated_at=runtime_input.generated_at,
        nifty=runtime_input.nifty,
        sensex=runtime_input.sensex,
        recommendation=runtime_input.recommendation,
        capital=runtime_input.capital,
        active_trade=runtime_input.active_trade,
        system_health=runtime_input.system_health,
    )
