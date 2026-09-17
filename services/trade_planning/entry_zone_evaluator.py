"""Pure deterministic entry-zone evaluation for a validated planning input."""
from __future__ import annotations

from typing import Any

from services.contracts.entry_zone_evaluation_input_v1 import EntryZoneEvaluationInputV1
from services.contracts.entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from services.contracts.trade_planning_policy_v1 import TradePlanningPolicyV1


_REFERENCE_PRIORITY = ("OPTION_MID", "OPTION_ASK", "LAST_TRADED_PRICE", "SIGNAL_REFERENCE")


def _deduplicated(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def evaluate_entry_zone(
    evaluation_input: EntryZoneEvaluationInputV1,
    policy: TradePlanningPolicyV1,
) -> EntryZoneEvaluationResultV1:
    if type(evaluation_input) is not EntryZoneEvaluationInputV1:
        raise TypeError("evaluation_input must be EntryZoneEvaluationInputV1")
    if type(policy) is not TradePlanningPolicyV1:
        raise TypeError("policy must be TradePlanningPolicyV1")

    policy_mismatch = (
        evaluation_input.policy_id != policy.policy_id
        or evaluation_input.entry_reference_method != policy.entry_reference_method
        or evaluation_input.execution_mode != "PAPER"
        or policy.execution_mode != "PAPER"
        or evaluation_input.live_execution_eligible is not False
        or policy.live_execution_eligible is not False
    )
    early_blockers = evaluation_input.blockers
    if not evaluation_input.planning_allowed:
        early_blockers += ("ENTRY_PLANNING_NOT_ALLOWED",)
    if policy_mismatch:
        early_blockers += ("ENTRY_POLICY_MISMATCH",)

    def result(
        *,
        status: str,
        entry_method: str,
        selected_reference_source: str | None = None,
        entry_reference_price: float | None = None,
        entry_zone_lower: float | None = None,
        entry_zone_upper: float | None = None,
        entry_tolerance_fraction: float | None = None,
        maximum_chase_price: float | None = None,
        maximum_entry_premium: float | None = None,
        effective_spread_fraction: float | None = None,
        effective_spread_limit: float | None = None,
        blockers: tuple[str, ...] = (),
        warnings: tuple[str, ...] = evaluation_input.warnings,
    ) -> EntryZoneEvaluationResultV1:
        metadata: dict[str, Any] = {
            "input_metadata": evaluation_input.to_dict()["metadata"],
            "selected_reference_source": selected_reference_source,
            "effective_premium_limit": maximum_entry_premium,
            "effective_spread_limit": effective_spread_limit,
            "quote_timestamp": evaluation_input.option_quote_timestamp.isoformat(),
            "trade_plan_input_id": evaluation_input.trade_plan_input_id,
            "policy_id": policy.policy_id,
        }
        return EntryZoneEvaluationResultV1(
            evaluation_result_id=evaluation_input.evaluation_result_id,
            evaluation_id=evaluation_input.evaluation_id,
            evaluated_at=evaluation_input.evaluated_at,
            underlying_symbol=evaluation_input.underlying_symbol,
            exchange=evaluation_input.exchange,
            direction=evaluation_input.direction,
            option_right=evaluation_input.option_right,
            entry_method=entry_method,
            selected_reference_source=selected_reference_source,
            status=status,
            entry_reference_price=entry_reference_price,
            entry_zone_lower=entry_zone_lower,
            entry_zone_upper=entry_zone_upper,
            entry_tolerance_fraction=entry_tolerance_fraction,
            maximum_chase_price=maximum_chase_price,
            maximum_entry_premium=maximum_entry_premium,
            effective_spread_fraction=effective_spread_fraction,
            effective_spread_limit=effective_spread_limit,
            require_limit_entry=policy.require_limit_entry,
            blockers=_deduplicated(blockers),
            warnings=_deduplicated(warnings),
            decision_reasons=(),
            source_timestamps=dict(evaluation_input.source_timestamps),
            metadata=metadata,
            execution_mode="PAPER",
            live_execution_eligible=False,
            schema_version="1.0",
        )

    if early_blockers:
        return result(
            status="BLOCKED",
            entry_method=evaluation_input.entry_reference_method,
            blockers=early_blockers,
        )

    price_by_source = {
        "OPTION_MID": evaluation_input.option_mid_price,
        "OPTION_ASK": evaluation_input.ask_price,
        "LAST_TRADED_PRICE": evaluation_input.last_traded_price,
        "SIGNAL_REFERENCE": evaluation_input.signal_reference_price,
    }
    entry_method = policy.entry_reference_method
    selected_reference_source = (
        next((source for source in _REFERENCE_PRIORITY if price_by_source[source] is not None), None)
        if entry_method == "HYBRID"
        else entry_method
    )
    entry_reference_price = price_by_source[selected_reference_source] if selected_reference_source else None
    warnings = evaluation_input.warnings
    if entry_method == "HYBRID" and selected_reference_source not in {None, "OPTION_MID"}:
        warnings += ("ENTRY_HYBRID_FALLBACK_USED",)

    if entry_reference_price is None:
        return result(
            status="BLOCKED",
            entry_method=entry_method,
            blockers=("ENTRY_REFERENCE_UNAVAILABLE",),
            warnings=warnings,
        )

    entry_zone_lower = entry_reference_price * (1 - policy.entry_tolerance_below_fraction)
    entry_zone_upper = entry_reference_price * (1 + policy.entry_tolerance_above_fraction)
    entry_tolerance_fraction = max(
        policy.entry_tolerance_below_fraction,
        policy.entry_tolerance_above_fraction,
    )
    maximum_chase_price = entry_reference_price * (1 + policy.maximum_chase_fraction)

    premium_limits = tuple(
        value
        for value in (evaluation_input.maximum_entry_premium, policy.maximum_entry_premium)
        if value is not None
    )
    maximum_entry_premium = min(premium_limits) if premium_limits else None
    spread_limits = tuple(
        value
        for value in (evaluation_input.maximum_spread_fraction, policy.maximum_spread_fraction)
        if value is not None
    )
    effective_spread_limit = min(spread_limits) if spread_limits else None

    blockers: tuple[str, ...] = ()
    if maximum_entry_premium is not None and (
        entry_reference_price > maximum_entry_premium
        or entry_zone_upper > maximum_entry_premium
        or maximum_chase_price > maximum_entry_premium
    ):
        blockers += ("ENTRY_PREMIUM_LIMIT_EXCEEDED",)

    effective_spread_fraction = None
    if evaluation_input.bid_price is not None and evaluation_input.ask_price is not None:
        spread_basis = evaluation_input.option_mid_price or entry_reference_price
        effective_spread_fraction = (evaluation_input.ask_price - evaluation_input.bid_price) / spread_basis
        if effective_spread_limit is not None and effective_spread_fraction > effective_spread_limit:
            blockers += ("ENTRY_SPREAD_LIMIT_EXCEEDED",)

    return result(
        status="BLOCKED" if blockers else "READY",
        entry_method=entry_method,
        selected_reference_source=selected_reference_source,
        entry_reference_price=entry_reference_price,
        entry_zone_lower=entry_zone_lower,
        entry_zone_upper=entry_zone_upper,
        entry_tolerance_fraction=entry_tolerance_fraction,
        maximum_chase_price=maximum_chase_price,
        maximum_entry_premium=maximum_entry_premium,
        effective_spread_fraction=effective_spread_fraction,
        effective_spread_limit=effective_spread_limit,
        blockers=blockers,
        warnings=warnings,
    )
