from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import (
    CertifiedCycleIdentityBundleV1,
    build_certified_cycle_identities,
    build_certified_cycle_input,
)


IST = ZoneInfo("Asia/Kolkata")
MARKET_TIME = datetime(2026, 1, 8, 10, 0, tzinfo=IST)
RECEIVED_AT = datetime(2026, 1, 8, 10, 0, 1, tzinfo=IST)
REQUESTED_AT = datetime(2026, 1, 8, 10, 0, 2, tzinfo=IST)


def policy(*, emergency_halt=False):
    return PaperOrchestrationPolicyV1(
        orchestration_policy_id="certified-policy-1",
        policy_timestamp=MARKET_TIME,
        emergency_paper_halt=emergency_halt,
    )


def session(symbol="NIFTY", exchange="NSE"):
    return validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=MARKET_TIME,
        evaluated_at=RECEIVED_AT,
        id_factory=lambda: (
            f"session-{symbol.strip().upper()}-"
            f"{exchange.strip().upper()}-2026-01-08T10-00-00"
        ),
    )


def build(**overrides):
    values = {
        "cycle_kind": "OPPORTUNITY",
        "observation_id": "observation-1",
        "orchestration_policy": policy(),
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "market_timestamp": MARKET_TIME,
        "received_at": RECEIVED_AT,
        "cycle_requested_at": REQUESTED_AT,
        "session_validation": session(),
    }
    values.update(overrides)
    return build_certified_cycle_input(**values)


def test_identity_bundle_is_exact_paper_only_and_deterministic():
    first = build_certified_cycle_identities(
        cycle_kind="OPPORTUNITY",
        observation_id="observation-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME,
    )
    second = build_certified_cycle_identities(
        cycle_kind="OPPORTUNITY",
        observation_id="observation-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME,
    )

    assert type(first) is CertifiedCycleIdentityBundleV1
    assert first == second
    assert first.execution_mode == "PAPER"
    assert first.live_execution_eligible is False
    assert len({
        first.cycle_id,
        first.cycle_idempotency_key,
        first.p6_integration_id,
        first.p8_admission_request_id,
        first.p8_admission_idempotency_key,
        first.p8_portfolio_event_id,
        first.p7_requested_transition_id,
        first.p7_position_id,
        first.p7_entry_fill_id,
        first.p8_update_idempotency_key,
        first.p8_update_event_id,
    }) == 11


def test_opportunity_and_monitoring_identities_are_separate():
    opportunity = build_certified_cycle_identities(
        cycle_kind="OPPORTUNITY",
        observation_id="observation-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME,
    )
    monitoring = build_certified_cycle_identities(
        cycle_kind="MONITORING",
        observation_id="observation-1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        market_timestamp=MARKET_TIME,
    )

    assert opportunity.cycle_id != monitoring.cycle_id
    assert (
        opportunity.cycle_idempotency_key
        != monitoring.cycle_idempotency_key
    )


def test_factory_returns_exact_valid_cycle_input():
    value = build()

    assert type(value) is PaperOrchestrationCycleInputV1
    assert value.underlying_symbol == "NIFTY"
    assert value.exchange == "NSE"
    assert value.trading_day_id == "2026-01-08"
    assert value.execution_mode == "PAPER"
    assert value.metadata["certified_runtime"] is True
    assert value.metadata["cycle_kind"] == "OPPORTUNITY"
    assert value.metadata["broker_order_submission"] is False
    assert value.metadata["live_execution_eligible"] is False


def test_factory_preserves_semantic_hash_determinism():
    first = build()
    second = build()

    assert first.semantic_hash() == second.semantic_hash()
    assert first.semantic_dict() == second.semantic_dict()


def test_observation_change_changes_cycle_identity_and_hash():
    first = build()
    second = build(observation_id="observation-2")

    assert first.cycle_id != second.cycle_id
    assert (
        first.cycle_idempotency_key
        != second.cycle_idempotency_key
    )
    assert first.semantic_hash() != second.semantic_hash()


def test_factory_supports_sensex_bse_identity():
    value = build(
        underlying_symbol="SENSEX",
        exchange="BSE",
        session_validation=session("SENSEX", "BSE"),
    )

    assert value.underlying_symbol == "SENSEX"
    assert value.exchange == "BSE"


@pytest.mark.parametrize("kind", ("LIVE", "ENTRY", "", None))
def test_unsupported_cycle_kind_is_rejected(kind):
    with pytest.raises((TypeError, ValueError)):
        build(cycle_kind=kind)


def test_session_identity_mismatch_fails_closed():
    with pytest.raises(
        ValueError,
        match="session_validation market identity mismatch",
    ):
        build(
            underlying_symbol="SENSEX",
            exchange="BSE",
            session_validation=session("NIFTY", "NSE"),
        )


def test_timestamp_order_is_enforced_by_contract():
    with pytest.raises(ValueError, match="received_at"):
        build(received_at=MARKET_TIME.replace(hour=9))


def test_protected_metadata_cannot_be_overridden():
    with pytest.raises(ValueError, match="protected keys"):
        build(metadata={"broker_order_submission": True})


def test_emergency_halt_policy_is_preserved():
    value = build(
        orchestration_policy=policy(emergency_halt=True),
    )

    assert value.orchestration_policy.emergency_paper_halt is True
    assert value.execution_mode == "PAPER"
