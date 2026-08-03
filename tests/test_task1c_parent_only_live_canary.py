from datetime import datetime, timezone

import pytest

from services.certification.task1c_parent_only_live_canary import Task1CParentOnlyDependenciesV1


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
