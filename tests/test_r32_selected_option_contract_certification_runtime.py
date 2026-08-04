from dataclasses import replace
from pathlib import Path

import pytest

from services.contracts.selected_option_contract_certification_policy_v1 import (
    SelectedOptionContractCertificationPolicyV1,
)
from services.paper_orchestration.selected_option_contract_certification_runtime import (
    execute_selected_option_contract_certification,
)
from test_selected_option_contract_certifier import ready_bridge


def policy():
    return SelectedOptionContractCertificationPolicyV1(
        maximum_ranking_age_seconds=180.0,
        maximum_contract_age_seconds=180.0,
        maximum_quote_age_seconds=60.0,
        maximum_spread_fraction=0.03,
        minimum_liquidity_score=0.5,
        minimum_open_interest=1000.0,
        minimum_volume=500.0,
    )


def execute(value=None):
    bridge = value or ready_bridge()
    return execute_selected_option_contract_certification(
        certification_result_id="r32-certification",
        bridge=bridge,
        policy=policy(),
        evaluated_at=bridge.evaluated_at,
    )


@pytest.mark.parametrize(
    ("symbol", "direction", "right"),
    (
        ("NIFTY", "BULLISH", "CALL"),
        ("NIFTY", "BEARISH", "PUT"),
        ("SENSEX", "BULLISH", "CALL"),
        ("SENSEX", "BEARISH", "PUT"),
    ),
)
def test_runtime_certifies_exact_selected_contract(
    symbol,
    direction,
    right,
):
    bridge = ready_bridge(symbol, direction)
    result = execute(bridge)

    assert result.status == "CERTIFIED"
    assert result.selected_market == (
        symbol,
        bridge.selected_market[1],
    )
    assert result.direction == direction
    assert result.option_right == right
    assert result.candidate_id == bridge.candidate_id
    assert result.observation_id == bridge.observation_id
    assert result.selected_contract is (
        bridge.selected_candidate
        .option_contract_eligibility
        .selected_candidate
        .contract
    )
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False


def test_runtime_uses_only_bridge_retained_ranking():
    bridge = ready_bridge()
    ranking = bridge.selected_candidate.option_contract_eligibility

    result = execute(bridge)

    assert result.ranking_result_id == ranking.ranking_id
    assert result.universe_id == ranking.universe_id
    assert result.contract_id == (
        ranking.selected_candidate.contract.contract_id
    )


def test_non_actionable_bridge_fails_closed():
    bridge = ready_bridge()
    blocked = replace(
        bridge,
        action="WAIT",
        selected_child_action="WAIT",
        planning_allowed=False,
        blockers=("SELECTED_CANDIDATE_STALE",),
    )

    result = execute(blocked)

    assert result.status == "BLOCKED"
    assert result.selected_contract is None
    assert result.contract_id is None
    assert "PLANNING_HANDOFF_NOT_ALLOWED" in result.blockers


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("maximum_ranking_age_seconds", 0.0),
        ("maximum_contract_age_seconds", -1.0),
        ("maximum_quote_age_seconds", float("inf")),
        ("maximum_spread_fraction", 1.01),
        ("minimum_liquidity_score", -0.01),
        ("minimum_open_interest", -1.0),
        ("minimum_volume", -1.0),
    ),
)
def test_policy_rejects_unsafe_thresholds(name, value):
    with pytest.raises(ValueError, match=name):
        replace(
            policy(),
            **{name: value},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("execution_mode", "LIVE"),
        ("live_execution_eligible", True),
        ("broker_order_submission", True),
    ),
)
def test_policy_rejects_live_capability(field, value):
    with pytest.raises(
        ValueError,
        match="PAPER-only certification policy",
    ):
        replace(
            policy(),
            **{field: value},
        )


def test_runtime_rejects_wrong_exact_dependencies():
    bridge = ready_bridge()

    with pytest.raises(TypeError, match="bridge"):
        execute_selected_option_contract_certification(
            certification_result_id="r32",
            bridge=object(),
            policy=policy(),
            evaluated_at=bridge.evaluated_at,
        )

    with pytest.raises(TypeError, match="policy"):
        execute_selected_option_contract_certification(
            certification_result_id="r32",
            bridge=bridge,
            policy=object(),
            evaluated_at=bridge.evaluated_at,
        )


def test_runtime_has_no_provider_broker_or_execution_dependency():
    source = Path(
        "services/paper_orchestration/"
        "selected_option_contract_certification_runtime.py"
    ).read_text(encoding="utf-8")

    for token in (
        "provider",
        "place_order(",
        "submit_order(",
        "requests.",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "random.",
    ):
        assert token not in source
