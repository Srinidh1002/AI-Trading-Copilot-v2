"""Task 4 Slice 4 runtime integration and final certification."""
from dataclasses import replace
import ast
from pathlib import Path

import pytest

from services.trade_planning.capital_safe_recommendation_runtime import (
    run_capital_safe_recommendation_cycle,
)
from test_capital_risk_authority import make_input
from test_final_trade_recommendation_projector import (
    ready_planning,
)
from test_selected_market_planning_bridge import (
    selected_decision,
)


def run_runtime(
    *,
    symbol="NIFTY",
    direction="BULLISH",
    capital_changes=None,
    planner=None,
):
    decision = selected_decision(
        selected_symbol=symbol,
        selected_changes={"direction": direction},
    )
    capital = make_input(
        selected_market=decision.selected_market,
        evaluated_at=decision.completed_at,
        **(capital_changes or {}),
    )
    calls = []

    def default_planner(bridge, authority):
        calls.append(
            (
                bridge.selected_market,
                authority.selected_market,
                authority.status,
            )
        )
        return ready_planning(bridge)

    result = run_capital_safe_recommendation_cycle(
        bridge_result_id="bridge-runtime",
        authority_result_id="authority-runtime",
        recommendation_id="recommendation-runtime",
        decision=decision,
        capital_risk_input=capital,
        maximum_candidate_age_seconds=180.0,
        certified_p6_planner=planner or default_planner,
    )
    return result, calls


@pytest.mark.parametrize(
    ("symbol", "direction", "action"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_selected_market_reaches_p6_once_and_returns_complete_plan(
    symbol,
    direction,
    action,
):
    result, calls = run_runtime(
        symbol=symbol,
        direction=direction,
    )

    assert calls == [
        (
            result.selected_market,
            result.selected_market,
            "READY",
        )
    ]
    assert result.action == action
    assert result.contract is not None
    assert result.lots >= 1
    assert result.quantity >= 1
    assert result.capital_required > 0.0
    assert result.maximum_loss > 0.0
    assert result.capital_required <= 100_000.0
    assert result.maximum_loss <= 2_000.0


def test_blocked_capital_returns_wait_and_never_exposes_geometry():
    result, calls = run_runtime(
        capital_changes={
            "available_capital": 2_000.0,
            "maximum_daily_loss": 1_000.0,
            "realized_daily_loss": 0.0,
            "bid_price": 99.0,
            "ask_price": 101.0,
        },
    )

    assert len(calls) == 1
    assert calls[0][2] == "BLOCKED"
    assert result.action == "WAIT"
    assert result.contract is None
    assert result.quantity == 0
    assert result.capital_required == 0.0
    assert result.maximum_loss == 0.0


def test_stale_selected_candidate_returns_wait():
    decision = selected_decision()
    evaluated_at = (
        decision.completed_at
        + __import__("datetime").timedelta(seconds=181)
    )
    capital = make_input(
        selected_market=decision.selected_market,
        evaluated_at=evaluated_at,
    )
    calls = []

    def planner(bridge, authority):
        calls.append(bridge.action)
        blocked = ready_planning(
            replace(
                bridge,
                action="CALL",
                planning_allowed=True,
                blockers=(),
            )
        )
        return replace(
            blocked,
            status="BLOCKED",
            blockers=("BRIDGE_NOT_READY",),
            decision_reasons=(),
        )

    result = run_capital_safe_recommendation_cycle(
        bridge_result_id="bridge-stale-runtime",
        authority_result_id="authority-stale-runtime",
        recommendation_id="recommendation-stale-runtime",
        decision=decision,
        capital_risk_input=capital,
        maximum_candidate_age_seconds=180.0,
        certified_p6_planner=planner,
    )

    assert calls == ["WAIT"]
    assert result.action == "WAIT"
    assert "SELECTED_CANDIDATE_STALE" in result.blockers


def test_capital_input_for_nonselected_market_is_rejected_before_p6():
    decision = selected_decision(selected_symbol="NIFTY")
    capital = make_input(
        selected_market=("SENSEX", "BSE"),
        evaluated_at=decision.completed_at,
    )
    calls = []

    with pytest.raises(ValueError, match="selected market"):
        run_capital_safe_recommendation_cycle(
            bridge_result_id="bridge-mismatch",
            authority_result_id="authority-mismatch",
            recommendation_id="recommendation-mismatch",
            decision=decision,
            capital_risk_input=capital,
            maximum_candidate_age_seconds=180.0,
            certified_p6_planner=lambda bridge, authority: (
                calls.append(True)
            ),
        )
    assert calls == []


def test_planner_must_return_exact_integrated_result():
    decision = selected_decision()
    capital = make_input(
        selected_market=decision.selected_market,
        evaluated_at=decision.completed_at,
    )

    with pytest.raises(TypeError, match="exact integrated result"):
        run_capital_safe_recommendation_cycle(
            bridge_result_id="bridge-type",
            authority_result_id="authority-type",
            recommendation_id="recommendation-type",
            decision=decision,
            capital_risk_input=capital,
            maximum_candidate_age_seconds=180.0,
            certified_p6_planner=lambda bridge, authority: {},
        )


def test_runtime_has_no_broker_order_dashboard_or_four_market_dependency():
    source = Path(
        "services/trade_planning/"
        "capital_safe_recommendation_runtime.py"
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
        "live_execution",
        "four_market",
        "market_ranking_engine",
        "opportunity_ranking",
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
