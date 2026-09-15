"""Deterministic, provider-free Task 9 PAPER trading-cost authority."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from services.contracts.capital_quantity_trading_cost_evidence_v1 import (
    CapitalQuantityTradingCostEvidenceV1,
)
from services.contracts.capital_quantity_trading_cost_policy_v1 import (
    CapitalQuantityTradingCostPolicyV1,
)


TASK9_LOCAL_EVIDENCE_SOURCE = "TASK9_LOCAL_FIXED_ASSUMPTION_MODEL"


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise ValueError(name)
    return value


def _non_negative(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0.0
    ):
        raise ValueError(name)
    return float(value)


def calculate_task9_local_paper_cost_evidence(
    *,
    policy: CapitalQuantityTradingCostPolicyV1,
    planning_input_id: str,
    trade_plan_id: str,
    option_selection_result_id: str,
    planned_lot_count: int,
    lot_size: int,
    estimated_premium_outlay: float,
    evidence_timestamp: datetime,
    evidence_id: str | None = None,
    caller_supplied_gst_taxable_base: float | None = None,
    warnings: tuple[str, ...] = (),
    source_timestamps: Mapping[str, datetime] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> CapitalQuantityTradingCostEvidenceV1:
    """Calculate the canonical Task 9 cost evidence without external I/O.

    The FIXED_ASSUMPTION_MODEL component semantics deliberately match Task 8.
    A caller-supplied GST base is required only for the policy's explicit
    CALLER_SUPPLIED taxable-base mode.
    """
    if type(policy) is not CapitalQuantityTradingCostPolicyV1:
        raise TypeError("policy")
    lots = _positive_int(planned_lot_count, "planned_lot_count")
    size = _positive_int(lot_size, "lot_size")
    premium_outlay = _non_negative(
        estimated_premium_outlay, "estimated_premium_outlay"
    )
    if not isinstance(evidence_timestamp, datetime) or evidence_timestamp.tzinfo is None:
        raise ValueError("evidence_timestamp")

    brokerage = (
        policy.brokerage_fixed_per_order * policy.estimated_order_count
        + premium_outlay * policy.brokerage_rate_fraction
        if policy.apply_brokerage
        else 0.0
    )
    exchange = (
        premium_outlay * policy.exchange_transaction_charge_fraction
        if policy.apply_exchange_transaction_charges else 0.0
    )
    clearing = (
        premium_outlay * policy.clearing_charge_fraction
        if policy.apply_clearing_charges else 0.0
    )
    stt = premium_outlay * policy.stt_rate_fraction if policy.apply_stt else 0.0
    sebi = premium_outlay * policy.sebi_charge_fraction if policy.apply_sebi_charges else 0.0
    stamp_duty = premium_outlay * policy.stamp_duty_rate_fraction if policy.apply_stamp_duty else 0.0
    slippage = premium_outlay * policy.slippage_rate_fraction if policy.apply_slippage else 0.0

    if policy.gst_taxable_base_mode == "CALLER_SUPPLIED":
        if caller_supplied_gst_taxable_base is None:
            raise ValueError("caller_supplied_gst_taxable_base")
        gst_base = _non_negative(
            caller_supplied_gst_taxable_base, "caller_supplied_gst_taxable_base"
        )
    else:
        gst_base = brokerage + exchange + clearing + sebi
    gst = gst_base * policy.gst_rate_fraction if policy.apply_gst else 0.0

    total_cost = brokerage + exchange + clearing + stt + sebi + stamp_duty + gst + slippage
    total_capital = premium_outlay + total_cost
    return CapitalQuantityTradingCostEvidenceV1(
        evidence_id=(
            evidence_id
            or f"task9-local-cost-evidence:{planning_input_id}:{policy.cost_policy_id}"
        ),
        planning_input_id=planning_input_id,
        trade_plan_id=trade_plan_id,
        cost_policy_id=policy.cost_policy_id,
        option_selection_result_id=option_selection_result_id,
        planned_lot_count=lots,
        lot_size=size,
        planned_quantity=lots * size,
        estimated_premium_outlay=premium_outlay,
        estimated_order_count=policy.estimated_order_count,
        estimated_brokerage=brokerage,
        estimated_exchange_transaction_charges=exchange,
        estimated_clearing_charges=clearing,
        estimated_stt=stt,
        estimated_sebi_charges=sebi,
        estimated_stamp_duty=stamp_duty,
        estimated_gst=gst,
        estimated_slippage=slippage,
        estimated_total_trading_cost=total_cost,
        estimated_total_capital_requirement=total_capital,
        applied_slippage_rate_fraction=(
            policy.slippage_rate_fraction if policy.apply_slippage else 0.0
        ),
        applied_effective_cost_fraction=(
            total_cost / premium_outlay
            if premium_outlay and total_cost / premium_outlay <= 1.0
            else None
        ),
        evidence_timestamp=evidence_timestamp,
        evidence_source=TASK9_LOCAL_EVIDENCE_SOURCE,
        warnings=warnings,
        source_timestamps=dict(source_timestamps or {}),
        metadata={"cost_authority": "TASK9_LOCAL", **dict(metadata or {})},
    )
