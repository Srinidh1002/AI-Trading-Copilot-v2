"""Deterministic integration of decision and market intelligence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.contracts.technical_intelligence_result_v1 import (
    TechnicalIntelligenceResultV1,
)
from services.contracts.trade_opportunity_policy_v1 import (
    DEFAULT_TRADE_OPPORTUNITY_POLICY,
    TradeOpportunityPolicyV1,
)
from services.contracts.trade_opportunity_v1 import (
    TradeOpportunityV1,
)


_READY_TECHNICAL_STATUSES = frozenset(
    {
        "READY",
        "READY_WITH_WARNINGS",
    }
)

_READY_OPTION_CHAIN_STATUSES = frozenset(
    {
        "READY",
        "READY_WITH_WARNINGS",
    }
)

_READY_RANKING_STATUSES = frozenset(
    {
        "RANKED",
        "RANKED_WITH_WARNINGS",
    }
)


def build_canonical_trade_opportunity(
    *,
    decision: FinalDecisionV1,
    technical_intelligence: TechnicalIntelligenceResultV1,
    option_chain_intelligence: OptionChainIntelligenceResultV1,
    contract_ranking: OptionContractRankingResultV1,
    session_validation: MarketSessionValidationV1,
    policy: TradeOpportunityPolicyV1 = (
        DEFAULT_TRADE_OPPORTUNITY_POLICY
    ),
    clock: Callable[[], datetime] | None = None,
    opportunity_id_factory: Callable[[], str] | None = None,
) -> TradeOpportunityV1:
    """Build a canonical paper-only trade opportunity.

    This function does not construct entry, stop-loss, targets, quantity,
    position size, execution authorization, or broker requests.
    """

    if not isinstance(decision, FinalDecisionV1):
        raise TypeError(
            "decision must be a FinalDecisionV1"
        )

    if not isinstance(
        technical_intelligence,
        TechnicalIntelligenceResultV1,
    ):
        raise TypeError(
            "technical_intelligence must be a "
            "TechnicalIntelligenceResultV1"
        )

    if not isinstance(
        option_chain_intelligence,
        OptionChainIntelligenceResultV1,
    ):
        raise TypeError(
            "option_chain_intelligence must be an "
            "OptionChainIntelligenceResultV1"
        )

    if not isinstance(
        contract_ranking,
        OptionContractRankingResultV1,
    ):
        raise TypeError(
            "contract_ranking must be an "
            "OptionContractRankingResultV1"
        )

    if not isinstance(
        session_validation,
        MarketSessionValidationV1,
    ):
        raise TypeError(
            "session_validation must be a "
            "MarketSessionValidationV1"
        )

    if not isinstance(policy, TradeOpportunityPolicyV1):
        raise TypeError(
            "policy must be a TradeOpportunityPolicyV1"
        )

    now = clock() if clock is not None else decision.created_at

    if not isinstance(now, datetime):
        raise TypeError("clock must return a datetime")

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(
            "opportunity creation time must be timezone-aware"
        )

    opportunity_id = (
        opportunity_id_factory
        or (lambda: str(uuid4()))
    )()

    action = str(decision.action).upper()

    if action not in {"BUY", "SELL", "WAIT", "HOLD"}:
        return _result(
            opportunity_id=opportunity_id,
            created_at=now,
            decision=decision,
            technical=technical_intelligence,
            option_chain=option_chain_intelligence,
            ranking=contract_ranking,
            session=session_validation,
            status="FAILED",
            blockers=("DECISION ACTION IS UNSUPPORTED",),
        )

    if action in {"WAIT", "HOLD"}:
        return _result(
            opportunity_id=opportunity_id,
            created_at=now,
            decision=decision,
            technical=technical_intelligence,
            option_chain=option_chain_intelligence,
            ranking=contract_ranking,
            session=session_validation,
            status="NO_ACTION",
            action=action,
            directional_bias=(
                str(decision.direction).upper()
                if str(decision.direction).upper()
                in {
                    "BULLISH",
                    "BEARISH",
                    "NEUTRAL",
                    "MIXED",
                    "UNAVAILABLE",
                }
                else "NEUTRAL"
            ),
        )

    expected_bias = (
        "BULLISH"
        if action == "BUY"
        else "BEARISH"
    )
    expected_option_type = (
        "CALL"
        if action == "BUY"
        else "PUT"
    )

    blockers: list[str] = []
    warnings: list[str] = []
    supporting: list[str] = []
    contradictions: list[str] = []

    identity = (
        decision.symbol,
        decision.exchange,
    )

    source_identities = (
        (
            technical_intelligence.underlying_symbol,
            technical_intelligence.exchange,
        ),
        (
            option_chain_intelligence.underlying_symbol,
            option_chain_intelligence.exchange,
        ),
        (
            contract_ranking.underlying_symbol,
            contract_ranking.exchange,
        ),
        (
            session_validation.symbol,
            session_validation.exchange,
        ),
    )

    if any(
        source_identity != identity
        for source_identity in source_identities
    ):
        blockers.append(
            "SOURCE MARKET IDENTITIES DO NOT MATCH"
        )

    if not decision.validation_passed:
        blockers.append(
            "FINAL DECISION VALIDATION FAILED"
        )

    if decision.authorization_status == "BLOCKED":
        blockers.append(
            "FINAL DECISION IS BLOCKED"
        )

    if (
        policy.decision_policy == "REQUIRE_DIRECTIONAL"
        and action not in {"BUY", "SELL"}
    ):
        blockers.append(
            "DIRECTIONAL FINAL DECISION IS REQUIRED"
        )

    if (
        policy.session_policy
        == "REQUIRE_PAPER_PREPARATION_ALLOWED"
        and not session_validation.paper_preparation_allowed
    ):
        blockers.append(
            "MARKET SESSION DOES NOT ALLOW PAPER PREPARATION"
        )

    if (
        policy.session_policy
        == "REQUIRE_ANALYSIS_ALLOWED"
        and not session_validation.analysis_allowed
    ):
        blockers.append(
            "MARKET SESSION DOES NOT ALLOW ANALYSIS"
        )

    if session_validation.errors:
        blockers.extend(
            str(item).strip().upper()
            for item in session_validation.errors
            if str(item).strip()
        )

    if (
        policy.require_ready_technical_intelligence
        and technical_intelligence.status
        not in _READY_TECHNICAL_STATUSES
    ):
        blockers.append(
            "TECHNICAL INTELLIGENCE IS NOT READY"
        )

    if (
        policy.require_ready_option_chain_intelligence
        and option_chain_intelligence.intelligence_status
        not in _READY_OPTION_CHAIN_STATUSES
    ):
        blockers.append(
            "OPTION-CHAIN INTELLIGENCE IS NOT READY"
        )

    if (
        policy.require_ranked_contract
        and contract_ranking.ranking_status
        not in _READY_RANKING_STATUSES
    ):
        blockers.append(
            "OPTION CONTRACT RANKING IS NOT READY"
        )

    selected_candidate = contract_ranking.selected_candidate

    if (
        policy.require_ranked_contract
        and selected_candidate is None
    ):
        blockers.append(
            "RANKED OPTION CONTRACT IS REQUIRED"
        )

    if (
        policy.require_matching_direction
        and technical_intelligence.aggregate_bias
        != expected_bias
    ):
        contradictions.append(
            "TECHNICAL INTELLIGENCE DOES NOT MATCH DECISION"
        )

    if (
        policy.require_matching_direction
        and option_chain_intelligence.aggregate_bias
        != expected_bias
    ):
        contradictions.append(
            "OPTION-CHAIN INTELLIGENCE DOES NOT MATCH DECISION"
        )

    if (
        policy.require_matching_direction
        and contract_ranking.directional_bias
        != expected_bias
    ):
        contradictions.append(
            "CONTRACT RANKING DIRECTION DOES NOT MATCH DECISION"
        )

    if (
        policy.require_matching_direction
        and contract_ranking.required_option_type
        != expected_option_type
    ):
        contradictions.append(
            "CONTRACT RANKING OPTION TYPE DOES NOT MATCH DECISION"
        )

    if selected_candidate is not None:
        if (
            selected_candidate.contract.option_type
            != expected_option_type
        ):
            contradictions.append(
                "SELECTED CONTRACT OPTION TYPE DOES NOT MATCH DECISION"
            )

        supporting.append(
            "RANKED OPTION CONTRACT IS AVAILABLE"
        )

    if technical_intelligence.aggregate_bias == expected_bias:
        supporting.append(
            "TECHNICAL INTELLIGENCE ALIGNS WITH DECISION"
        )

    if option_chain_intelligence.aggregate_bias == expected_bias:
        supporting.append(
            "OPTION-CHAIN INTELLIGENCE ALIGNS WITH DECISION"
        )

    if contract_ranking.directional_bias == expected_bias:
        supporting.append(
            "CONTRACT RANKING ALIGNS WITH DECISION"
        )

    warnings.extend(
        str(item).strip().upper()
        for item in decision.warnings
        if str(item).strip()
    )
    warnings.extend(technical_intelligence.warnings)
    warnings.extend(option_chain_intelligence.warnings)
    warnings.extend(contract_ranking.warnings)
    warnings.extend(session_validation.warnings)

    blockers.extend(
        str(item).strip().upper()
        for item in decision.blocking_reasons
        if str(item).strip()
    )

    source_times = (
        technical_intelligence.created_at,
        option_chain_intelligence.created_at,
        contract_ranking.ranked_at,
        session_validation.evaluated_at,
        decision.created_at,
    )

    for source_time in source_times:
        age_seconds = (now - source_time).total_seconds()
        future_skew_seconds = (
            source_time - now
        ).total_seconds()

        if age_seconds > policy.maximum_source_age_seconds:
            blockers.append(
                "INTEGRATION SOURCE IS STALE"
            )
            break

        if (
            future_skew_seconds
            > policy.maximum_future_skew_seconds
        ):
            blockers.append(
                "INTEGRATION SOURCE TIMESTAMP IS IN THE FUTURE"
            )
            break

    technical_strength = float(
        technical_intelligence.aggregate_strength
    )
    option_chain_strength = float(
        option_chain_intelligence.aggregate_strength
    )
    contract_ranking_score = (
        float(selected_candidate.total_score)
        if selected_candidate is not None
        else 0.0
    )
    decision_confidence = _normalize_decision_confidence(
        decision.confidence
    )

    opportunity_score = (
        technical_strength
        * policy.technical_weight
        + option_chain_strength
        * policy.option_chain_weight
        + contract_ranking_score
        * policy.contract_ranking_weight
        + decision_confidence
        * policy.decision_confidence_weight
    )

    opportunity_score = min(
        1.0,
        max(0.0, opportunity_score),
    )

    if (
        technical_strength
        < policy.minimum_technical_strength
    ):
        blockers.append(
            "TECHNICAL STRENGTH IS BELOW POLICY MINIMUM"
        )

    if (
        option_chain_strength
        < policy.minimum_option_chain_strength
    ):
        blockers.append(
            "OPTION-CHAIN STRENGTH IS BELOW POLICY MINIMUM"
        )

    if (
        contract_ranking_score
        < policy.minimum_contract_ranking_score
    ):
        blockers.append(
            "CONTRACT RANKING SCORE IS BELOW POLICY MINIMUM"
        )

    if (
        decision_confidence
        < policy.minimum_decision_confidence
    ):
        blockers.append(
            "DECISION CONFIDENCE IS BELOW POLICY MINIMUM"
        )

    if opportunity_score < policy.minimum_opportunity_score:
        blockers.append(
            "OPPORTUNITY SCORE IS BELOW POLICY MINIMUM"
        )

    if contradictions:
        blockers.append(
            "DIRECTIONAL EVIDENCE IS CONFLICTING"
        )

    if blockers:
        status = (
            "CONFLICTING"
            if contradictions
            else "BLOCKED"
        )

        return _result(
            opportunity_id=opportunity_id,
            created_at=now,
            decision=decision,
            technical=technical_intelligence,
            option_chain=option_chain_intelligence,
            ranking=contract_ranking,
            session=session_validation,
            status=status,
            action=action,
            directional_bias=expected_bias,
            technical_strength=technical_strength,
            option_chain_strength=option_chain_strength,
            contract_ranking_score=contract_ranking_score,
            decision_confidence=decision_confidence,
            opportunity_score=opportunity_score,
            supporting_evidence=tuple(
                sorted(set(supporting))
            ),
            contradictions=tuple(
                sorted(set(contradictions))
            ),
            blockers=tuple(
                sorted(set(blockers))
            ),
            warnings=tuple(
                sorted(set(warnings))
            ),
        )

    status = (
        "READY_WITH_WARNINGS"
        if warnings
        else "READY"
    )

    contract = selected_candidate.contract

    reference_price = _reference_option_price(contract)

    return _result(
        opportunity_id=opportunity_id,
        created_at=now,
        decision=decision,
        technical=technical_intelligence,
        option_chain=option_chain_intelligence,
        ranking=contract_ranking,
        session=session_validation,
        status=status,
        action=action,
        directional_bias=expected_bias,
        option_type=expected_option_type,
        expiry=contract.expiry_date,
        contract_id=contract.contract_id,
        trading_symbol=contract.trading_symbol,
        instrument_token=contract.instrument_token,
        strike=contract.strike,
        lot_size=contract.lot_size,
        reference_option_price=reference_price,
        technical_strength=technical_strength,
        option_chain_strength=option_chain_strength,
        contract_ranking_score=contract_ranking_score,
        decision_confidence=decision_confidence,
        opportunity_score=opportunity_score,
        supporting_evidence=tuple(
            sorted(set(supporting))
        ),
        warnings=tuple(
            sorted(set(warnings))
        ),
    )


def _result(
    *,
    opportunity_id: str,
    created_at: datetime,
    decision: FinalDecisionV1,
    technical: TechnicalIntelligenceResultV1,
    option_chain: OptionChainIntelligenceResultV1,
    ranking: OptionContractRankingResultV1,
    session: MarketSessionValidationV1,
    status: str,
    action: str | None = None,
    directional_bias: str | None = None,
    option_type: str | None = None,
    expiry=None,
    contract_id: str | None = None,
    trading_symbol: str | None = None,
    instrument_token: str | None = None,
    strike: float | None = None,
    lot_size: int | None = None,
    reference_option_price: float | None = None,
    technical_strength: float = 0.0,
    option_chain_strength: float = 0.0,
    contract_ranking_score: float = 0.0,
    decision_confidence: float = 0.0,
    opportunity_score: float = 0.0,
    supporting_evidence: tuple[str, ...] = (),
    contradictions: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> TradeOpportunityV1:
    resolved_action = (
        action
        if action is not None
        else str(decision.action).upper()
    )

    resolved_bias = directional_bias

    if resolved_bias is None:
        resolved_bias = (
            "BULLISH"
            if resolved_action == "BUY"
            else "BEARISH"
            if resolved_action == "SELL"
            else "NEUTRAL"
        )

    resolved_option_type = option_type

    if resolved_option_type is None:
        resolved_option_type = (
            "CALL"
            if resolved_action == "BUY"
            else "PUT"
            if resolved_action == "SELL"
            else None
        )

    return TradeOpportunityV1(
        opportunity_id=opportunity_id,
        created_at=created_at,
        snapshot_id=decision.snapshot_id,
        decision_id=decision.decision_id,
        technical_intelligence_result_id=(
            technical.technical_intelligence_result_id
        ),
        option_chain_intelligence_result_id=(
            option_chain.option_chain_intelligence_result_id
        ),
        option_contract_ranking_id=ranking.ranking_id,
        session_validation_id=session.validation_id,
        underlying_symbol=decision.symbol,
        exchange=decision.exchange,
        expiry=expiry,
        action=resolved_action,
        directional_bias=resolved_bias,
        option_type=resolved_option_type,
        contract_id=contract_id,
        trading_symbol=trading_symbol,
        instrument_token=instrument_token,
        strike=strike,
        lot_size=lot_size,
        reference_option_price=reference_option_price,
        technical_strength=technical_strength,
        option_chain_strength=option_chain_strength,
        contract_ranking_score=contract_ranking_score,
        decision_confidence=decision_confidence,
        opportunity_score=opportunity_score,
        opportunity_status=status,
        supporting_evidence=supporting_evidence,
        contradictions=contradictions,
        blockers=blockers,
        warnings=warnings,
    )


def _normalize_decision_confidence(
    value,
) -> float:
    if value is None:
        return 0.0

    normalized = float(value)

    if normalized > 1.0:
        normalized /= 100.0

    return min(1.0, max(0.0, normalized))


def _reference_option_price(contract) -> float | None:
    bid = contract.bid_price
    ask = contract.ask_price

    if (
        bid is not None
        and ask is not None
        and bid > 0.0
        and ask > 0.0
        and ask >= bid
    ):
        return (bid + ask) / 2.0

    for value in (
        ask,
        contract.last_price,
        bid,
    ):
        if value is not None and value > 0.0:
            return float(value)

    return None


__all__ = [
    "build_canonical_trade_opportunity",
]