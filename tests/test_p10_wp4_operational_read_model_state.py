from datetime import datetime, timezone

import pytest

from dashboard.dashboard_operational_read_model_state import (
    OPTION_INTELLIGENCE_STATE_KEY,
    RUNTIME_OPERATIONS_STATE_KEY,
    get_operational_views,
)
from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardRuntimeOperationsViewV1,
)


NOW = datetime(2026, 7, 30, 16, 0, tzinfo=timezone.utc)


def option_view():
    return DashboardOptionIntelligenceViewV1(
        source_id="option-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        status="READY",
        source_updated_at=NOW,
    )


def runtime_view():
    return DashboardRuntimeOperationsViewV1(
        source_id="runtime-1",
        runtime_status="COMPLETED",
        source_updated_at=NOW,
    )


def test_getter_returns_exact_typed_views():
    option = option_view()
    runtime = runtime_view()
    result = get_operational_views(
        {
            OPTION_INTELLIGENCE_STATE_KEY: option,
            RUNTIME_OPERATIONS_STATE_KEY: runtime,
        }
    )

    assert result == (option, runtime)


def test_getter_returns_none_for_missing_state():
    assert get_operational_views({}) == (None, None)


def test_getter_fails_closed_for_wrong_types():
    assert get_operational_views(
        {
            OPTION_INTELLIGENCE_STATE_KEY: object(),
            RUNTIME_OPERATIONS_STATE_KEY: object(),
        }
    ) == (None, None)


def test_getter_rejects_nonmapping():
    with pytest.raises(TypeError, match="mapping"):
        get_operational_views(())
