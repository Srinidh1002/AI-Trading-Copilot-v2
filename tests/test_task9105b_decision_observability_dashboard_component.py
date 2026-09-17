from services.contracts.task9_decision_observability_v1 import (
    Task9DecisionObservabilityV1,
)
from services.dashboard_read_models.task9_decision_observability_view_v1 import (
    build_task9_decision_observability_dashboard_view,
)

from dashboard.dashboard_read_model_state import (
    DECISION_OBSERVABILITY_STATE_KEY,
    get_task9_decision_observability_view,
)
from dashboard.decision_observability_components import (
    render_task9_decision_observability,
)


def _view():
    source = Task9DecisionObservabilityV1(
        audit_id="audit-ui-1",
        parent_cycle_id="cycle-ui-1",
        prediction_id="prediction-ui-1",
        market="NIFTY",
        exchange="NSE",
        action="NO_TRADE",
        direction="BEARISH",
        eligibility="INELIGIBLE",
        first_causal_blocker="POLICY_INELIGIBLE",
        concurrent_blockers=(
            "POLICY_INELIGIBLE",
        ),
        decision_reasons=(
            "INSUFFICIENT_DIRECTIONAL_FAMILIES",
        ),
        actual_confidence=53.0,
        required_confidence=55.0,
        confidence_margin=-2.0,
        supporting_family_count=1,
        required_family_count=2,
        family_margin=-1,
        supporting_families=(
            "TECHNICAL",
        ),
        opposing_families=(),
        candidate_reached=True,
        ranking_reached=True,
        planning_reached=False,
        capital_authority_reached=False,
        paper_entry_reached=False,
    )

    return (
        build_task9_decision_observability_dashboard_view(
            source
        )
    )


class _Column:
    def __init__(self, events):
        self.events = events

    def metric(self, label, value):
        self.events.append(
            ("metric", label, value)
        )


class _Streamlit:
    def __init__(self):
        self.events = []

    def subheader(self, value):
        self.events.append(
            ("subheader", value)
        )

    def info(self, value):
        self.events.append(
            ("info", value)
        )

    def caption(self, value):
        self.events.append(
            ("caption", value)
        )

    def columns(self, count):
        return tuple(
            _Column(self.events)
            for _ in range(count)
        )

    def write(self, value):
        self.events.append(
            ("write", value)
        )

    def warning(self, value):
        self.events.append(
            ("warning", value)
        )


def test_read_boundary_returns_exact_typed_view():
    view = _view()

    state = {
        DECISION_OBSERVABILITY_STATE_KEY:
            view,
    }

    result = get_task9_decision_observability_view(
        state
    )

    assert result is view


def test_read_boundary_returns_none_when_absent():
    assert (
        get_task9_decision_observability_view({})
        is None
    )


def test_read_boundary_rejects_wrong_type():
    state = {
        DECISION_OBSERVABILITY_STATE_KEY:
            {"not": "typed"},
    }

    try:
        get_task9_decision_observability_view(
            state
        )
    except TypeError:
        pass
    else:
        raise AssertionError(
            "wrong typed dashboard state accepted"
        )


def test_renderer_has_safe_unavailable_state():
    st = _Streamlit()

    render_task9_decision_observability(
        st=st,
        view=None,
    )

    assert (
        "subheader",
        "Decision History",
    ) in st.events

    info = [
        event
        for event in st.events
        if event[0] == "info"
    ]

    assert len(info) == 1
    assert "legacy SQLite" in info[0][1]


def test_renderer_exposes_decision_funnel():
    st = _Streamlit()

    render_task9_decision_observability(
        st=st,
        view=_view(),
    )

    writes = [
        event[1]
        for event in st.events
        if event[0] == "write"
    ]

    assert (
        "First causal blocker: POLICY_INELIGIBLE"
        in writes
    )

    assert "Candidate: REACHED" in writes
    assert "Option ranking: REACHED" in writes
    assert "Trade planning: NOT REACHED" in writes
    assert "Capital authority: NOT REACHED" in writes
    assert "PAPER entry: NOT REACHED" in writes


def test_renderer_exposes_threshold_metrics():
    st = _Streamlit()

    render_task9_decision_observability(
        st=st,
        view=_view(),
    )

    metrics = [
        event
        for event in st.events
        if event[0] == "metric"
    ]

    assert (
        "metric",
        "Confidence / Required",
        "53.0 / 55.0 (-2.0)",
    ) in metrics

    assert (
        "metric",
        "Directional families / Required",
        "1 / 2 (-1)",
    ) in metrics
