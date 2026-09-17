from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_projection import (
    project_runtime_operations,
)


NOW = datetime(2026, 7, 30, 14, 30, tzinfo=timezone.utc)


def cycle(status="COMPLETED", errors=()):
    source = object.__new__(PaperOrchestrationCycleResultV1)
    stage = SimpleNamespace(
        stage="DATA",
        status="COMPLETED",
        errors=(),
    )
    values = {
        "cycle_result_id": "cycle-result-1",
        "cycle_status": status,
        "started_at": NOW,
        "completed_at": NOW + timedelta(seconds=2.5),
        "stage_results": (stage,),
        "warnings": ("SLOW_SOURCE",),
        "errors": errors,
    }
    for name, value in values.items():
        object.__setattr__(source, name, value)
    return source


def test_completed_cycle_projects_observations():
    result = project_runtime_operations(cycle())

    assert result.runtime_status == "COMPLETED"
    assert result.market_cycle_duration_seconds == 2.5
    assert result.last_successful_cycle_at == NOW + timedelta(seconds=2.5)
    assert result.last_failed_attempt_at is None
    assert result.components[0].component == "DATA"


def test_failed_cycle_projects_failure_without_running_check():
    result = project_runtime_operations(
        cycle(status="FAILED", errors=("DATA_FAILURE",))
    )

    assert result.last_successful_cycle_at is None
    assert result.last_failed_attempt_at == NOW + timedelta(seconds=2.5)
    assert result.last_failed_attempt_error == "DATA_FAILURE"


def test_projection_rejects_untyped_source():
    with pytest.raises(TypeError, match="exact"):
        project_runtime_operations(SimpleNamespace())
