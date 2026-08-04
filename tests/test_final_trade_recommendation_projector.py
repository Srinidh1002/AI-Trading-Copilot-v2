"""Task 4 Slice 3 final recommendation projection certification."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace
import ast
from pathlib import Path

import pytest

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.trade_planning.final_trade_recommendation_projector import (
    project_final_trade_recommendation,
)
from test_capital_risk_authority import evaluate, make_input
from test_selected_market_planning_bridge import (
    selected_decision,
)
from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)


def ready_bridge(symbol="NIFTY", direction="BULLISH"):
    decision = selected_decision(
        selected_symbol=symbol,
        selected_changes={"direction": direction},
    )
    return bridge_selected_market_to_planning(
        bridge_result_id="bridge-final",
        decision=decision,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )


def ready_planning(
    bridge,
    *,
    capital_required=5_000.0,
    maximum_loss=1_000.0,
    lots=2,
):
    symbol, exchange = bridge.selected_market
    option_right = bridge.action
    now = bridge.evaluated_at
    direction = (
        "BULLISH" if option_right == "CALL" else "BEARISH"
    )

    entry = SimpleNamespace(
        underlying_symbol=symbol,
        exchange=exchange,
        option_right=option_right,
        status="READY",
        evaluated_at=now,
        entry_zone_lower=100.0,
        entry_zone_upper=102.0,
        decision_reasons=("ENTRY_READY",),
        warnings=(),
    )
    stop = SimpleNamespace(
        underlying_symbol=symbol,
        exchange=exchange,
        option_right=option_right,
        status="READY",
        evaluated_at=now,
        stop_loss_price=95.0,
        decision_reasons=("STOP_READY",),
        invalidation_rules=("EXIT_BELOW_95",),
        warnings=(),
    )
    target = lambda number, price, rr, allocation: SimpleNamespace(
        target_number=number,
        target_price=price,
        reward_to_risk=rr,
        allocation_fraction=allocation,
    )
    targets = SimpleNamespace(
        underlying_symbol=symbol,
        exchange=exchange,
        option_right=option_right,
        status="READY",
        evaluated_at=now,
        target_1=target(1, 110.0, 1.5, 0.4),
        target_2=target(2, 120.0, 3.0, 0.3),
        target_3=target(3, 130.0, 4.5, 0.3),
        weighted_reward_to_risk=2.85,
        decision_reasons=("TARGETS_READY",),
        warnings=(),
    )
    option = SimpleNamespace(
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        status="READY",
        evaluated_at=now,
        selected_expiry=date(2026, 8, 6),
        selected_strike=25_000.0,
        selected_trading_symbol=f"{symbol}06AUG26{option_right}",
        decision_reasons=("CONTRACT_READY",),
        warnings=(),
    )
    size = SimpleNamespace(
        status="READY",
        evaluated_at=now,
        planned_lot_count=lots,
        planned_quantity=lots * 25,
        estimated_total_capital_requirement=capital_required,
        estimated_premium_outlay=capital_required,
        estimated_risk_amount=maximum_loss,
        warnings=(),
    )
    return IntegratedThreeTargetTradePlanResultV1(
        integration_id="integration-final",
        status="READY",
        canonical_trade_plan_input=SimpleNamespace(),
        entry_zone_result=entry,
        stop_loss_result=stop,
        three_target_result=targets,
        option_contract_selection_result=option,
        capital_quantity_result=size,
        decision_reasons=("P6_READY",),
    )


@pytest.mark.parametrize(
    ("symbol", "direction", "action"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_ready_projection_contains_complete_capital_safe_plan(
    symbol,
    direction,
    action,
):
    bridge = ready_bridge(symbol, direction)
    authority = evaluate(
        make_input(selected_market=bridge.selected_market)
    )
    planning = ready_planning(bridge)

    result = project_final_trade_recommendation(
        recommendation_id="recommendation-1",
        bridge=bridge,
        authority=authority,
        planning=planning,
    )

    assert result.action == action
    assert result.selected_market == bridge.selected_market
    assert result.expiry == date(2026, 8, 6)
    assert result.strike == 25_000.0
    assert result.entry_zone_lower == 100.0
    assert result.entry_zone_upper == 102.0
    assert result.stop_loss == 95.0
    assert (result.target_1, result.target_2, result.target_3) == (
        110.0,
        120.0,
        130.0,
    )
    assert result.lots == 2
    assert result.quantity == 50
    assert result.capital_required == 5_000.0
    assert result.maximum_loss == 1_000.0
    assert result.risk_reward == 2.85
    assert result.losing_outcome_reason == "LOWER_RANK"
    assert "EXIT_BELOW_95" in result.invalidation_conditions


def test_blocked_capital_authority_returns_wait_without_geometry():
    bridge = ready_bridge()
    authority = evaluate(
        make_input(
            available_capital=2_000.0,
            maximum_daily_loss=1_000.0,
            realized_daily_loss=0.0,
            bid_price=99.0,
            ask_price=101.0,
        )
    )
    planning = ready_planning(bridge)

    result = project_final_trade_recommendation(
        recommendation_id="recommendation-blocked",
        bridge=bridge,
        authority=authority,
        planning=planning,
    )

    assert result.action == "WAIT"
    assert result.lots == 0
    assert result.contract is None
    assert result.stop_loss is None
    assert authority.blockers[0] in result.blockers


def test_no_trade_bridge_stays_no_trade():
    bridge = ready_bridge()
    no_trade = replace(
        bridge,
        action="NO_TRADE",
        selected_child_action="NO_TRADE",
        planning_allowed=False,
        selected_market=None,
        selected_candidate=None,
        selected_child_result_id=None,
        candidate_id=None,
        observation_id=None,
        direction=None,
        confidence=None,
        score=None,
        losing_market=None,
        losing_outcome_reason=None,
        losing_rationale=(),
        blockers=("NO_ELIGIBLE_MARKET",),
    )
    authority = evaluate(make_input())
    planning = ready_planning(bridge)

    result = project_final_trade_recommendation(
        recommendation_id="recommendation-no-trade",
        bridge=no_trade,
        authority=authority,
        planning=planning,
    )

    assert result.action == "NO_TRADE"
    assert result.selected_market is None
    assert result.quantity == 0
    assert result.capital_required == 0.0


def test_planned_capital_may_not_exceed_deployable_capital():
    bridge = ready_bridge()
    authority = evaluate(make_input())
    planning = ready_planning(
        bridge,
        capital_required=authority.deployable_capital + 1.0,
    )

    with pytest.raises(ValueError, match="deployable"):
        project_final_trade_recommendation(
            recommendation_id="recommendation-over-capital",
            bridge=bridge,
            authority=authority,
            planning=planning,
        )


def test_planned_loss_may_not_exceed_authorized_maximum_loss():
    bridge = ready_bridge()
    authority = evaluate(make_input())
    planning = ready_planning(
        bridge,
        maximum_loss=authority.maximum_new_loss + 1.0,
    )

    with pytest.raises(ValueError, match="loss exceeds"):
        project_final_trade_recommendation(
            recommendation_id="recommendation-over-risk",
            bridge=bridge,
            authority=authority,
            planning=planning,
        )


def test_planned_lots_may_not_exceed_authority():
    bridge = ready_bridge()
    authority = evaluate(make_input())
    planning = ready_planning(
        bridge,
        lots=authority.maximum_affordable_lots + 1,
    )

    with pytest.raises(ValueError, match="lots exceed"):
        project_final_trade_recommendation(
            recommendation_id="recommendation-over-lots",
            bridge=bridge,
            authority=authority,
            planning=planning,
        )


def test_projector_has_no_broker_dashboard_or_order_submission():
    source = Path(
        "services/trade_planning/"
        "final_trade_recommendation_projector.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "broker",
        "dashboard",
        "paper_trading",
        "paper_portfolio",
        "live_execution",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "random.",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "time.sleep(",
    ):
        assert token not in source
