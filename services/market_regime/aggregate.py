"""Pure deterministic aggregation of normalized market-regime components."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY, MarketRegimePolicyV1


_ORDER = ("TECHNICAL", "BROADER_MARKET", "EXTERNAL_CONTEXT", "MARKET_SESSION")
_WEIGHTS = {
    "TECHNICAL": "technical_weight",
    "BROADER_MARKET": "broader_market_weight",
    "EXTERNAL_CONTEXT": "external_context_weight",
}
_POSITIVE = {"POSITIVE", "BULLISH", "STRONG_BULLISH", "UPTREND", "STRONG_UPTREND"}
_NEGATIVE = {"NEGATIVE", "BEARISH", "STRONG_BEARISH", "DOWNTREND", "STRONG_DOWNTREND"}
_NEUTRAL = {"FLAT", "NEUTRAL", "SIDEWAYS", "RANGE_BOUND"}


def _clean(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted({" ".join(value.split()).upper() for value in values if isinstance(value, str) and value.strip()}))


def _component_timestamp(name: str, component: Any) -> datetime:
    return component.market_timestamp if name == "MARKET_SESSION" else component.created_at


def _sign(value: str) -> int | None:
    normalized = value.upper()
    if normalized in _POSITIVE:
        return 1
    if normalized in _NEGATIVE:
        return -1
    if normalized in _NEUTRAL:
        return 0
    return None


def aggregate_market_regime(
    market_regime_input: MarketRegimeInputV1,
    policy: MarketRegimePolicyV1 = DEFAULT_MARKET_REGIME_POLICY,
) -> CanonicalMarketRegimeResultV1:
    """Aggregate supplied normalized components without I/O or clock access."""
    if type(market_regime_input) is not MarketRegimeInputV1:
        raise TypeError("market_regime_input")
    if type(policy) is not MarketRegimePolicyV1:
        raise TypeError("policy")

    components = {
        "TECHNICAL": market_regime_input.technical_regime_component,
        "BROADER_MARKET": market_regime_input.broader_market_regime_component,
        "EXTERNAL_CONTEXT": market_regime_input.external_context_regime_component,
        "MARKET_SESSION": market_regime_input.market_session_validation,
    }
    usable: dict[str, Any] = {}
    unavailable: list[str] = []
    warnings = list(market_regime_input.warnings)
    blockers = list(market_regime_input.blockers)
    timestamps: dict[str, datetime] = {}
    aggregate_timestamp = market_regime_input.created_at

    for name in _ORDER:
        component = components[name]
        failed = component is None
        if not failed:
            timestamp = _component_timestamp(name, component)
            age = (aggregate_timestamp - timestamp).total_seconds()
            failed = age < -policy.future_timestamp_tolerance_seconds or age > policy.maximum_component_age_seconds[name]
            if name != "MARKET_SESSION":
                failed = failed or component.context_status in {"UNAVAILABLE", "BLOCKED"}
        if failed:
            unavailable.append(name)
            if name in policy.required_components and policy.block_on_required_component_failure:
                blockers.append(f"REQUIRED_{name}_UNUSABLE")
            elif name in policy.optional_components:
                warnings.append(f"OPTIONAL_{name}_UNUSABLE")
            continue
        usable[name] = component
        timestamps[name] = _component_timestamp(name, component)
        if name != "MARKET_SESSION":
            warnings.extend(component.warnings)

    if len(timestamps) > 1:
        skew = (max(timestamps.values()) - min(timestamps.values())).total_seconds()
        if skew > policy.maximum_component_timestamp_skew_seconds:
            warnings.append("COMPONENT_TIMESTAMP_SKEW")

    session = usable.get("MARKET_SESSION")
    analysis_allowed = bool(session.analysis_allowed) if session is not None else False
    session_entries_allowed = bool(session.paper_execution_allowed) if session is not None else False
    external = usable.get("EXTERNAL_CONTEXT")
    external_restriction = external.entry_restriction_state if external is not None else "OPEN"
    if external_restriction == "BLOCKED":
        restriction = "BLOCKED"
    elif session is not None and not session_entries_allowed and policy.preserve_session_owned_restriction:
        restriction = "SESSION_OWNED"
    elif external_restriction == "WARNING":
        restriction = "WARNING"
    else:
        restriction = "OPEN"
    new_entries_allowed = analysis_allowed and session_entries_allowed and restriction in {"OPEN", "WARNING"}
    if not analysis_allowed and policy.block_when_analysis_disallowed:
        blockers.append("ANALYSIS_DISALLOWED")
    if restriction == "BLOCKED":
        blockers.append("ENTRY_RESTRICTION_BLOCKED")

    directions: list[tuple[str, int, float, float, str]] = []
    for name in ("TECHNICAL", "BROADER_MARKET", "EXTERNAL_CONTEXT"):
        component = usable.get(name)
        if component is None:
            continue
        sign = _sign(component.directional_state)
        if sign is None:
            continue
        directions.append((name, sign, float(component.component_strength), float(component.confidence), component.confirmation_state))

    denominator = sum(float(getattr(policy, _WEIGHTS[name])) for name, *_ in directions)
    signed_score = sum(float(getattr(policy, _WEIGHTS[name])) * sign * strength for name, sign, strength, _, _ in directions)
    normalized_score = signed_score / denominator if denominator else 0.0
    strength = min(1.0, max(0.0, abs(normalized_score))) if denominator else 0.0
    confidence = sum(float(getattr(policy, _WEIGHTS[name])) * value for name, _, _, value, _ in directions) / denominator if denominator else 0.0
    positive = any(sign > 0 for _, sign, *_ in directions)
    negative = any(sign < 0 for _, sign, *_ in directions)
    contradictory = positive and negative
    contradictions: list[str] = ["OPPOSING_DIRECTIONAL_COMPONENTS"] if contradictory else []
    confirmations = sum(confirmation == "CONFIRMING" for *_, confirmation in directions)
    confirmation_state = "UNAVAILABLE" if not directions else "CONFLICTING" if contradictory else "CONFIRMING" if confirmations >= policy.minimum_confirmation_count else "PARTIAL" if confirmations else "NOT_CONFIRMING"
    if directions and 0 < confirmations < policy.minimum_confirmation_count:
        warnings.append("PARTIAL_CONFIRMATION")

    applied_penalties: list[str] = []
    if contradictory:
        confidence -= policy.conflict_penalty
        applied_penalties.append("CONFLICT")
    if any(name in unavailable for name in policy.optional_components):
        confidence -= policy.missing_optional_component_penalty
        applied_penalties.append("MISSING_OPTIONAL")
    if warnings:
        confidence -= policy.warning_penalty
        applied_penalties.append("WARNING")
    if directions and 0 < confirmations < policy.minimum_confirmation_count:
        confidence -= policy.partial_confirmation_penalty
        applied_penalties.append("PARTIAL_CONFIRMATION")
    confidence = min(1.0, max(0.0, confidence))

    technical = usable.get("TECHNICAL")
    broader = usable.get("BROADER_MARKET")
    trend = technical.trend_state if technical is not None else "UNAVAILABLE"
    volatility = broader.volatility_state if broader is not None else "UNAVAILABLE"
    breadth = broader.breadth_state if broader is not None else "UNAVAILABLE"
    event_risk = external.event_risk_state if external is not None else "UNAVAILABLE"
    event_block = event_risk in policy.blocking_event_risk_states and restriction == "BLOCKED"
    if event_block:
        blockers.append("BLOCKING_EVENT_RISK")

    blocked = bool(blockers)
    unavailable_result = not directions
    if blocked:
        primary, status, entry = "BLOCKED", "BLOCKED", "BLOCKED"
        new_entries_allowed = False
        restriction = "BLOCKED"
    elif event_risk in policy.event_risk_override_states:
        primary, status = "EVENT_RISK", "READY_WITH_WARNINGS" if warnings else "READY"
        entry = "NOT_SUITABLE" if not new_entries_allowed else "CAUTION"
    elif contradictory:
        primary, status, entry = "CONFLICTING", "CONFLICTING", "NOT_SUITABLE"
    elif volatility in policy.high_volatility_override_states:
        primary, status, entry = "HIGH_VOLATILITY", "READY_WITH_WARNINGS" if warnings else "READY", "NOT_SUITABLE"
    elif unavailable_result:
        primary, status, entry = "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE"
        strength = confidence = 0.0
        new_entries_allowed = False
        restriction = "UNAVAILABLE"
        trend = volatility = breadth = confirmation_state = "UNAVAILABLE"
    else:
        status = "READY_WITH_WARNINGS" if warnings else "READY"
        if normalized_score > 0 and strength >= policy.strong_bullish_strength_threshold and confidence >= policy.strong_regime_confidence_threshold:
            primary = "STRONG_BULLISH"
        elif normalized_score > 0 and strength >= policy.bullish_strength_threshold and confidence >= policy.minimum_regime_confidence:
            primary = "BULLISH"
        elif normalized_score < 0 and strength >= policy.strong_bearish_strength_threshold and confidence >= policy.strong_regime_confidence_threshold:
            primary = "STRONG_BEARISH"
        elif normalized_score < 0 and strength >= policy.bearish_strength_threshold and confidence >= policy.minimum_regime_confidence:
            primary = "BEARISH"
        else:
            primary = "RANGE_BOUND"
        if not new_entries_allowed:
            entry = "NOT_SUITABLE"
        elif confidence >= policy.suitable_confidence_threshold and not warnings:
            entry = "SUITABLE"
        elif confidence >= policy.caution_confidence_threshold:
            entry = "CAUTION"
        else:
            entry = "NOT_SUITABLE"

    evidence = [f"{name}_USABLE" for name, *_ in directions]
    metadata = {
        "usable_components": tuple(name for name in _ORDER if name in usable),
        "unavailable_components": tuple(unavailable),
        "applied_penalties": tuple(applied_penalties),
        "aggregate_status_source": primary,
        "policy_schema_version": policy.schema_version,
    }
    return CanonicalMarketRegimeResultV1(
        market_regime_result_id=f"market-regime:{market_regime_input.market_regime_input_id}",
        created_at=aggregate_timestamp, underlying_symbol=market_regime_input.underlying_symbol,
        exchange=market_regime_input.exchange, technical_context=market_regime_input.technical_intelligence,
        broader_market_context=market_regime_input.broader_market_intelligence,
        external_market_context=market_regime_input.external_market_context, market_session_validation=market_regime_input.market_session_validation,
        context_status=status, directional_regime=primary if primary in {"STRONG_BULLISH", "BULLISH", "RANGE_BOUND", "BEARISH", "STRONG_BEARISH", "CONFLICTING", "UNAVAILABLE", "BLOCKED"} else ("UNAVAILABLE" if primary == "UNAVAILABLE" else "RANGE_BOUND"),
        trend_state=trend, volatility_state=volatility, market_condition="BLOCKED" if primary == "BLOCKED" else "EVENT_RISK" if primary == "EVENT_RISK" else "HIGH_VOLATILITY" if primary == "HIGH_VOLATILITY" else "CONFLICTING" if primary == "CONFLICTING" else "UNAVAILABLE" if primary == "UNAVAILABLE" else "NORMAL",
        confirmation_state=confirmation_state, entry_suitability=entry, regime_strength=strength, confidence=confidence,
        available_component_count=len(usable), unavailable_component_count=4-len(usable), confirming_component_count=confirmations,
        conflicting_component_count=int(contradictory), supporting_evidence=_clean(evidence), contradictions=_clean(contradictions), blockers=_clean(blockers), warnings=_clean(warnings), source_timestamps=timestamps,
        metadata=metadata, technical_regime_component=market_regime_input.technical_regime_component,
        broader_market_regime_component=market_regime_input.broader_market_regime_component,
        external_context_regime_component=market_regime_input.external_context_regime_component,
        primary_regime=primary, breadth_state=breadth, event_risk_state=event_risk,
        entry_restriction_state=restriction, analysis_allowed=analysis_allowed, new_entries_allowed=new_entries_allowed,
    )
