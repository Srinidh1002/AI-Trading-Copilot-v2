"""Task 4 entry, stop-loss, and target planning integration."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.trade_planning.selected_option_entry_stop_target_planner import (
    plan_selected_option_entry_stop_targets,
)
from test_selected_option_affordability_risk_planner import certified, plan
from tests.test_canonical_trade_plan_input_v1 import _value
from tests.test_trade_planning_policy_v1 import _p


def ready_affordability(symbol="NIFTY", direction="BULLISH"):
    return plan(certified(symbol, direction))


def run(
    affordability=None,
    trade_plan_input=None,
    policy=None,
    **changes,
):
    if affordability is None:
        affordability = ready_affordability()

    if trade_plan_input is None:
        trade_plan_input = _value(
            affordability.selected_market
            if hasattr(affordability, "selected_market")
            else ("NIFTY", "NSE")
        )

    if policy is None:
        policy = _p(
            stop_loss_method="ATR",
            target_method="RISK_MULTIPLE",
        )
    defaults = dict(
        planning_result_id="task4-result-1",
        entry_evaluation_id="entry-evaluation-1",
        entry_evaluation_result_id="entry-result-1",
        stop_evaluation_id="stop-evaluation-1",
        stop_evaluation_result_id="stop-result-1",
        target_evaluation_id="target-evaluation-1",
        target_evaluation_result_id="target-result-1",
        affordability=affordability,
        trade_plan_input=trade_plan_input,
        policy=policy,
        evaluated_at=(
            affordability.evaluated_at
            if hasattr(affordability, "evaluated_at")
            else ready_affordability().evaluated_at
        ),
        signal_reference_price=100.0,
        atr_value=10.0,
        structure_stop_price=95.0,
        recent_swing_low=96.0,
        recent_swing_high=105.0,
        expected_move_value=10.0,
        resistance_levels=(110.0, 115.0, 120.0),
        support_levels=(80.0, 90.0),
    )
    defaults.update(changes)
    return plan_selected_option_entry_stop_targets(**defaults)


def test_ready_chain_uses_existing_evaluators():
    result = run()

    assert result.status == "READY"
    assert result.planning_allowed is True
    assert result.entry_result.status == "READY"
    assert result.entry_result.entry_reference_price == 100.0
    assert result.stop_loss_result.status == "READY"
    assert result.stop_loss_result.stop_loss_price == 90.0
    assert result.target_result.status == "READY"
    assert [
        target.target_price
        for target in (
            result.target_result.target_1,
            result.target_result.target_2,
            result.target_result.target_3,
        )
    ] == [110.0, 115.0, 120.0]


@pytest.mark.parametrize(
    ("symbol", "direction", "right"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("NIFTY", "BEARISH", "PUT"),
        ("SENSEX", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_both_markets_and_directions(symbol, direction, right):
    affordability = ready_affordability(symbol, direction)
    result = run(
        affordability=affordability,
        trade_plan_input=_value(affordability.selected_market),
    )

    assert result.status == "READY"
    assert result.entry_result.option_right == right
    assert result.stop_loss_result.option_right == right
    assert result.target_result.option_right == right


def test_trace_chain_is_preserved():
    affordability = ready_affordability()
    result = run(affordability=affordability)

    assert result.affordability_result_id == affordability.affordability_result_id
    assert result.certification_result_id == affordability.certification_result_id
    assert result.parent_cycle_id == affordability.parent_cycle_id
    assert result.parent_decision_id == affordability.parent_decision_id
    assert result.bridge_result_id == affordability.bridge_result_id
    assert result.candidate_id == affordability.candidate_id
    assert result.observation_id == affordability.observation_id
    assert result.ranking_result_id == affordability.ranking_result_id
    assert result.contract_id == affordability.contract_id


def test_affordability_not_ready_is_unavailable():
    affordability = ready_affordability()
    blocked = replace(
        affordability,
        status="BLOCKED",
        planning_allowed=False,
        blockers=("CAPITAL_BLOCKED",),
    )
    result = run(affordability=blocked)

    assert result.status == "UNAVAILABLE"
    assert result.entry_result is None
    assert result.blockers == (
        "AFFORDABILITY_RISK_NOT_READY",
        "CAPITAL_BLOCKED",
    )


def test_entry_failure_stops_chain():
    result = run(
        policy=_p(
            stop_loss_method="ATR",
            target_method="RISK_MULTIPLE",
            maximum_entry_premium=99.0,
        )
    )

    assert result.status == "BLOCKED"
    assert result.entry_result.status == "BLOCKED"
    assert result.stop_loss_result is None
    assert result.target_result is None
    assert "ENTRY_PREMIUM_LIMIT_EXCEEDED" in result.blockers


def test_stop_failure_stops_before_targets():
    result = run(atr_value=None)

    assert result.status == "BLOCKED"
    assert result.entry_result.status == "READY"
    assert result.stop_loss_result.status == "BLOCKED"
    assert result.target_result is None
    assert "STOP_REFERENCE_UNAVAILABLE" in result.blockers


def test_target_failure_is_preserved():
    result = run(
        policy=_p(
            stop_loss_method="ATR",
            target_method="EXPECTED_MOVE",
        ),
        expected_move_value=None,
    )

    assert result.status == "BLOCKED"
    assert result.entry_result.status == "READY"
    assert result.stop_loss_result.status == "READY"
    assert result.target_result.status == "BLOCKED"
    assert "TARGET_REFERENCE_UNAVAILABLE" in result.blockers


def test_market_mismatch_blocks_at_entry():
    affordability = ready_affordability("NIFTY")
    result = run(
        affordability=affordability,
        trade_plan_input=_value(("SENSEX", "BSE")),
    )

    assert result.status == "BLOCKED"
    assert result.entry_result.status == "BLOCKED"
    assert "TASK4_MARKET_IDENTITY_MISMATCH" in result.blockers


def test_capital_mismatch_blocks_at_entry():
    affordability = ready_affordability()
    trade_plan_input = _value(("NIFTY", "NSE"))
    object.__setattr__(trade_plan_input, "available_capital", 50_000.0)

    result = run(
        affordability=affordability,
        trade_plan_input=trade_plan_input,
    )

    assert "TASK4_CAPITAL_EVIDENCE_MISMATCH" in result.blockers


def test_output_is_deterministic_and_inputs_are_not_mutated():
    affordability = ready_affordability()
    trade_plan_input = _value(("NIFTY", "NSE"))
    policy = _p(stop_loss_method="ATR", target_method="RISK_MULTIPLE")
    before = (
        affordability.to_json(),
        trade_plan_input.to_json(),
        policy.to_json(),
    )

    first = run(
        affordability=affordability,
        trade_plan_input=trade_plan_input,
        policy=policy,
    )
    second = run(
        affordability=affordability,
        trade_plan_input=trade_plan_input,
        policy=policy,
    )

    assert first.to_json() == second.to_json()
    assert before == (
        affordability.to_json(),
        trade_plan_input.to_json(),
        policy.to_json(),
    )


def test_wrong_exact_types_are_rejected():
    affordability = ready_affordability()
    with pytest.raises(TypeError, match="affordability"):
        run(affordability=object())
    with pytest.raises(TypeError, match="trade_plan_input"):
        run(affordability=affordability, trade_plan_input=object())
    with pytest.raises(TypeError, match="policy"):
        run(affordability=affordability, policy=object())


def test_no_provider_broker_lifecycle_or_persistence_dependencies():
    source = Path(
        "services/trade_planning/"
        "selected_option_entry_stop_target_planner.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "provider",
        "broker",
        "paper_trading",
        "paper_portfolio",
        "persistence",
        "repository",
        "requests",
        "dashboard",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "random.",
        "time.sleep(",
    ):
        assert token not in source
