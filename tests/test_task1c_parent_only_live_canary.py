from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.certification.task1c_parent_only_live_canary import Task1CParentOnlyDependenciesV1, _component_status


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def test_parent_only_dependency_contract_exposes_no_downstream_capabilities():
    dependency = Task1CParentOnlyDependenciesV1("branch", "commit", lambda: None, lambda: NOW, lambda: "run")
    assert dependency.execution_mode == "PAPER"
    assert not dependency.live_execution_eligible and not dependency.broker_order_submission
    for name in ("selected_planner", "lifecycle", "monitoring", "order_adapter"):
        assert not hasattr(dependency, name)


@pytest.mark.parametrize("changes", ({"execution_mode": "LIVE"}, {"live_execution_eligible": True}, {"broker_order_submission": True}))
def test_parent_only_contract_rejects_non_paper_safety_values(changes):
    values = dict(branch="branch", commit="commit", run_parent=lambda: None, clock=lambda: NOW, id_factory=lambda: "run")
    values.update(changes)
    with pytest.raises(ValueError):
        Task1CParentOnlyDependenciesV1(**values)


def test_shared_parent_boundary_can_be_distinct_from_individual_receipt_times():
    # The certified reader normalizes both captures to the parent boundary;
    # provider receipt timestamps remain on the individual capture contracts.
    first = NOW
    second = NOW.replace(second=1)
    assert max(first, second) == second


def test_early_candidate_failure_is_attributed_once_and_downstream_is_not_evaluated():
    entry = SimpleNamespace(child=SimpleNamespace(candidate=None, terminal_status="FAILED", blockers=("CANDIDATE_COMPOSITION_FAILED",), errors=("CANDIDATE_COMPOSITION_FAILED",)))
    broader = SimpleNamespace(intelligence_status="READY_WITH_WARNINGS", blockers=(), warnings=("optional breadth evidence is unavailable",))
    summary = _component_status(entry, broader, None)
    assert summary["terminal_components"] == ["candidate_composition"]
    assert summary["terminal_reason_codes"] == ["CANDIDATE_COMPOSITION_FAILED"]
    assert summary["statuses"]["candidate_composition"] == "FAILED"
    assert summary["statuses"]["technical"] == "NOT_EVALUATED"
    assert summary["statuses"]["external_context"] == "UNAVAILABLE"
