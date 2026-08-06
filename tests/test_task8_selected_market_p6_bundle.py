from dataclasses import replace
from datetime import date

import pytest

from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from services.certification.task8_selected_market_p6_bundle import (
    build_task8_selected_market_p6_bundle,
    classify_task8_expiry,
    derive_task8_moneyness_steps,
    derive_task8_strike_interval,
)
from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)

from test_market_analysis_candidate_v1 import (
    build as build_candidate,
)
from test_task8_parent_typed_candidate_certification import (
    NOW,
    captured,
    cycle,
)


def test_unambiguous_strike_interval_and_moneyness_steps():
    interval = derive_task8_strike_interval(
        strikes=(
            24900.0,
            24950.0,
            25000.0,
            25050.0,
        ),
    )

    assert interval == 50.0

    assert derive_task8_moneyness_steps(
        strike=25000.0,
        spot_price=25000.0,
        strike_interval=interval,
    ) == 0

    assert derive_task8_moneyness_steps(
        strike=25100.0,
        spot_price=25000.0,
        strike_interval=interval,
    ) == 2


def test_ambiguous_strike_interval_fails_closed():
    with pytest.raises(
        ValueError,
        match="ambiguous canonical strike interval",
    ):
        derive_task8_strike_interval(
            strikes=(
                24900.0,
                24950.0,
                25025.0,
            ),
        )


def test_non_integral_moneyness_fails_closed():
    with pytest.raises(
        ValueError,
        match="non-integral moneyness steps",
    ):
        derive_task8_moneyness_steps(
            strike=25025.0,
            spot_price=25000.0,
            strike_interval=50.0,
        )


def test_expiry_category_is_calendar_deterministic():
    assert classify_task8_expiry(
        date(2026, 8, 6)
    ) == "WEEKLY"

    assert classify_task8_expiry(
        date(2026, 8, 27)
    ) == "MONTHLY"

    assert classify_task8_expiry(
        date(2026, 8, 25)
    ) == "MONTHLY"


def _real_selected_bundle_inputs():
    capture = captured(
        "NIFTY",
        "NSE",
        25000.0,
        complete_options=True,
    )

    selected_cycle = cycle(
        "NIFTY",
        "NSE",
        capture,
    )

    evaluation = evaluate_captured_certified_market_candidate(
        captured_evidence=capture,
        session_validation=(
            selected_cycle.session_validation
        ),
        policy_source=LiveCandidatePolicySourceV1(
            "BULLISH",
            "ELIGIBLE",
            80.0,
            80.0,
            reasons=(
                "TASK8 CERTIFIED SELECTION",
            ),
        ),
        parent_cycle_id="task8-real-parent",
        candidate_id="task8-real-candidate",
        observation_id=selected_cycle.observation_id,
        engines=(
            build_default_live_canonical_evidence_engines()
        ),
    )

    fixture_candidate = build_candidate(
        underlying_symbol="NIFTY",
    )

    ranking = replace(
        evaluation.evidence.contract_ranking,
        ranking_status="RANKED",
        warnings=(),
    )

    technical = replace(
        fixture_candidate.technical,
        created_at=NOW,
        status="READY",
        aggregate_bias="BULLISH",
        aggregate_strength=0.8,
        blockers=(),
        warnings=(),
    )

    option_chain = replace(
        fixture_candidate.option_chain,
        created_at=NOW,
        intelligence_status="READY",
        aggregate_bias="BULLISH",
        aggregate_strength=0.8,
        blockers=(),
        warnings=(),
    )

    regime = replace(
        fixture_candidate.regime,
        created_at=NOW,
    )

    evidence = replace(
        evaluation.evidence,
        technical=technical,
        option_chain=option_chain,
        contract_ranking=ranking,
        regime=regime,
        session=selected_cycle.session_validation,
    )

    candidate = replace(
        fixture_candidate,
        candidate_id="task8-real-candidate",
        observation_id=selected_cycle.observation_id,
        requested_at=selected_cycle.cycle_requested_at,
        market_timestamp=selected_cycle.market_timestamp,
        received_at=selected_cycle.received_at,
        session=selected_cycle.session_validation,
        technical=technical,
        option_chain=option_chain,
        option_contract_eligibility=ranking,
        regime=regime,
        direction="BULLISH",
        eligibility="ELIGIBLE",
        confidence=80.0,
        score=80.0,
        blockers=(),
        contradictions=(),
        warnings=(),
        reasons=(
            "TASK8 CERTIFIED SELECTION",
        ),
    )

    evaluation = replace(
        evaluation,
        evidence=evidence,
        candidate=candidate,
    )

    bridge = SelectedMarketPlanningBridgeResultV1(
        bridge_result_id="task8-real-bridge",
        parent_cycle_id="task8-real-parent",
        parent_decision_id="task8-real-decision",
        evaluated_at=NOW,
        action="CALL",
        planning_allowed=True,
        selected_market=(
            "NIFTY",
            "NSE",
        ),
        selected_candidate=candidate,
        selected_child_result_id=(
            "task8-real-nifty-child"
        ),
        selected_child_action="CALL",
        candidate_id=candidate.candidate_id,
        observation_id=candidate.observation_id,
        direction="BULLISH",
        confidence=candidate.confidence,
        score=candidate.score,
        losing_market=(
            "SENSEX",
            "BSE",
        ),
        losing_outcome_reason="LOWER_RANK",
        losing_rationale=(
            "LOWER_SCORE",
        ),
        reasons=candidate.reasons,
        invalidation_conditions=(
            candidate.invalidation_conditions
        ),
        warnings=candidate.warnings,
    )

    return (
        bridge,
        selected_cycle,
        evaluation,
    )


def test_canonical_trade_plan_exposes_selected_direction():
    (
        bridge,
        selected_cycle,
        evaluation,
    ) = _real_selected_bundle_inputs()

    bundle = build_task8_selected_market_p6_bundle(
        bridge=bridge,
        cycle=selected_cycle,
        evaluation=evaluation,
        available_capital=10000.0,
        evaluated_at=NOW,
    )

    assert (
        bundle.capital_quantity_input
        .canonical_trade_plan_input
        .direction
        == "BULLISH"
    )


def test_real_retained_evaluation_constructs_exact_p6_bundle():
    (
        bridge,
        selected_cycle,
        evaluation,
    ) = _real_selected_bundle_inputs()

    bundle = build_task8_selected_market_p6_bundle(
        bridge=bridge,
        cycle=selected_cycle,
        evaluation=evaluation,
        available_capital=10000.0,
        evaluated_at=NOW,
    )

    assert type(bundle) is CertifiedP6InputBundleV1
    assert bundle.execution_mode == "PAPER"
    assert bundle.live_execution_eligible is False

    assert (
        bundle.option_selection_input.option_ranking_result
        is evaluation.evidence.contract_ranking
    )

    assert (
        bundle.option_selection_input.underlying_symbol,
        bundle.option_selection_input.exchange,
        bundle.option_selection_input.direction,
        bundle.option_selection_input.option_right,
    ) == (
        "NIFTY",
        "NSE",
        "BULLISH",
        "CALL",
    )

    assert (
        bundle.capital_quantity_input
        .canonical_trade_plan_input
        .available_capital
        == 10000.0
    )



def test_ten_thousand_capital_returns_safe_no_size():
    (
        bridge,
        selected_cycle,
        evaluation,
    ) = _real_selected_bundle_inputs()

    bundle = build_task8_selected_market_p6_bundle(
        bridge=bridge,
        cycle=selected_cycle,
        evaluation=evaluation,
        available_capital=10000.0,
        evaluated_at=NOW,
    )

    from services.trade_planning.capital_quantity_planner import (
        plan_capital_quantity,
    )

    result = plan_capital_quantity(
        bundle.capital_quantity_input
    )

    assert result.status == "NO_SIZE"
    assert result.planned_lot_count == 0
    assert result.planned_quantity == 0
    assert result.estimated_premium_outlay == 0.0
    assert result.estimated_risk_amount == 0.0
    assert result.live_execution_eligible is False
