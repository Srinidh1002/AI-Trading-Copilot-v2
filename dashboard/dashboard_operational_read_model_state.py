from __future__ import annotations

from collections.abc import Mapping

from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)


OPTION_INTELLIGENCE_STATE_KEY = (
    "dashboard_option_intelligence_view_v1"
)
RUNTIME_OPERATIONS_STATE_KEY = (
    "dashboard_runtime_operations_view_v1"
)


def _exact_or_none(
    state: Mapping[str, object],
    key: str,
    expected_type: type,
):
    value = state.get(key)
    if value is None:
        return None
    if type(value) is not expected_type:
        return None
    return value


def get_operational_views(
    state: Mapping[str, object],
) -> tuple[
    DashboardOptionIntelligenceViewV1 | None,
    DashboardRuntimeOperationsViewV1 | None,
]:
    if not isinstance(state, Mapping):
        raise TypeError("state must be a mapping")

    return (
        _exact_or_none(
            state,
            OPTION_INTELLIGENCE_STATE_KEY,
            DashboardOptionIntelligenceViewV1,
        ),
        _exact_or_none(
            state,
            RUNTIME_OPERATIONS_STATE_KEY,
            DashboardRuntimeOperationsViewV1,
        ),
    )
