from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts.selected_option_contract_v1 import (
    SelectedOptionContractV1,
)
from services.options.policies import TradePlanPolicy
from services.options.trade_plan import build_trade_plan


NOW = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)


def selected(
    action: str = "BUY",
    kind: str | None = "CALL",
    **changes,
) -> SelectedOptionContractV1:
    values = {
        "selection_id": "sel",
        "selected_at": NOW,
        "snapshot_id": "snap",
        "decision_id": "dec",
        "universe_id": "uni",
        "contract_id": "con",
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "action": action,
        "option_type": kind,
        "trading_symbol": "SYM",
        "instrument_token": None,
        "expiry_date": date(2026, 7, 30),
        "strike": 25000,
        "lot_size": 50,
        "reference_spot_price": 25000,
        "reference_option_price": 100,
        "reference_price_source": "LAST",
        "expiry_selection_policy": "EARLIEST_ELIGIBLE",
        "strike_selection_policy": "NEAREST_ATM",
        "selection_valid": True,
        "blockers": (),
        "warnings": (),
        "metadata": {},
    }
    values.update(changes)

    return SelectedOptionContractV1(**values)


def build(
    selected_contract: SelectedOptionContractV1 | None = None,
    **changes,
):
    action = changes.pop("action", "BUY")

    return build_trade_plan(
        snapshot_id=changes.pop("snapshot_id", "snap"),
        analysis_id=changes.pop("analysis_id", "analysis"),
        decision_id=changes.pop("decision_id", "dec"),
        action=action,
        selected_contract=selected_contract or selected(),
        clock=changes.pop("clock", lambda: NOW),
        id_factory=changes.pop("id_factory", lambda: "plan"),
        **changes,
    )


def test_valid_identity_and_reference_fallback():
    plan = build()

    assert (
        plan.trade_plan_id,
        plan.selection_id,
        plan.contract_id,
        plan.entry_reference_price,
        plan.plan_status,
    ) == (
        "plan",
        "sel",
        "con",
        100,
        "READY_FOR_RISK",
    )


def test_sell_put_preserves_identity():
    contract = selected(
        "SELL",
        "PUT",
        underlying_symbol="SENSEX",
        exchange="BSE",
    )

    plan = build(
        contract,
        action="SELL",
    )

    assert (
        plan.action,
        plan.option_type,
        plan.exchange,
    ) == (
        "SELL",
        "PUT",
        "BSE",
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_reference_price", 101),
        ("stop_loss_price", 90),
        ("target_price", 120),
    ],
)
def test_explicit_values_preserved(field, value):
    plan = build(**{field: value})

    assert getattr(plan, field) == value


def test_missing_entry_returns_insufficient_data():
    contract = selected(
        reference_option_price=None,
        reference_price_source="UNAVAILABLE",
    )

    plan = build(contract)

    assert plan.plan_status == "INSUFFICIENT_DATA"
    assert plan.paper_preparation_eligible is False


def test_missing_required_stop_loss_returns_insufficient_data():
    plan = build(
        policy=TradePlanPolicy(
            require_stop_loss=True,
        )
    )

    assert plan.plan_status == "INSUFFICIENT_DATA"
    assert plan.paper_preparation_eligible is False


def test_missing_required_target_returns_insufficient_data():
    plan = build(
        policy=TradePlanPolicy(
            require_target=True,
        )
    )

    assert plan.plan_status == "INSUFFICIENT_DATA"
    assert plan.paper_preparation_eligible is False


def test_risk_and_execution_fields_remain_unset():
    plan = build()

    assert (
        plan.quantity,
        plan.lots,
        plan.capital_required,
        plan.maximum_loss,
        plan.execution_eligible,
    ) == (
        None,
        None,
        None,
        None,
        False,
    )


@pytest.mark.parametrize(
    "cap",
    [
        NOW,
        NOW - timedelta(seconds=1),
    ],
)
def test_contract_expiry_caps_block(cap):
    plan = build(
        contract_expiry_at=cap,
    )

    assert plan.plan_status == "EXPIRED"
    assert plan.paper_preparation_eligible is False


@pytest.mark.parametrize(
    "cap",
    [
        NOW,
        NOW - timedelta(seconds=1),
    ],
)
def test_session_close_caps_block(cap):
    plan = build(
        session_close_at=cap,
    )

    assert plan.plan_status == "EXPIRED"
    assert plan.paper_preparation_eligible is False


def test_earliest_validity_cap_wins():
    plan = build(
        contract_expiry_at=NOW + timedelta(seconds=20),
        session_close_at=NOW + timedelta(seconds=10),
    )

    assert plan.valid_until == NOW + timedelta(seconds=10)


def test_contract_expiry_cap_wins_when_earlier():
    plan = build(
        contract_expiry_at=NOW + timedelta(seconds=10),
        session_close_at=NOW + timedelta(seconds=20),
    )

    assert plan.valid_until == NOW + timedelta(seconds=10)


def test_validity_seconds_determine_default_valid_until():
    plan = build(
        policy=TradePlanPolicy(
            validity_seconds=120,
        )
    )

    assert plan.valid_until == NOW + timedelta(seconds=120)


def test_injected_clock_controls_created_and_valid_from():
    custom_now = NOW + timedelta(minutes=5)

    plan = build(
        clock=lambda: custom_now,
    )

    assert plan.created_at == custom_now
    assert plan.valid_from == custom_now


def test_injected_id_factory_controls_plan_id():
    plan = build(
        id_factory=lambda: "fixed-plan-id",
    )

    assert plan.trade_plan_id == "fixed-plan-id"


def test_naive_contract_expiry_rejected():
    with pytest.raises(ValueError):
        build(
            contract_expiry_at=datetime(2026, 7, 27),
        )


def test_naive_session_close_rejected():
    with pytest.raises(ValueError):
        build(
            session_close_at=datetime(2026, 7, 27),
        )


def test_invalid_or_no_selection_has_no_fake_identity():
    contract = selected(
        action="WAIT",
        kind=None,
        selection_valid=False,
        blockers=("No option contract selected.",),
        universe_id=None,
        contract_id=None,
        trading_symbol=None,
        expiry_date=None,
        strike=None,
        lot_size=None,
        reference_option_price=None,
        reference_price_source="UNAVAILABLE",
    )

    plan = build(
        contract,
        action="WAIT",
    )

    assert plan.plan_status == "INSUFFICIENT_DATA"
    assert plan.selection_id is None
    assert plan.contract_id is None
    assert plan.trading_symbol is None
    assert plan.expiry_date is None
    assert plan.strike is None
    assert plan.lot_size is None
    assert plan.paper_preparation_eligible is False
    assert plan.execution_eligible is False


def test_buy_put_mismatch_blocks():
    contract = selected(
        action="BUY",
        kind="PUT",
        selection_valid=False,
        blockers=("Action and option type mismatch.",),
    )

    plan = build(
        contract,
        action="BUY",
    )

    assert plan.plan_status == "INSUFFICIENT_DATA"
    assert "Action and option type do not match." in plan.blockers
    assert "Selected contract is invalid." in plan.blockers
    assert plan.paper_preparation_eligible is False
    assert plan.execution_eligible is False


def test_sell_call_mismatch_blocks():
    contract = selected(
        action="SELL",
        kind="CALL",
        selection_valid=False,
        blockers=("Action and option type mismatch.",),
    )

    plan = build(
        contract,
        action="SELL",
    )

    assert plan.plan_status == "INSUFFICIENT_DATA"
    assert "Action and option type do not match." in plan.blockers
    assert "Selected contract is invalid." in plan.blockers
    assert plan.paper_preparation_eligible is False
    assert plan.execution_eligible is False


def test_selected_contract_is_not_mutated():
    contract = selected()
    before = contract.to_dict()

    build(contract)

    assert contract.to_dict() == before


def test_policy_is_not_mutated():
    policy = TradePlanPolicy(
        validity_seconds=120,
        require_entry_reference_price=True,
        require_stop_loss=False,
        require_target=False,
    )

    build(policy=policy)

    assert policy == TradePlanPolicy(
        validity_seconds=120,
        require_entry_reference_price=True,
        require_stop_loss=False,
        require_target=False,
    )


def test_semantic_result_is_deterministic():
    first = build()
    second = build()

    assert first.semantic_dict() == second.semantic_dict()


def test_stop_loss_is_not_derived():
    plan = build()

    assert plan.stop_loss_price is None
    assert plan.stop_loss_source is None


def test_target_is_not_derived():
    plan = build()

    assert plan.target_price is None
    assert plan.target_source is None