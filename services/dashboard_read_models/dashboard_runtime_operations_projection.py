from __future__ import annotations

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)

from .dashboard_runtime_operations_view_v1 import (
    DashboardComponentHealthViewV1,
    DashboardRuntimeOperationsViewV1,
)


def project_runtime_operations(
    source: PaperOrchestrationCycleResultV1,
) -> DashboardRuntimeOperationsViewV1:
    """Project completed-cycle observations without executing checks."""

    if type(source) is not PaperOrchestrationCycleResultV1:
        raise TypeError(
            "source must be exact PaperOrchestrationCycleResultV1"
        )

    duration = (source.completed_at - source.started_at).total_seconds()
    components = tuple(
        DashboardComponentHealthViewV1(
            component=stage.stage,
            status=stage.status,
            detail=(
                "; ".join(stage.errors)
                if stage.errors
                else None
            ),
        )
        for stage in source.stage_results
    )

    failed = source.cycle_status == "FAILED"
    return DashboardRuntimeOperationsViewV1(
        source_id=source.cycle_result_id,
        runtime_status=source.cycle_status,
        source_updated_at=source.completed_at,
        last_successful_cycle_at=(
            None if failed else source.completed_at
        ),
        last_failed_attempt_at=(
            source.completed_at if failed else None
        ),
        last_failed_attempt_error=(
            "; ".join(source.errors)
            if failed and source.errors
            else None
        ),
        market_cycle_duration_seconds=duration,
        decision_cycle_duration_seconds=None,
        freshness_status="FRESH",
        components=components,
        warnings=source.warnings,
    )
