from datetime import datetime, timezone

from dashboard.operational_components import (
    render_option_intelligence,
    render_runtime_operations,
)
from services.dashboard_read_models.dashboard_option_intelligence_view_v1 import (
    DashboardOptionIntelligenceViewV1,
)
from services.dashboard_read_models.dashboard_runtime_operations_view_v1 import (
    DashboardComponentHealthViewV1,
    DashboardRuntimeOperationsViewV1,
)


NOW = datetime(2026, 7, 30, 16, 30, tzinfo=timezone.utc)


class FakeColumn:
    def __init__(self, calls):
        self.calls = calls

    def metric(self, label, value):
        self.calls.append(("metric", label, value))


class FakeExpander:
    def __init__(self, st):
        self.st = st

    def __enter__(self):
        return self.st

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeStreamlit:
    def __init__(self):
        self.calls = []

    def subheader(self, value):
        self.calls.append(("subheader", value))

    def info(self, value):
        self.calls.append(("info", value))

    def warning(self, value):
        self.calls.append(("warning", value))

    def error(self, value):
        self.calls.append(("error", value))

    def caption(self, value):
        self.calls.append(("caption", value))

    def columns(self, count):
        return tuple(FakeColumn(self.calls) for _ in range(count))

    def expander(self, value):
        self.calls.append(("expander", value))
        return FakeExpander(self)

    def write(self, value):
        self.calls.append(("write", value))

    def dataframe(self, value, **kwargs):
        self.calls.append(("dataframe", value, kwargs))


def test_option_renderer_has_explicit_no_data_state():
    st = FakeStreamlit()

    render_option_intelligence(st, None)

    assert any(call[0] == "info" for call in st.calls)


def test_option_renderer_uses_certified_values():
    st = FakeStreamlit()
    view = DashboardOptionIntelligenceViewV1(
        source_id="option-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        status="READY",
        source_updated_at=NOW,
        directional_bias="BULLISH",
        confidence=0.8,
        pcr=1.1,
        support=24900,
        resistance=25100,
        max_pain=25000,
    )

    render_option_intelligence(st, view)

    labels = tuple(
        call[1] for call in st.calls if call[0] == "metric"
    )
    assert "PCR" in labels
    assert "Support" in labels
    assert "Max Pain" in labels


def test_runtime_renderer_uses_observations_only():
    st = FakeStreamlit()
    view = DashboardRuntimeOperationsViewV1(
        source_id="runtime-1",
        runtime_status="COMPLETED",
        source_updated_at=NOW,
        market_cycle_duration_seconds=1.5,
        components=(
            DashboardComponentHealthViewV1(
                component="DATA",
                status="COMPLETED",
            ),
        ),
    )

    render_runtime_operations(st, view)

    assert any(call[0] == "dataframe" for call in st.calls)
    assert not any(call[0] == "error" for call in st.calls)


def test_runtime_renderer_fails_closed_for_invalid_type():
    st = FakeStreamlit()

    render_runtime_operations(st, object())

    assert any(call[0] == "error" for call in st.calls)
