"""Build the authoritative capital and risk budget before P6 planning."""
from __future__ import annotations

from math import floor

from services.contracts.capital_risk_authority_v1 import (
    CapitalRiskAuthorityInputV1,
    CapitalRiskAuthorityResultV1,
)


def evaluate_capital_risk_authority(
    *,
    authority_result_id: str,
    authority_input: CapitalRiskAuthorityInputV1,
) -> CapitalRiskAuthorityResultV1:
    """Fail closed unless both capital and risk permit at least one lot."""

    if type(authority_input) is not CapitalRiskAuthorityInputV1:
        raise TypeError("authority_input")

    reserved_capital = sum(
        item.reserved_capital
        for item in authority_input.existing_positions
    )
    existing_open_risk = sum(
        item.maximum_open_loss
        for item in authority_input.existing_positions
    )
    deployable_capital = max(
        0.0,
        authority_input.available_capital - reserved_capital,
    )
    capital_risk_budget = (
        authority_input.available_capital
        * authority_input.risk_percentage
    )
    daily_loss_remaining = max(
        0.0,
        authority_input.maximum_daily_loss
        - authority_input.realized_daily_loss
        - existing_open_risk,
    )
    maximum_new_loss = max(
        0.0,
        min(capital_risk_budget, daily_loss_remaining),
    )

    adjusted_entry_premium = (
        authority_input.ask_price
        * (1.0 + authority_input.slippage_allowance_fraction)
    )
    estimated_one_lot_capital = (
        adjusted_entry_premium
        * authority_input.instrument_lot_size
        + authority_input.estimated_costs_per_lot
    )
    affordable_lots = (
        floor(deployable_capital / estimated_one_lot_capital)
        if estimated_one_lot_capital > 0.0
        else 0
    )

    blockers: list[str] = []
    warnings = list(authority_input.warnings)

    if reserved_capital >= authority_input.available_capital:
        blockers.append("NO_DEPLOYABLE_CAPITAL")
    if daily_loss_remaining <= 0.0:
        blockers.append("MAXIMUM_DAILY_LOSS_EXHAUSTED")
    if maximum_new_loss <= 0.0:
        blockers.append("NO_NEW_RISK_BUDGET")
    if affordable_lots < 1:
        blockers.append("CAPITAL_INSUFFICIENT_FOR_ONE_LOT")
    if (
        authority_input.observed_traded_quantity
        < authority_input.minimum_traded_quantity
    ):
        blockers.append("INSUFFICIENT_LIQUIDITY")

    spread_fraction = (
        (authority_input.ask_price - authority_input.bid_price)
        / authority_input.premium
    )
    if spread_fraction > authority_input.slippage_allowance_fraction:
        blockers.append("SPREAD_EXCEEDS_ALLOWANCE")
    elif spread_fraction > 0.0:
        warnings.append(
            f"OBSERVED_SPREAD_FRACTION={spread_fraction:.6f}"
        )

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    ready = not blockers

    return CapitalRiskAuthorityResultV1(
        authority_result_id=authority_result_id,
        authority_input_id=authority_input.authority_input_id,
        selected_market=authority_input.selected_market,
        evaluated_at=authority_input.evaluated_at,
        status="READY" if ready else "BLOCKED",
        planning_allowed=ready,
        total_capital=authority_input.available_capital,
        reserved_capital=reserved_capital,
        deployable_capital=deployable_capital,
        capital_risk_budget=capital_risk_budget,
        daily_loss_remaining=daily_loss_remaining,
        existing_open_risk=existing_open_risk,
        maximum_new_loss=maximum_new_loss,
        adjusted_entry_premium=adjusted_entry_premium,
        estimated_one_lot_capital=estimated_one_lot_capital,
        maximum_affordable_lots=affordable_lots,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
    )
