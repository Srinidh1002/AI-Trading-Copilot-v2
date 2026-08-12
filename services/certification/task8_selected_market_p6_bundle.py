"""Build an exact selected-market P6 bundle from retained Task 8 evidence.

This module is provider-free. It accepts only the authoritative selected-market
bridge, its exact cycle input, and the exact live evaluation retained while the
two-market parent was evaluated.

No quote, candle, option-chain, broker, execution, or external-context reader
is called here.
"""
from __future__ import annotations

import calendar
import math
from datetime import date, datetime
from typing import Iterable

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.contracts.canonical_trade_plan_input_v1 import (
    CanonicalTradePlanInputV1,
)
from services.contracts.capital_quantity_planning_input_v1 import (
    CapitalQuantityPlanningInputV1,
)
from services.contracts.capital_quantity_planning_policy_v1 import (
    CapitalQuantityPlanningPolicyV1,
)
from services.contracts.capital_quantity_trading_cost_policy_v1 import (
    CapitalQuantityTradingCostPolicyV1,
)
from services.contracts.capital_quantity_trading_cost_evidence_v1 import (
    CapitalQuantityTradingCostEvidenceV1,
)
from services.contracts.entry_zone_evaluation_input_v1 import (
    EntryZoneEvaluationInputV1,
)
from services.contracts.entry_zone_evaluation_result_v1 import (
    EntryZoneEvaluationResultV1,
)
from services.contracts.final_decision_v1 import (
    AuthorizationStatus,
    DataHealthSummary,
    ExecutionStatus,
    FinalDecisionV1,
    RiskSummary,
)
from services.contracts.market_opportunity_candidate_v1 import (
    MarketOpportunityCandidateV1,
)
from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_eligibility_evidence_v1 import (
    OptionContractEligibilityEvidenceV1,
)
from services.contracts.option_contract_selection_input_v1 import (
    OptionContractSelectionInputV1,
)
from services.contracts.option_contract_selection_result_v1 import (
    OptionContractSelectionResultV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.contracts.stop_loss_evaluation_input_v1 import (
    StopLossEvaluationInputV1,
)
from services.contracts.stop_loss_evaluation_result_v1 import (
    StopLossEvaluationResultV1,
)
from services.contracts.three_target_evaluation_input_v1 import (
    ThreeTargetEvaluationInputV1,
)
from services.contracts.three_target_evaluation_result_v1 import (
    ThreeTargetEvaluationResultV1,
)
from services.contracts.trade_plan_target_v1 import (
    TradePlanTargetV1,
)
from services.contracts.trade_planning_policy_v1 import (
    TradePlanningPolicyV1,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)
from services.trade_opportunity.integration import (
    build_canonical_trade_opportunity,
)


_SUPPORTED_MARKETS = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}
_DIRECTION_RIGHT = {
    "BULLISH": "CALL",
    "BEARISH": "PUT",
}
_DIRECTION_ACTION = {
    "BULLISH": "BUY",
    "BEARISH": "SELL",
}
_RIGHT_LEGACY = {
    "CALL": "CE",
    "PUT": "PE",
}

_MAXIMUM_RISK_FRACTION = 0.01
_MAXIMUM_CAPITAL_UTILIZATION_FRACTION = 0.80
_MAXIMUM_PLANNED_LOTS = 3
_MAXIMUM_SPREAD_FRACTION = 0.10
_ENTRY_TOLERANCE_FRACTION = 0.01
_MAXIMUM_CHASE_FRACTION = 0.02
_STOP_FRACTION = 0.10


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _positive(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(f"{name} must be positive and finite")
    return float(value)


def _unit_score(value: object, name: str) -> float:
    numeric = _positive(value, name)
    if numeric <= 1.0:
        return numeric
    if numeric <= 100.0:
        return numeric / 100.0
    raise ValueError(f"{name} exceeds supported score range")


def classify_task8_expiry(expiry: date) -> str:
    """Classify the final occurrence of an expiry weekday as MONTHLY."""

    if isinstance(expiry, datetime) or type(expiry) is not date:
        raise TypeError("expiry must be an exact date")

    final_day = calendar.monthrange(
        expiry.year,
        expiry.month,
    )[1]
    candidate = expiry.day + 7

    return (
        "MONTHLY"
        if candidate > final_day
        else "WEEKLY"
    )


def derive_task8_strike_interval(
    *,
    strikes: Iterable[float],
    tolerance: float = 1e-9,
) -> float:
    """Return one unambiguous positive interval or fail closed."""

    if (
        type(tolerance) not in (int, float)
        or isinstance(tolerance, bool)
        or not math.isfinite(tolerance)
        or tolerance <= 0.0
    ):
        raise ValueError("tolerance")

    normalized = sorted(
        {
            _positive(value, "strike")
            for value in strikes
        }
    )
    if len(normalized) < 2:
        raise ValueError(
            "canonical strike interval requires at least two strikes"
        )

    differences = tuple(
        right - left
        for left, right in zip(
            normalized,
            normalized[1:],
        )
    )
    interval = differences[0]

    if interval <= 0.0:
        raise ValueError("canonical strike interval is not positive")

    if any(
        not math.isclose(
            difference,
            interval,
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
        for difference in differences[1:]
    ):
        raise ValueError("ambiguous canonical strike interval")

    return float(interval)


def derive_task8_moneyness_steps(
    *,
    strike: float,
    spot_price: float,
    strike_interval: float,
    tolerance: float = 1e-9,
) -> int:
    """Derive integral strike steps from the retained option universe."""

    strike_value = _positive(strike, "strike")
    spot_value = _positive(spot_price, "spot_price")
    interval = _positive(
        strike_interval,
        "strike_interval",
    )

    raw_steps = abs(
        strike_value - spot_value
    ) / interval
    rounded = round(raw_steps)

    if not math.isclose(
        raw_steps,
        rounded,
        rel_tol=tolerance,
        abs_tol=tolerance,
    ):
        raise ValueError("non-integral moneyness steps")

    return int(rounded)


def _validate_selected_inputs(
    *,
    bridge: SelectedMarketPlanningBridgeResultV1,
    cycle: PaperOrchestrationCycleInputV1,
    evaluation: LiveMarketCandidateEvaluationResultV1,
    evaluated_at: datetime,
) -> tuple[str, str, str, str]:
    if type(bridge) is not SelectedMarketPlanningBridgeResultV1:
        raise TypeError("bridge")
    if type(cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("cycle")
    if (
        type(evaluation)
        is not LiveMarketCandidateEvaluationResultV1
    ):
        raise TypeError("evaluation")

    now = _aware(evaluated_at, "evaluated_at")

    if not bridge.planning_allowed:
        raise ValueError("selected bridge does not allow planning")
    if bridge.action not in {"CALL", "PUT"}:
        raise ValueError("selected bridge is not directional")
    if bridge.direction not in _DIRECTION_RIGHT:
        raise ValueError("selected bridge direction is unsupported")
    if _DIRECTION_RIGHT[bridge.direction] != bridge.action:
        raise ValueError("selected bridge action/direction mismatch")

    market = (
        cycle.underlying_symbol,
        cycle.exchange,
    )
    if market not in _SUPPORTED_MARKETS:
        raise ValueError("unsupported Task 8 market")
    if bridge.selected_market != market:
        raise ValueError("selected bridge/cycle market mismatch")
    if bridge.observation_id != cycle.observation_id:
        raise ValueError("selected bridge/cycle observation mismatch")

    candidate = evaluation.candidate
    candidate_identity = (
        candidate.underlying_symbol,
        candidate.exchange,
        candidate.observation_id,
    )
    expected_identity = (
        cycle.underlying_symbol,
        cycle.exchange,
        cycle.observation_id,
    )
    if candidate_identity != expected_identity:
        raise ValueError("retained evaluation identity mismatch")
    if bridge.candidate_id != candidate.candidate_id:
        raise ValueError("selected candidate identity mismatch")
    if bridge.direction != candidate.direction:
        raise ValueError("selected candidate direction mismatch")
    if candidate.eligibility != "ELIGIBLE":
        raise ValueError("selected candidate is not eligible")
    if candidate.blockers:
        raise ValueError("selected candidate contains blockers")
    if candidate.contradictions:
        raise ValueError("selected candidate is conflicting")

    if now < candidate.market_timestamp:
        raise ValueError("selected candidate timestamp is in the future")

    ranking = evaluation.evidence.contract_ranking
    if ranking is not candidate.option_contract_eligibility:
        raise ValueError(
            "retained ranking is not the selected candidate ranking"
        )
    if ranking.ranking_status not in {
        "RANKED",
        "RANKED_WITH_WARNINGS",
    }:
        raise ValueError("selected contract ranking is not ready")
    if (
        ranking.underlying_symbol,
        ranking.exchange,
        ranking.directional_bias,
        ranking.required_option_type,
    ) != (
        cycle.underlying_symbol,
        cycle.exchange,
        bridge.direction,
        bridge.action,
    ):
        raise ValueError("selected ranking identity mismatch")
    if not ranking.ranked_candidates:
        raise ValueError("selected ranking has no ranked candidates")

    universe = evaluation.options.universe
    if universe is None:
        raise ValueError("retained option universe is unavailable")
    if not universe.trusted:
        raise ValueError("retained option universe is untrusted")
    if (
        universe.underlying_symbol,
        universe.exchange,
    ) != market:
        raise ValueError("retained option universe identity mismatch")

    return (
        market[0],
        market[1],
        bridge.direction,
        bridge.action,
    )


def _reference_price(
    candidate: OptionContractCandidateV1,
) -> tuple[str, float, float | None]:
    contract = candidate.contract
    bid = contract.bid_price
    ask = contract.ask_price
    last = contract.last_price

    if (
        bid is not None
        and ask is not None
        and bid > 0.0
        and ask >= bid
    ):
        midpoint = (bid + ask) / 2.0
        spread = (
            (ask - bid) / midpoint
            if midpoint > 0.0
            else None
        )
        return "OPTION_MID", midpoint, spread

    if ask is not None and ask > 0.0:
        return "OPTION_ASK", float(ask), None

    if last is not None and last > 0.0:
        return "LAST_TRADED_PRICE", float(last), None

    raise ValueError("selected contract has no usable retained price")


def _planning_policy(
    *,
    policy_id: str,
) -> TradePlanningPolicyV1:
    return TradePlanningPolicyV1(
        policy_id=policy_id,
        policy_name="TASK8_SELECTED_MARKET_PAPER",
        policy_version="1",
        maximum_risk_fraction=_MAXIMUM_RISK_FRACTION,
        minimum_risk_amount=None,
        maximum_risk_amount=None,
        stop_loss_method="PREMIUM_FRACTION",
        stop_loss_atr_multiplier=None,
        stop_loss_premium_fraction=_STOP_FRACTION,
        stop_loss_structure_buffer_fraction=0.01,
        minimum_stop_distance_fraction=0.01,
        maximum_stop_distance_fraction=0.20,
        entry_reference_method="OPTION_MID",
        entry_tolerance_below_fraction=(
            _ENTRY_TOLERANCE_FRACTION
        ),
        entry_tolerance_above_fraction=(
            _ENTRY_TOLERANCE_FRACTION
        ),
        maximum_chase_fraction=_MAXIMUM_CHASE_FRACTION,
        require_limit_entry=True,
        minimum_reward_to_risk_t1=1.0,
        minimum_reward_to_risk_t2=1.5,
        minimum_reward_to_risk_t3=2.0,
        target_method="RISK_MULTIPLE",
        target_1_multiplier=1.0,
        target_2_multiplier=1.5,
        target_3_multiplier=2.0,
        target_1_allocation_fraction=0.30,
        target_2_allocation_fraction=0.40,
        target_3_allocation_fraction=0.30,
        maximum_entry_premium=None,
        maximum_spread_fraction=_MAXIMUM_SPREAD_FRACTION,
        minimum_open_interest=0,
        minimum_volume=0,
        minimum_liquidity_score=None,
        allowed_moneyness=("ATM",),
        maximum_moneyness_steps=0,
        minimum_lot_count=1,
        maximum_lot_count=_MAXIMUM_PLANNED_LOTS,
        allow_partial_target_lots=True,
        minimum_lots_for_three_targets=3,
        insufficient_target_lot_behavior="ALLOW",
        estimated_entry_slippage_fraction=0.005,
        estimated_exit_slippage_fraction=0.005,
        estimated_brokerage_per_order=20.0,
        estimated_other_charges_fraction=0.001,
        allow_weekly_expiry=True,
        allow_monthly_expiry=True,
        allow_same_day_expiry=False,
        minimum_days_to_expiry=1,
        maximum_days_to_expiry=None,
        block_new_entries_during_high_impact_events=True,
        event_pre_buffer_minutes=0,
        event_post_buffer_minutes=0,
        blocked_event_categories=(),
        require_market_open=True,
        require_new_entries_allowed=True,
        require_paper_execution_allowed=True,
        block_special_sessions=False,
        minimum_minutes_after_open=0,
        minimum_minutes_before_close=0,
        minimum_opportunity_confidence=0.50,
        minimum_option_confidence=0.50,
        minimum_plan_confidence=0.50,
        warnings_block_planning=False,
    )


def build_task8_selected_market_p6_bundle(
    *,
    bridge: SelectedMarketPlanningBridgeResultV1,
    cycle: PaperOrchestrationCycleInputV1,
    evaluation: LiveMarketCandidateEvaluationResultV1,
    available_capital: float,
    evaluated_at: datetime,
) -> CertifiedP6InputBundleV1:
    """Build the exact P6 input bundle for one authoritative selected child."""

    symbol, exchange, direction, option_right = (
        _validate_selected_inputs(
            bridge=bridge,
            cycle=cycle,
            evaluation=evaluation,
            evaluated_at=evaluated_at,
        )
    )
    now = _aware(evaluated_at, "evaluated_at")
    capital = _positive(
        available_capital,
        "available_capital",
    )

    evidence = evaluation.evidence
    ranking = evidence.contract_ranking
    universe = evaluation.options.universe
    if universe is None:
        raise ValueError("retained option universe is unavailable")

    selected_candidate = ranking.ranked_candidates[0]
    selected_contract = selected_candidate.contract

    same_expiry_strikes = tuple(
        contract.strike
        for contract in universe.contracts
        if (
            contract.expiry_date
            == selected_contract.expiry_date
            and contract.option_type == option_right
        )
    )
    strike_interval = derive_task8_strike_interval(
        strikes=same_expiry_strikes,
    )
    moneyness_steps = derive_task8_moneyness_steps(
        strike=selected_contract.strike,
        spot_price=universe.spot_price,
        strike_interval=strike_interval,
    )
    if moneyness_steps != 0:
        raise ValueError("selected contract is not ATM")

    days_to_expiry = (
        selected_contract.expiry_date - now.date()
    ).days
    if days_to_expiry < 1:
        raise ValueError("same-day or expired contract is blocked")

    expiry_category = classify_task8_expiry(
        selected_contract.expiry_date
    )
    reference_method, reference_price, spread_fraction = (
        _reference_price(selected_candidate)
    )
    if (
        spread_fraction is not None
        and spread_fraction > _MAXIMUM_SPREAD_FRACTION
    ):
        raise ValueError("selected contract spread exceeds policy")

    policy_id = (
        f"task8-p6-policy:{cycle.cycle_id}"
    )
    policy = _planning_policy(
        policy_id=policy_id,
    )

    decision = FinalDecisionV1(
        snapshot_id=cycle.observation_id,
        decision_id=(
            f"task8-final-decision:{cycle.cycle_id}"
        ),
        symbol=symbol,
        exchange=exchange,
        instrument_type="INDEX_OPTION",
        created_at=now,
        market_timestamp=cycle.market_timestamp,
        action=_DIRECTION_ACTION[direction],
        authorization_status=(
            AuthorizationStatus.ANALYSIS_ONLY.value
        ),
        execution_status=(
            ExecutionStatus.NOT_REQUESTED.value
        ),
        market_regime=str(
            getattr(
                evidence.regime,
                "market_regime",
                getattr(
                    evidence.regime,
                    "regime",
                    "UNKNOWN",
                ),
            )
        ),
        direction=direction,
        confidence=evaluation.candidate.confidence,
        trade_quality_score=evaluation.candidate.score,
        technical_score=evaluation.candidate.score,
        options_score=(
            selected_candidate.total_score * 100.0
            if selected_candidate.total_score <= 1.0
            else selected_candidate.total_score
        ),
        data_quality_score=evaluation.candidate.score,
        risk=RiskSummary(
            risk_status="NOT_EVALUATED",
            capital=capital,
            risk_amount=(
                capital * _MAXIMUM_RISK_FRACTION
            ),
        ),
        supporting_reasons=(
            evaluation.candidate.reasons
        ),
        contradictions=(
            evaluation.candidate.contradictions
        ),
        blocking_reasons=(
            evaluation.candidate.blockers
        ),
        invalidation_conditions=(
            evaluation.candidate.invalidation_conditions
        ),
        warnings=evaluation.candidate.warnings,
        options_interpretation={
            "ranking_id": ranking.ranking_id,
            "ranking_status": ranking.ranking_status,
            "selected_contract_id": (
                selected_contract.contract_id
            ),
            "selected_trading_symbol": (
                selected_contract.trading_symbol
            ),
            "selected_option_right": option_right,
            "selected_strike": selected_contract.strike,
            "selected_expiry": (
                selected_contract.expiry_date.isoformat()
            ),
        },
        data_health=DataHealthSummary(
            overall_status="READY",
            validation_passed=True,
            warnings=evaluation.candidate.warnings,
        ),
        engine_versions={
            "task8_candidate_evaluator": "1",
            "trade_opportunity_integrator": "1",
        },
        rule_versions={
            "task8_selected_market_p6": "1",
        },
        source_timestamps={
            "market": cycle.market_timestamp.isoformat(),
            "evaluation": now.isoformat(),
            "option_universe": universe.captured_at.isoformat(),
            "option_ranking": ranking.ranked_at.isoformat(),
            "technical": evidence.technical.created_at.isoformat(),
            "option_chain": evidence.option_chain.created_at.isoformat(),
            "session": evidence.session.evaluated_at.isoformat(),
        },
        trace_metadata={
            "pipeline": "task8_selected_market_p6",
            "parent_cycle_id": bridge.parent_cycle_id,
            "observation_id": cycle.observation_id,
            "candidate_id": (
                evaluation.candidate.candidate_id
            ),
            "ranking_id": ranking.ranking_id,
        },
    )

    if not decision.validation_passed:
        raise ValueError(
            "Task 8 final decision failed validation: "
            + " | ".join(decision.validation_errors)
        )

    trade_opportunity = build_canonical_trade_opportunity(
        decision=decision,
        technical_intelligence=evidence.technical,
        option_chain_intelligence=evidence.option_chain,
        contract_ranking=ranking,
        session_validation=cycle.session_validation,
        clock=lambda: now,
        opportunity_id_factory=lambda: (
            f"task8-opportunity:{cycle.cycle_id}"
        ),
    )
    if trade_opportunity.opportunity_status not in {
        "READY",
        "READY_WITH_WARNINGS",
    }:
        raise ValueError(
            "canonical trade opportunity is not ready: "
            + " | ".join(
                trade_opportunity.blockers
                or trade_opportunity.contradictions
                or trade_opportunity.warnings
                or (
                    trade_opportunity.opportunity_status,
                )
            )
        )

    warnings = tuple(
        dict.fromkeys(
            evaluation.candidate.warnings
            + ranking.warnings
            + trade_opportunity.warnings
        )
    )
    opportunity_status = (
        "READY_WITH_WARNINGS"
        if warnings
        else "READY"
    )

    broader_market = evaluation.composition.broader_market
    external_context = evaluation.composition.external_context

    market_opportunity = MarketOpportunityCandidateV1(
        candidate_id=(
            f"task8-market-opportunity:{cycle.cycle_id}"
        ),
        evaluated_at=now,
        underlying_symbol=symbol,
        exchange=exchange,
        market_regime=evidence.regime,
        market_session_validation=cycle.session_validation,
        candidate_status=opportunity_status,
        analysis_allowed=True,
        new_entries_allowed=True,
        opportunity_confidence=_unit_score(
            evaluation.candidate.confidence,
            "candidate confidence",
        ),
        regime_suitability_score=_unit_score(
            evaluation.candidate.score,
            "candidate score",
        ),
        technical_confirmation_score=_unit_score(
            evaluation.candidate.score,
            "technical score",
        ),
        option_chain_confirmation_score=_unit_score(
            selected_candidate.total_score,
            "option score",
        ),
        broader_market_confirmation_score=(
            _unit_score(
                evaluation.candidate.score,
                "broader score",
            )
            if broader_market is not None
            else 0.0
        ),
        external_context_confirmation_score=(
            _unit_score(
                evaluation.candidate.score,
                "external score",
            )
            if external_context is not None
            else 0.0
        ),
        data_quality_score=_unit_score(
            evaluation.candidate.score,
            "data quality score",
        ),
        liquidity_score=_unit_score(
            selected_candidate.liquidity_score,
            "liquidity score",
        ),
        execution_quality_score=_unit_score(
            selected_candidate.total_score,
            "execution quality score",
        ),
        trade_opportunity_available=True,
        option_chain_available=True,
        broader_market_available=broader_market is not None,
        external_context_available=external_context is not None,
        liquidity_available=True,
        execution_quality_available=True,
        entry_restriction_state="OPEN",
        data_quality_state="GOOD",
        freshness_state="FRESH",
        trade_opportunity=trade_opportunity,
        broader_market_intelligence=broader_market,
        external_market_context=external_context,
        supporting_evidence=evaluation.candidate.reasons,
        warnings=warnings,
        source_timestamps={
            "MARKET": cycle.market_timestamp,
            "EVALUATION": now,
            "OPTION_UNIVERSE": universe.captured_at,
            "OPTION_RANKING": ranking.ranked_at,
            "TECHNICAL": evidence.technical.created_at,
            "OPTION_CHAIN": evidence.option_chain.created_at,
            "SESSION": evidence.session.evaluated_at,
        },
        metadata={
            "task8_parent_cycle_id": bridge.parent_cycle_id,
            "task8_selected_child_result_id": (
                bridge.selected_child_result_id
            ),
        },
    )

    maximum_risk_amount = (
        capital * _MAXIMUM_RISK_FRACTION
    )
    trade_plan_input_id = (
        f"task8-trade-plan-input:{cycle.cycle_id}"
    )
    canonical = CanonicalTradePlanInputV1(
        trade_plan_input_id=trade_plan_input_id,
        evaluated_at=now,
        underlying_symbol=symbol,
        exchange=exchange,
        selected_market_opportunity=market_opportunity,
        market_regime=evidence.regime,
        market_session_validation=cycle.session_validation,
        option_chain_available=True,
        external_context_available=external_context is not None,
        available_capital=capital,
        maximum_risk_amount=maximum_risk_amount,
        maximum_risk_fraction=_MAXIMUM_RISK_FRACTION,
        maximum_entry_premium=None,
        maximum_slippage_fraction=0.01,
        maximum_spread_fraction=_MAXIMUM_SPREAD_FRACTION,
        estimated_brokerage_per_order=20.0,
        minimum_lot_count=1,
        maximum_lot_count=_MAXIMUM_PLANNED_LOTS,
        allow_weekly_expiry=True,
        allow_monthly_expiry=True,
        allow_same_day_expiry=False,
        option_chain_intelligence=evidence.option_chain,
        external_market_context=external_context,
        warnings=warnings,
        source_timestamps={
            "MARKET": cycle.market_timestamp,
            "EVALUATION": now,
            "OPTION_UNIVERSE": universe.captured_at,
            "OPTION_RANKING": ranking.ranked_at,
            "TECHNICAL": evidence.technical.created_at,
            "OPTION_CHAIN": evidence.option_chain.created_at,
            "SESSION": evidence.session.evaluated_at,
        },
        metadata={
            "task8_observation_id": cycle.observation_id,
            "task8_ranking_id": ranking.ranking_id,
        },
    )
    if not canonical.planning_allowed:
        raise ValueError(
            "canonical trade plan input does not allow planning"
        )

    eligibility = tuple(
        OptionContractEligibilityEvidenceV1(
            evidence_id=(
                f"task8-eligibility:{cycle.cycle_id}:"
                f"{ranked.contract.contract_id}"
            ),
            candidate_id=ranked.contract.contract_id,
            underlying_symbol=symbol,
            exchange=exchange,
            option_right=option_right,
            trading_symbol=ranked.contract.trading_symbol,
            strike_price=ranked.contract.strike,
            expiry_date=ranked.contract.expiry_date,
            moneyness_steps=derive_task8_moneyness_steps(
                strike=ranked.contract.strike,
                spot_price=universe.spot_price,
                strike_interval=strike_interval,
            ),
            expiry_category=classify_task8_expiry(
                ranked.contract.expiry_date
            ),
            days_to_expiry=(
                ranked.contract.expiry_date - now.date()
            ).days,
            evidence_timestamp=now,
            evidence_source="TASK8_RETAINED_OPTION_UNIVERSE",
            warnings=ranked.warnings,
            source_timestamps={
                "universe": universe.captured_at,
                "ranking": ranking.ranked_at,
                "contract": ranked.contract.market_timestamp,
            },
            metadata={
                "strike_interval": strike_interval,
                "spot_price": universe.spot_price,
            },
        )
        for ranked in ranking.ranked_candidates
        if (
            ranked.contract.expiry_date - now.date()
        ).days >= 1
    )
    if not eligibility:
        raise ValueError(
            "no eligible retained option-contract evidence"
        )

    selection_id = (
        f"task8-option-selection:{cycle.cycle_id}"
    )
    selection_result_id = (
        f"{selection_id}:result"
    )
    option_selection_input = OptionContractSelectionInputV1(
        selection_id=selection_id,
        selection_result_id=selection_result_id,
        evaluated_at=now,
        trade_plan_input_id=trade_plan_input_id,
        policy_id=policy.policy_id,
        option_ranking_result_id=ranking.ranking_id,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        option_ranking_result=ranking,
        available_capital=capital,
        maximum_entry_premium=None,
        maximum_spread_fraction=_MAXIMUM_SPREAD_FRACTION,
        minimum_open_interest=0,
        minimum_volume=0,
        minimum_liquidity_score=None,
        allowed_moneyness=("ATM",),
        maximum_moneyness_steps=0,
        minimum_lot_count=1,
        maximum_lot_count=_MAXIMUM_PLANNED_LOTS,
        allow_weekly_expiry=True,
        allow_monthly_expiry=True,
        allow_same_day_expiry=False,
        minimum_days_to_expiry=1,
        maximum_days_to_expiry=None,
        planning_allowed=True,
        session_allows_new_entries=True,
        event_restriction_active=False,
        warnings=warnings,
        source_timestamps={
            "universe": universe.captured_at,
            "ranking": ranking.ranked_at,
        },
        metadata={
            "task8_observation_id": cycle.observation_id,
        },
        candidate_eligibility_evidence=eligibility,
    )

    entry_evaluation_id = (
        f"task8-entry:{cycle.cycle_id}"
    )
    entry_result_id = (
        f"{entry_evaluation_id}:result"
    )
    midpoint = (
        reference_price
        if reference_method == "OPTION_MID"
        else None
    )
    entry_zone_input = EntryZoneEvaluationInputV1(
        evaluation_id=entry_evaluation_id,
        evaluation_result_id=entry_result_id,
        evaluated_at=now,
        underlying_symbol=symbol,
        exchange=exchange,
        trade_plan_input_id=trade_plan_input_id,
        policy_id=policy.policy_id,
        direction=direction,
        option_right=option_right,
        entry_reference_method=reference_method,
        last_traded_price=selected_contract.last_price,
        bid_price=selected_contract.bid_price,
        ask_price=selected_contract.ask_price,
        signal_reference_price=None,
        option_mid_price=midpoint,
        option_quote_timestamp=(
            selected_contract.market_timestamp
        ),
        maximum_entry_premium=None,
        maximum_spread_fraction=(
            _MAXIMUM_SPREAD_FRACTION
        ),
        planning_allowed=True,
        warnings=warnings,
        source_timestamps={
            "contract": selected_contract.market_timestamp,
        },
        metadata={
            "task8_contract_id": (
                selected_contract.contract_id
            ),
        },
    )

    entry_lower = reference_price * (
        1.0 - _ENTRY_TOLERANCE_FRACTION
    )
    entry_upper = reference_price * (
        1.0 + _ENTRY_TOLERANCE_FRACTION
    )
    maximum_chase = reference_price * (
        1.0 + _MAXIMUM_CHASE_FRACTION
    )
    stop_price = reference_price * (
        1.0 - _STOP_FRACTION
    )
    stop_distance = reference_price - stop_price

    stop_evaluation_id = (
        f"task8-stop:{cycle.cycle_id}"
    )
    stop_result_id = (
        f"{stop_evaluation_id}:result"
    )
    stop_loss_input = StopLossEvaluationInputV1(
        evaluation_id=stop_evaluation_id,
        evaluation_result_id=stop_result_id,
        evaluated_at=now,
        trade_plan_input_id=trade_plan_input_id,
        policy_id=policy.policy_id,
        entry_evaluation_result_id=entry_result_id,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        entry_reference_price=reference_price,
        entry_zone_lower=entry_lower,
        entry_zone_upper=entry_upper,
        atr_value=None,
        structure_stop_price=None,
        premium_reference_price=reference_price,
        recent_swing_low=None,
        recent_swing_high=None,
        planning_allowed=True,
        warnings=warnings,
        source_timestamps={
            "contract": selected_contract.market_timestamp,
        },
    )

    target_evaluation_id = (
        f"task8-targets:{cycle.cycle_id}"
    )
    target_result_id = (
        f"{target_evaluation_id}:result"
    )
    three_target_input = ThreeTargetEvaluationInputV1(
        evaluation_id=target_evaluation_id,
        evaluation_result_id=target_result_id,
        evaluated_at=now,
        trade_plan_input_id=trade_plan_input_id,
        policy_id=policy.policy_id,
        entry_evaluation_result_id=entry_result_id,
        stop_evaluation_result_id=stop_result_id,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        entry_reference_price=reference_price,
        stop_loss_price=stop_price,
        stop_distance=stop_distance,
        stop_distance_fraction=_STOP_FRACTION,
        atr_value=None,
        expected_move_value=None,
        structure_target_1=None,
        structure_target_2=None,
        structure_target_3=None,
        planning_allowed=True,
        warnings=warnings,
        source_timestamps={
            "contract": selected_contract.market_timestamp,
        },
    )

    estimated_one_lot_cost = (
        reference_price * selected_contract.lot_size
    )
    affordable_lots = min(
        _MAXIMUM_PLANNED_LOTS,
        int(
            (
                capital
                * _MAXIMUM_CAPITAL_UTILIZATION_FRACTION
            )
            // estimated_one_lot_cost
        ),
    )
    if affordable_lots < 1:
        raise ValueError(
            "selected contract is unaffordable"
        )

    placeholder_selection = (
        OptionContractSelectionResultV1(
            selection_result_id=selection_result_id,
            selection_id=selection_id,
            evaluated_at=now,
            underlying_symbol=symbol,
            exchange=exchange,
            direction=direction,
            option_right=option_right,
            status="READY",
            selected_contract=selected_candidate,
            selected_rank=1,
            selected_score=selected_candidate.total_score,
            selected_reason_codes=("TASK8_RETAINED_RANKING",),
            premium_affordable=True,
            spread_acceptable=True,
            liquidity_acceptable=True,
            open_interest_acceptable=True,
            volume_acceptable=True,
            moneyness_acceptable=True,
            expiry_acceptable=True,
            lot_size_acceptable=True,
            session_acceptable=True,
            event_acceptable=True,
            effective_maximum_entry_premium=None,
            effective_maximum_spread_fraction=(
                _MAXIMUM_SPREAD_FRACTION
            ),
            estimated_one_lot_premium_cost=(
                estimated_one_lot_cost
            ),
            affordable_lot_count=affordable_lots,
            warnings=warnings,
        )
    )
    placeholder_entry = EntryZoneEvaluationResultV1(
        evaluation_result_id=entry_result_id,
        evaluation_id=entry_evaluation_id,
        evaluated_at=now,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        entry_method=reference_method,
        selected_reference_source=reference_method,
        status="READY",
        entry_reference_price=reference_price,
        entry_zone_lower=entry_lower,
        entry_zone_upper=entry_upper,
        entry_tolerance_fraction=(
            _ENTRY_TOLERANCE_FRACTION
        ),
        maximum_chase_price=maximum_chase,
        maximum_entry_premium=None,
        effective_spread_fraction=spread_fraction,
        effective_spread_limit=(
            _MAXIMUM_SPREAD_FRACTION
        ),
        require_limit_entry=True,
        warnings=warnings,
    )
    placeholder_stop = StopLossEvaluationResultV1(
        evaluation_result_id=stop_result_id,
        evaluation_id=stop_evaluation_id,
        evaluated_at=now,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        stop_method="PREMIUM_FRACTION",
        selected_stop_source="PREMIUM_FRACTION",
        status="READY",
        stop_loss_price=stop_price,
        stop_reference_price=reference_price,
        stop_distance=stop_distance,
        stop_distance_fraction=_STOP_FRACTION,
        minimum_stop_distance_fraction=0.01,
        maximum_stop_distance_fraction=0.20,
        warnings=warnings,
        invalidation_rules=(
            "STOP_OPTION_PREMIUM_BREACH",
        ),
    )

    target_1_price = reference_price + stop_distance
    target_2_price = (
        reference_price + 1.5 * stop_distance
    )
    target_3_price = (
        reference_price + 2.0 * stop_distance
    )
    placeholder_targets = ThreeTargetEvaluationResultV1(
        evaluation_result_id=target_result_id,
        evaluation_id=target_evaluation_id,
        evaluated_at=now,
        underlying_symbol=symbol,
        exchange=exchange,
        direction=direction,
        option_right=option_right,
        target_method="RISK_MULTIPLE",
        selected_target_source="RISK_MULTIPLE",
        status="READY",
        target_1=TradePlanTargetV1(
            1,
            target_1_price,
            0.30,
            stop_distance,
            1.0,
            "RISK_REDUCTION",
        ),
        target_2=TradePlanTargetV1(
            2,
            target_2_price,
            0.40,
            1.5 * stop_distance,
            1.5,
            "PRIMARY",
        ),
        target_3=TradePlanTargetV1(
            3,
            target_3_price,
            0.30,
            2.0 * stop_distance,
            2.0,
            "EXTENDED",
        ),
        entry_reference_price=reference_price,
        stop_loss_price=stop_price,
        stop_distance=stop_distance,
        stop_distance_fraction=_STOP_FRACTION,
        minimum_reward_to_risk_t1=1.0,
        minimum_reward_to_risk_t2=1.5,
        minimum_reward_to_risk_t3=2.0,
        target_1_multiplier=1.0,
        target_2_multiplier=1.5,
        target_3_multiplier=2.0,
        warnings=warnings,
    )

    capital_policy = CapitalQuantityPlanningPolicyV1(
        policy_id=policy.policy_id,
        maximum_capital_utilization_fraction=(
            _MAXIMUM_CAPITAL_UTILIZATION_FRACTION
        ),
        maximum_risk_fraction=(
            _MAXIMUM_RISK_FRACTION
        ),
        maximum_planned_lot_count=(
            _MAXIMUM_PLANNED_LOTS
        ),
        target_allocation_enabled=True,
        target_allocation_weights=(0.30, 0.40, 0.30),
        policy_timestamp=now,
        policy_source="TASK8_CERTIFIED",
    )
    cost_policy = CapitalQuantityTradingCostPolicyV1(
        cost_policy_id=(
            f"task8-cost-policy:{cycle.cycle_id}"
        ),
        calculation_mode="FIXED_ASSUMPTION_MODEL",
        brokerage_fixed_per_order=20.0,
        exchange_transaction_charge_fraction=0.0005,
        clearing_charge_fraction=0.0,
        stt_rate_fraction=0.000625,
        sebi_charge_fraction=0.000001,
        stamp_duty_rate_fraction=0.00003,
        gst_rate_fraction=0.18,
        slippage_rate_fraction=0.005,
        estimated_order_count=5,
        policy_timestamp=now,
        policy_source="TASK8_CERTIFIED",
    )

    planning_input_id = (
        f"task8-capital-input:{cycle.cycle_id}"
    )
    trade_plan_id = (
        f"task8-trade-plan:{cycle.cycle_id}"
    )

    one_lot_premium_cost = (
        placeholder_selection
        .estimated_one_lot_premium_cost
    )
    affordable_lot_count = (
        placeholder_selection
        .affordable_lot_count
    )
    selected_lot_size = (
        placeholder_selection.selected_lot_size
    )
    stop_distance = placeholder_stop.stop_distance

    if (
        one_lot_premium_cost is None
        or affordable_lot_count is None
        or selected_lot_size is None
        or stop_distance is None
    ):
        raise ValueError(
            "Task 8 requires complete affordability "
            "and stop-distance evidence"
        )

    # Cost evidence must remain structurally complete even when the
    # capital/risk planner later determines that zero lots are permissible.
    # The evidence therefore describes the deterministic cost of one lot.
    # The authoritative planner still applies the 1% PREMIUM_AT_RISK rule
    # and returns NO_SIZE when that one lot exceeds the risk budget.
    evidence_lot_count = 1
    planned_lot_count = evidence_lot_count
    planned_quantity = (
        evidence_lot_count * selected_lot_size
    )
    premium_outlay = one_lot_premium_cost

    estimated_brokerage = 0.0
    if cost_policy.apply_brokerage:
        estimated_brokerage = (
            cost_policy.brokerage_fixed_per_order
            * cost_policy.estimated_order_count
            + premium_outlay
            * cost_policy.brokerage_rate_fraction
        )

    estimated_exchange_charges = (
        premium_outlay
        * cost_policy.exchange_transaction_charge_fraction
        if cost_policy.apply_exchange_transaction_charges
        else 0.0
    )
    estimated_clearing_charges = (
        premium_outlay
        * cost_policy.clearing_charge_fraction
        if cost_policy.apply_clearing_charges
        else 0.0
    )
    estimated_stt = (
        premium_outlay
        * cost_policy.stt_rate_fraction
        if cost_policy.apply_stt
        else 0.0
    )
    estimated_sebi_charges = (
        premium_outlay
        * cost_policy.sebi_charge_fraction
        if cost_policy.apply_sebi_charges
        else 0.0
    )
    estimated_stamp_duty = (
        premium_outlay
        * cost_policy.stamp_duty_rate_fraction
        if cost_policy.apply_stamp_duty
        else 0.0
    )
    estimated_slippage = (
        premium_outlay
        * cost_policy.slippage_rate_fraction
        if cost_policy.apply_slippage
        else 0.0
    )

    gst_taxable_base = (
        estimated_brokerage
        + estimated_exchange_charges
        + estimated_clearing_charges
        + estimated_sebi_charges
    )
    estimated_gst = (
        gst_taxable_base
        * cost_policy.gst_rate_fraction
        if cost_policy.apply_gst
        else 0.0
    )

    estimated_total_trading_cost = (
        estimated_brokerage
        + estimated_exchange_charges
        + estimated_clearing_charges
        + estimated_stt
        + estimated_sebi_charges
        + estimated_stamp_duty
        + estimated_gst
        + estimated_slippage
    )
    estimated_total_capital_requirement = (
        premium_outlay
        + estimated_total_trading_cost
    )

    cost_source_timestamps = {
        "candidate": (
            evaluation.candidate.market_timestamp
        ),
        "ranking": ranking.ranked_at,
        "universe": universe.captured_at,
    }

    cost_evidence = (
        CapitalQuantityTradingCostEvidenceV1(
            evidence_id=(
                f"task8-cost-evidence:"
                f"{cycle.cycle_id}"
            ),
            planning_input_id=planning_input_id,
            trade_plan_id=trade_plan_id,
            cost_policy_id=cost_policy.cost_policy_id,
            option_selection_result_id=(
                placeholder_selection
                .selection_result_id
            ),
            planned_lot_count=planned_lot_count,
            lot_size=selected_lot_size,
            planned_quantity=planned_quantity,
            estimated_premium_outlay=(
                premium_outlay
            ),
            estimated_order_count=(
                cost_policy.estimated_order_count
            ),
            estimated_brokerage=(
                estimated_brokerage
            ),
            estimated_exchange_transaction_charges=(
                estimated_exchange_charges
            ),
            estimated_clearing_charges=(
                estimated_clearing_charges
            ),
            estimated_stt=estimated_stt,
            estimated_sebi_charges=(
                estimated_sebi_charges
            ),
            estimated_stamp_duty=(
                estimated_stamp_duty
            ),
            estimated_gst=estimated_gst,
            estimated_slippage=(
                estimated_slippage
            ),
            estimated_total_trading_cost=(
                estimated_total_trading_cost
            ),
            estimated_total_capital_requirement=(
                estimated_total_capital_requirement
            ),
            applied_slippage_rate_fraction=(
                cost_policy.slippage_rate_fraction
                if cost_policy.apply_slippage
                else 0.0
            ),
            applied_effective_cost_fraction=(
                estimated_total_trading_cost
                / premium_outlay
            ),
            evidence_timestamp=now,
            evidence_source=(
                "TASK8_FIXED_ASSUMPTION_MODEL"
            ),
            warnings=warnings,
            source_timestamps=(
                cost_source_timestamps
            ),
            metadata={
                "task8_parent_cycle_id": (
                    bridge.parent_cycle_id
                ),
                "task8_contract_id": (
                    selected_contract.contract_id
                ),
            },
        )
    )

    capital_input = CapitalQuantityPlanningInputV1(
        planning_input_id=planning_input_id,
        trade_plan_id=trade_plan_id,
        policy_id=capital_policy.policy_id,
        canonical_trade_plan_input=canonical,
        capital_quantity_policy=capital_policy,
        entry_zone_result=placeholder_entry,
        stop_loss_result=placeholder_stop,
        three_target_result=placeholder_targets,
        option_contract_selection_result=(
            placeholder_selection
        ),
        trading_cost_policy=cost_policy,
        trading_cost_evidence=cost_evidence,
        caller_supplied_per_lot_risk_amount=None,
        evaluated_at=now,
        input_source="TASK8_RETAINED_CERTIFIED_EVIDENCE",
        warnings=warnings,
        source_timestamps=cost_source_timestamps,
        metadata={
            "task8_parent_cycle_id": bridge.parent_cycle_id,
            "task8_observation_id": cycle.observation_id,
            "task8_contract_id": (
                selected_contract.contract_id
            ),
        },
    )

    return CertifiedP6InputBundleV1(
        planning_policy=policy,
        option_selection_input=option_selection_input,
        entry_zone_input=entry_zone_input,
        stop_loss_input=stop_loss_input,
        three_target_input=three_target_input,
        capital_quantity_input=capital_input,
    )
