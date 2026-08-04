from datetime import datetime, timezone

import pytest

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_lifecycle_policy_v1 import (
    PaperTradeLifecyclePolicyV1,
)
from services.paper_orchestration.certified_new_entry_input_factory import (
    CertifiedNewEntryInputFactory,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleInputV1,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


def cycle():
    value = object.__new__(PaperOrchestrationCycleInputV1)
    fields = {
        "cycle_id": "cycle-1",
        "cycle_idempotency_key": "cycle-key-1",
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "trading_day_id": "2026-01-08",
        "cycle_requested_at": NOW,
        "p6_integration_id": "p6-integration-1",
        "p8_admission_request_id": "admission-request-1",
        "p8_admission_idempotency_key": "admission-key-1",
        "p8_portfolio_event_id": "admission-event-1",
        "p7_requested_transition_id": "transition-1",
        "p7_position_id": "position-1",
        "p7_entry_fill_id": "entry-fill-1",
        "p8_update_idempotency_key": "update-key-1",
        "p8_update_event_id": "update-event-1",
    }
    for name, item in fields.items():
        object.__setattr__(value, name, item)
    return value


def plan():
    value = object.__new__(IntegratedThreeTargetTradePlanResultV1)
    object.__setattr__(value, "integration_id", "p6-integration-1")
    object.__setattr__(value, "status", "READY")
    object.__setattr__(value, "execution_mode", "PAPER")
    object.__setattr__(value, "live_execution_eligible", False)
    canonical = type(
        "Canonical",
        (),
        {"underlying_symbol": "NIFTY", "exchange": "NSE"},
    )()
    object.__setattr__(value, "canonical_trade_plan_input", canonical)
    return value


def exact(contract, **fields):
    value = object.__new__(contract)
    for name, item in fields.items():
        object.__setattr__(value, name, item)
    return value


def factory():
    return CertifiedNewEntryInputFactory(
        portfolio_id="certified-paper-portfolio",
        starting_capital=10000,
        portfolio_policy_provider=lambda *_: exact(PaperPortfolioPolicyV1),
        lifecycle_policy_provider=lambda *_: exact(
            PaperTradeLifecyclePolicyV1
        ),
        observation_provider=lambda *_: exact(
            PaperMarketObservationV1,
            underlying_symbol="NIFTY",
            exchange="NSE",
        ),
    )


def test_builds_exact_new_entry_lifecycle_input():
    result = factory()(cycle(), plan())

    assert type(result) is NewEntryPaperLifecycleInputV1
    assert result.admission_request_id == "admission-request-1"
    assert result.requested_transition_id == "transition-1"
    assert result.position_id == "position-1"
    assert result.entry_fill_id == "entry-fill-1"
    assert result.activation_update_idempotency_key == "update-key-1"
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_factory_is_deterministic():
    first = factory()(cycle(), plan())
    second = factory()(cycle(), plan())

    assert first.initial_portfolio_snapshot_id == second.initial_portfolio_snapshot_id
    assert first.requested_reservation_id == second.requested_reservation_id
    assert first.paper_trade_id == second.paper_trade_id


def test_rejects_non_ready_plan():
    value = plan()
    object.__setattr__(value, "status", "BLOCKED")

    with pytest.raises(ValueError, match="READY"):
        factory()(cycle(), value)


def test_rejects_p6_identity_mismatch():
    value = plan()
    object.__setattr__(value, "integration_id", "other")

    with pytest.raises(ValueError, match="P6 integration"):
        factory()(cycle(), value)


def test_rejects_observation_market_mismatch():
    value = CertifiedNewEntryInputFactory(
        portfolio_id="certified-paper-portfolio",
        starting_capital=10000,
        portfolio_policy_provider=lambda *_: exact(PaperPortfolioPolicyV1),
        lifecycle_policy_provider=lambda *_: exact(
            PaperTradeLifecyclePolicyV1
        ),
        observation_provider=lambda *_: exact(
            PaperMarketObservationV1,
            underlying_symbol="SENSEX",
            exchange="BSE",
        ),
    )

    with pytest.raises(ValueError, match="observation/cycle"):
        value(cycle(), plan())


def test_rejects_legacy_policy_mapping():
    value = CertifiedNewEntryInputFactory(
        portfolio_id="certified-paper-portfolio",
        starting_capital=10000,
        portfolio_policy_provider=lambda *_: {},
        lifecycle_policy_provider=lambda *_: exact(
            PaperTradeLifecyclePolicyV1
        ),
        observation_provider=lambda *_: exact(
            PaperMarketObservationV1,
            underlying_symbol="NIFTY",
            exchange="NSE",
        ),
    )

    with pytest.raises(TypeError, match="PaperPortfolioPolicyV1"):
        value(cycle(), plan())
