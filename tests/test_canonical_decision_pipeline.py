from services.canonical.pipeline import (
    CanonicalPipelineDependencies,
    run_canonical_pipeline,
)

from test_canonical_analysis_pipeline import _dependencies, _snapshot


def test_canonical_pipeline_returns_an_analysis_only_directional_decision():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=CanonicalPipelineDependencies(analysis=_dependencies()),
    )

    assert decision.action == "BUY"
    assert decision.authorization_status == "ANALYSIS_ONLY"
    assert decision.execution_status == "NOT_REQUESTED"
    assert decision.trade_plan is None


def test_canonical_pipeline_fails_closed_for_invalid_snapshot():
    snapshot = _snapshot()
    snapshot.ltp = None
    snapshot.__post_init__()

    decision = run_canonical_pipeline(
        snapshot,
        dependencies=CanonicalPipelineDependencies(analysis=_dependencies()),
    )

    assert decision.action == "WAIT"
    assert decision.authorization_status == "BLOCKED"
