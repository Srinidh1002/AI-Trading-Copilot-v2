from datetime import datetime, timezone

from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.market_session.validator import (
    validate_session_timestamp,
)
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_operator_controls import (
    CertifiedOperatorControls,
    ControlledOpportunityInputFactory,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)
RECEIVED_AT = datetime(
    2026,
    1,
    8,
    10,
    0,
    1,
    tzinfo=timezone.utc,
)
REQUESTED_AT = datetime(
    2026,
    1,
    8,
    10,
    0,
    2,
    tzinfo=timezone.utc,
)


def policy() -> PaperOrchestrationPolicyV1:
    return PaperOrchestrationPolicyV1(
        orchestration_policy_id="policy-1",
        policy_timestamp=NOW,
    )


def cycle():
    session = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=NOW,
        evaluated_at=RECEIVED_AT,
        id_factory=lambda: "session-nifty-operator-controls",
    )

    return build_certified_cycle_input(
        cycle_kind="OPPORTUNITY",
        observation_id="operator-control-observation-1",
        orchestration_policy=policy(),
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_timestamp=NOW,
        received_at=RECEIVED_AT,
        cycle_requested_at=REQUESTED_AT,
        session_validation=session,
    )


def test_observe_only_disables_entries_but_preserves_monitoring():
    controls = CertifiedOperatorControls(observe_only=True)

    result = controls.snapshot()

    assert result.observe_only is True
    assert result.new_entries_allowed is False
    assert result.position_monitoring_allowed is True
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_emergency_halt_disables_entries():
    controls = CertifiedOperatorControls(observe_only=False)
    controls.set_emergency_halt(True)

    result = controls.snapshot()

    assert result.observe_only is False
    assert result.emergency_halt is True
    assert result.new_entries_allowed is False
    assert result.position_monitoring_allowed is True


def test_controlled_factory_applies_fail_closed_policy():
    controls = CertifiedOperatorControls(observe_only=True)

    result = ControlledOpportunityInputFactory(
        delegate=cycle,
        controls=controls,
    )()

    assert result.orchestration_policy.emergency_paper_halt is True
    assert result.metadata["operator_observe_only"] is True
    assert result.metadata["operator_emergency_halt"] is False
    assert result.metadata["operator_new_entries_allowed"] is False
    assert (
        result.metadata["operator_position_monitoring_allowed"]
        is True
    )
    assert result.execution_mode == "PAPER"


def test_emergency_halt_is_applied_to_cycle_policy():
    controls = CertifiedOperatorControls(
        observe_only=False,
        emergency_halt=True,
    )

    result = ControlledOpportunityInputFactory(
        delegate=cycle,
        controls=controls,
    )()

    assert result.orchestration_policy.emergency_paper_halt is True
    assert result.metadata["operator_observe_only"] is False
    assert result.metadata["operator_emergency_halt"] is True
    assert result.metadata["operator_new_entries_allowed"] is False


def test_entry_enabled_returns_original_cycle():
    controls = CertifiedOperatorControls(observe_only=False)
    source = cycle()

    result = ControlledOpportunityInputFactory(
        delegate=lambda: source,
        controls=controls,
    )()

    assert result is source
    assert (
        result.orchestration_policy.emergency_paper_halt
        is False
    )