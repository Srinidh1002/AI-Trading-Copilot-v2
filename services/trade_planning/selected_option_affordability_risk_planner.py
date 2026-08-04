"""Task 3C affordability and risk planning for one certified option."""
from __future__ import annotations

from datetime import datetime
from math import isfinite

from services.contracts.capital_risk_authority_v1 import (
    CapitalRiskAuthorityInputV1,
    ExistingPositionExposureV1,
)
from services.contracts.selected_option_affordability_risk_result_v1 import (
    SelectedOptionAffordabilityRiskResultV1,
)
from services.contracts.selected_option_contract_certification_result_v1 import (
    SelectedOptionContractCertificationResultV1,
)
from services.trade_planning.capital_risk_authority import (
    evaluate_capital_risk_authority,
)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _number(
    value: object,
    name: str,
    *,
    positive: bool = False,
    maximum: float | None = None,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or (value <= 0.0 if positive else value < 0.0)
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(name)
    return float(value)


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool) or value <= 0:
        raise ValueError(name)
    return value


def _unavailable(
    *,
    affordability_result_id: str,
    certification: SelectedOptionContractCertificationResultV1,
    evaluated_at: datetime,
) -> SelectedOptionAffordabilityRiskResultV1:
    return SelectedOptionAffordabilityRiskResultV1(
        affordability_result_id=affordability_result_id,
        authority_input_id=None,
        authority_result_id=None,
        certification_result_id=certification.certification_result_id,
        parent_cycle_id=certification.parent_cycle_id,
        parent_decision_id=certification.parent_decision_id,
        bridge_result_id=certification.bridge_result_id,
        selected_child_result_id=certification.selected_child_result_id,
        candidate_id=certification.candidate_id,
        observation_id=certification.observation_id,
        ranking_result_id=certification.ranking_result_id,
        universe_id=certification.universe_id,
        contract_id=None,
        selected_market=None,
        direction=None,
        option_right=None,
        trading_symbol=None,
        instrument_token=None,
        expiry_date=None,
        strike=None,
        lot_size=None,
        premium=None,
        bid_price=None,
        ask_price=None,
        evaluated_at=evaluated_at,
        status="UNAVAILABLE",
        planning_allowed=False,
        blockers=tuple(
            dict.fromkeys(
                ("OPTION_CONTRACT_NOT_CERTIFIED",)
                + certification.blockers
            )
        ),
        warnings=certification.warnings,
    )


def plan_selected_option_affordability_risk(
    *,
    affordability_result_id: str,
    authority_input_id: str,
    authority_result_id: str,
    certification: SelectedOptionContractCertificationResultV1,
    evaluated_at: datetime,
    available_capital: float,
    risk_percentage: float,
    maximum_daily_loss: float,
    realized_daily_loss: float,
    existing_positions: tuple[ExistingPositionExposureV1, ...],
    minimum_traded_quantity: int,
    slippage_allowance_fraction: float,
    estimated_costs_per_lot: float = 0.0,
) -> SelectedOptionAffordabilityRiskResultV1:
    """Apply existing capital authority to exact Task 3B contract evidence."""

    if type(certification) is not SelectedOptionContractCertificationResultV1:
        raise TypeError("certification")

    result_id = _text(affordability_result_id, "affordability_result_id")
    input_id = _text(authority_input_id, "authority_input_id")
    authority_id = _text(authority_result_id, "authority_result_id")
    now = _aware(evaluated_at, "evaluated_at")

    capital = _number(available_capital, "available_capital", positive=True)
    risk = _number(
        risk_percentage,
        "risk_percentage",
        positive=True,
        maximum=1.0,
    )
    daily_limit = _number(
        maximum_daily_loss,
        "maximum_daily_loss",
        positive=True,
    )
    realized = _number(realized_daily_loss, "realized_daily_loss")
    minimum_quantity = _positive_int(
        minimum_traded_quantity,
        "minimum_traded_quantity",
    )
    slippage = _number(
        slippage_allowance_fraction,
        "slippage_allowance_fraction",
        maximum=1.0,
    )
    costs = _number(estimated_costs_per_lot, "estimated_costs_per_lot")

    if not isinstance(existing_positions, tuple):
        raise TypeError("existing_positions")
    if not all(
        type(item) is ExistingPositionExposureV1
        for item in existing_positions
    ):
        raise TypeError("existing_positions")

    if certification.status != "CERTIFIED":
        return _unavailable(
            affordability_result_id=result_id,
            certification=certification,
            evaluated_at=now,
        )

    authority_input = CapitalRiskAuthorityInputV1(
        authority_input_id=input_id,
        selected_market=certification.selected_market,
        evaluated_at=now,
        available_capital=capital,
        risk_percentage=risk,
        maximum_daily_loss=daily_limit,
        realized_daily_loss=realized,
        existing_positions=existing_positions,
        instrument_lot_size=certification.lot_size,
        premium=certification.premium,
        bid_price=certification.bid_price,
        ask_price=certification.ask_price,
        minimum_traded_quantity=minimum_quantity,
        observed_traded_quantity=max(1, int(certification.volume)),
        slippage_allowance_fraction=slippage,
        estimated_costs_per_lot=costs,
        warnings=certification.warnings,
    )
    authority = evaluate_capital_risk_authority(
        authority_result_id=authority_id,
        authority_input=authority_input,
    )

    return SelectedOptionAffordabilityRiskResultV1(
        affordability_result_id=result_id,
        authority_input_id=authority.authority_input_id,
        authority_result_id=authority.authority_result_id,
        certification_result_id=certification.certification_result_id,
        parent_cycle_id=certification.parent_cycle_id,
        parent_decision_id=certification.parent_decision_id,
        bridge_result_id=certification.bridge_result_id,
        selected_child_result_id=certification.selected_child_result_id,
        candidate_id=certification.candidate_id,
        observation_id=certification.observation_id,
        ranking_result_id=certification.ranking_result_id,
        universe_id=certification.universe_id,
        contract_id=certification.contract_id,
        selected_market=certification.selected_market,
        direction=certification.direction,
        option_right=certification.option_right,
        trading_symbol=certification.trading_symbol,
        instrument_token=certification.instrument_token,
        expiry_date=certification.expiry_date,
        strike=certification.strike,
        lot_size=certification.lot_size,
        premium=certification.premium,
        bid_price=certification.bid_price,
        ask_price=certification.ask_price,
        evaluated_at=now,
        status=authority.status,
        planning_allowed=authority.planning_allowed,
        total_capital=authority.total_capital,
        reserved_capital=authority.reserved_capital,
        deployable_capital=authority.deployable_capital,
        capital_risk_budget=authority.capital_risk_budget,
        daily_loss_remaining=authority.daily_loss_remaining,
        existing_open_risk=authority.existing_open_risk,
        maximum_new_loss=authority.maximum_new_loss,
        adjusted_entry_premium=authority.adjusted_entry_premium,
        estimated_one_lot_capital=authority.estimated_one_lot_capital,
        maximum_affordable_lots=authority.maximum_affordable_lots,
        blockers=authority.blockers,
        warnings=authority.warnings,
    )
