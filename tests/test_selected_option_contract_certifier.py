"""Task 3B exact option-contract certification."""
from dataclasses import replace
from datetime import timedelta
import ast
from pathlib import Path

import pytest

from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.trade_planning.selected_option_contract_certifier import (
    certify_selected_option_contract,
)
from test_selected_market_planning_bridge import bridge, selected_decision


def ready_bridge(symbol="NIFTY", direction="BULLISH", **contract_changes):
    value = bridge(
        selected_decision(
            selected_symbol=symbol,
            selected_changes={"direction": direction},
        )
    )
    market_candidate = value.selected_candidate
    ranking = market_candidate.option_contract_eligibility
    ranked = ranking.selected_candidate
    right = "CALL" if direction == "BULLISH" else "PUT"

    contract_values = {
        "instrument_token": f"token-{symbol}",
        "option_type": right,
        "last_price": 100.0,
        "bid_price": 99.0,
        "ask_price": 101.0,
        "open_interest": 2000.0,
        "volume": 1000.0,
        "market_timestamp": value.evaluated_at,
    }
    contract_values.update(contract_changes)
    contract = replace(ranked.contract, **contract_values)

    spread_percent = None
    if (
        contract.bid_price is not None
        and contract.ask_price is not None
        and contract.bid_price > 0
        and contract.ask_price > 0
        and contract.ask_price >= contract.bid_price
    ):
        midpoint = (contract.bid_price + contract.ask_price) / 2.0
        spread_percent = (
            (contract.ask_price - contract.bid_price)
            / midpoint
            * 100.0
        )

    ranked = replace(
        ranked,
        contract=contract,
        spread_percent=spread_percent,
        liquidity_score=0.8,
    )
    ranking = replace(
        ranking,
        ranked_at=value.evaluated_at,
        directional_bias=direction,
        required_option_type=right,
        ranked_candidates=(ranked,),
    )
    market_candidate = replace(
        market_candidate,
        option_contract_eligibility=ranking,
    )
    return replace(
        value,
        selected_candidate=market_candidate,
    )


def certify(value, **changes):
    defaults = dict(
        certification_result_id="cert-1",
        bridge=value,
        evaluated_at=value.evaluated_at,
        maximum_ranking_age_seconds=180.0,
        maximum_contract_age_seconds=180.0,
        maximum_quote_age_seconds=60.0,
        maximum_spread_fraction=0.03,
        minimum_liquidity_score=0.5,
        minimum_open_interest=1000.0,
        minimum_volume=500.0,
    )
    defaults.update(changes)
    return certify_selected_option_contract(**defaults)


@pytest.mark.parametrize(
    ("symbol", "direction", "right"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("NIFTY", "BEARISH", "PUT"),
        ("SENSEX", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_exact_contract_is_certified(symbol, direction, right):
    result = certify(ready_bridge(symbol, direction))

    assert result.status == "CERTIFIED"
    assert result.selected_market[0] == symbol
    assert result.direction == direction
    assert result.option_right == right
    assert result.selected_rank == 1
    assert result.instrument_token == f"token-{symbol}"
    assert result.premium == 100.0
    assert result.bid_price == 99.0
    assert result.ask_price == 101.0
    assert result.spread_value == 2.0
    assert result.spread_fraction == pytest.approx(0.02)
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False


def test_full_trace_identity_is_preserved():
    value = ready_bridge()
    result = certify(value)
    ranking = value.selected_candidate.option_contract_eligibility

    assert result.parent_cycle_id == value.parent_cycle_id
    assert result.parent_decision_id == value.parent_decision_id
    assert result.bridge_result_id == value.bridge_result_id
    assert result.selected_child_result_id == value.selected_child_result_id
    assert result.candidate_id == value.candidate_id
    assert result.observation_id == value.observation_id
    assert result.ranking_result_id == ranking.ranking_id
    assert result.universe_id == ranking.universe_id


@pytest.mark.parametrize(
    ("changes", "blocker"),
    (
        ({"instrument_token": None}, "OPTION_CONTRACT_TOKEN_UNAVAILABLE"),
        ({"last_price": None}, "OPTION_PREMIUM_UNAVAILABLE"),
        ({"bid_price": None}, "OPTION_BID_UNAVAILABLE"),
        ({"ask_price": None}, "OPTION_ASK_UNAVAILABLE"),
        ({"bid_price": 101.0, "ask_price": 99.0}, "OPTION_QUOTE_CROSSED"),
        ({"bid_price": 90.0, "ask_price": 110.0}, "OPTION_SPREAD_EXCEEDS_LIMIT"),
        ({"open_interest": None}, "OPTION_OPEN_INTEREST_UNAVAILABLE"),
        ({"open_interest": 999.0}, "OPTION_OPEN_INTEREST_BELOW_MINIMUM"),
        ({"volume": None}, "OPTION_VOLUME_UNAVAILABLE"),
        ({"volume": 499.0}, "OPTION_VOLUME_BELOW_MINIMUM"),
        ({"tradable": False}, "OPTION_CONTRACT_NOT_TRADABLE"),
    ),
)
def test_contract_and_quote_fail_closed(changes, blocker):
    result = certify(ready_bridge(**changes))
    assert result.status == "BLOCKED"
    assert blocker in result.blockers
    assert result.selected_contract is None
    assert result.contract_id is None


def test_low_liquidity_fails_closed():
    value = ready_bridge()
    ranking = value.selected_candidate.option_contract_eligibility
    ranked = replace(ranking.selected_candidate, liquidity_score=0.49)
    ranking = replace(ranking, ranked_candidates=(ranked,))
    candidate = replace(value.selected_candidate, option_contract_eligibility=ranking)
    value = replace(value, selected_candidate=candidate)

    result = certify(value)
    assert result.status == "BLOCKED"
    assert "OPTION_LIQUIDITY_BELOW_MINIMUM" in result.blockers


@pytest.mark.parametrize(
    ("seconds", "blocker"),
    (
        (181, "OPTION_RANKING_STALE"),
        (-1, "OPTION_RANKING_TIMESTAMP_IN_FUTURE"),
    ),
)
def test_ranking_freshness(seconds, blocker):
    value = ready_bridge()
    ranking = value.selected_candidate.option_contract_eligibility
    ranking = replace(
        ranking,
        ranked_at=value.evaluated_at - timedelta(seconds=seconds),
    )
    candidate = replace(value.selected_candidate, option_contract_eligibility=ranking)
    value = replace(value, selected_candidate=candidate)

    result = certify(value)
    assert blocker in result.blockers


@pytest.mark.parametrize(
    ("seconds", "blocker"),
    (
        (61, "OPTION_QUOTE_STALE"),
        (181, "OPTION_CONTRACT_STALE"),
        (-1, "OPTION_CONTRACT_TIMESTAMP_IN_FUTURE"),
    ),
)
def test_contract_and_quote_freshness(seconds, blocker):
    value = ready_bridge(
        market_timestamp=(
            ready_bridge().evaluated_at - timedelta(seconds=seconds)
        )
    )
    result = certify(value)
    assert blocker in result.blockers


def test_wait_and_no_trade_handoffs_are_blocked():
    stale = ready_bridge()
    stale = replace(
        stale,
        action="WAIT",
        selected_child_action="WAIT",
        planning_allowed=False,
        blockers=("STALE",),
    )
    result = certify(stale)
    assert result.status == "BLOCKED"
    assert "PLANNING_HANDOFF_NOT_ALLOWED" in result.blockers

    base = ready_bridge()
    no_trade = replace(
        base,
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
    result = certify(no_trade)
    assert result.status == "BLOCKED"
    assert "PLANNING_HANDOFF_NOT_ALLOWED" in result.blockers


def test_missing_ranking_is_unavailable():
    value = ready_bridge()
    object.__setattr__(
        value.selected_candidate,
        "option_contract_eligibility",
        None,
    )

    result = certify(value)
    assert result.status == "UNAVAILABLE"
    assert result.blockers == ("OPTION_RANKING_UNAVAILABLE",)


def test_blocked_ranking_preserves_stable_reason():
    value = ready_bridge()
    ranking = value.selected_candidate.option_contract_eligibility
    ranking = OptionContractRankingResultV1(
        ranking_id=ranking.ranking_id,
        ranked_at=value.evaluated_at,
        universe_id=ranking.universe_id,
        intelligence_result_id=ranking.intelligence_result_id,
        underlying_symbol=ranking.underlying_symbol,
        exchange=ranking.exchange,
        directional_bias=ranking.directional_bias,
        required_option_type=ranking.required_option_type,
        ranking_status="BLOCKED",
        blockers=("CHAIN_BLOCKED",),
    )
    object.__setattr__(
        value.selected_candidate,
        "option_contract_eligibility",
        ranking,
    )

    result = certify(value)
    assert result.status == "UNAVAILABLE"
    assert result.blockers == (
        "OPTION_RANKING_BLOCKED",
        "CHAIN_BLOCKED",
        "OPTION_CONTRACT_UNAVAILABLE",
    )


def test_inputs_are_not_mutated_and_output_is_deterministic():
    value = ready_bridge()
    before = (
        value.selected_candidate.option_contract_eligibility.to_json(),
        value.selected_candidate.option_contract_eligibility.selected_candidate.to_dict(),
    )
    first = certify(value)
    second = certify(value)

    assert first.to_json() == second.to_json()
    assert before == (
        value.selected_candidate.option_contract_eligibility.to_json(),
        value.selected_candidate.option_contract_eligibility.selected_candidate.to_dict(),
    )


def test_certifier_has_no_provider_capital_lifecycle_persistence_or_broker_dependencies():
    source = Path(
        "services/trade_planning/selected_option_contract_certifier.py"
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
        "capital",
        "paper_trading",
        "paper_portfolio",
        "persistence",
        "repository",
        "requests",
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
