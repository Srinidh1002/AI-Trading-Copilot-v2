"""Typed Task 3C selected-option affordability and risk result."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import ClassVar


_STATUSES = {"READY", "BLOCKED", "UNAVAILABLE"}
_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_DIRECTIONS = {"BULLISH", "BEARISH"}
_RIGHTS = {"CALL", "PUT"}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _optional_number(
    value: object,
    name: str,
    *,
    positive: bool = False,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or (value <= 0.0 if positive else value < 0.0)
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class SelectedOptionAffordabilityRiskResultV1:
    """Certified contract affordability and risk authority for PAPER planning."""

    SCHEMA_VERSION: ClassVar[str] = (
        "selected_option_affordability_risk_result.v1"
    )

    affordability_result_id: str
    authority_input_id: str | None
    authority_result_id: str | None
    certification_result_id: str
    parent_cycle_id: str
    parent_decision_id: str
    bridge_result_id: str
    selected_child_result_id: str | None
    candidate_id: str | None
    observation_id: str | None
    ranking_result_id: str | None
    universe_id: str | None
    contract_id: str | None
    selected_market: tuple[str, str] | None
    direction: str | None
    option_right: str | None
    trading_symbol: str | None
    instrument_token: str | None
    expiry_date: date | None
    strike: float | None
    lot_size: int | None
    premium: float | None
    bid_price: float | None
    ask_price: float | None
    evaluated_at: datetime
    status: str
    planning_allowed: bool
    total_capital: float | None = None
    reserved_capital: float | None = None
    deployable_capital: float | None = None
    capital_risk_budget: float | None = None
    daily_loss_remaining: float | None = None
    existing_open_risk: float | None = None
    maximum_new_loss: float | None = None
    adjusted_entry_premium: float | None = None
    estimated_one_lot_capital: float | None = None
    maximum_affordable_lots: int | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "affordability_result_id",
            "certification_result_id",
            "parent_cycle_id",
            "parent_decision_id",
            "bridge_result_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        for name in (
            "authority_input_id",
            "authority_result_id",
            "selected_child_result_id",
            "candidate_id",
            "observation_id",
            "ranking_result_id",
            "universe_id",
            "contract_id",
            "trading_symbol",
            "instrument_token",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        status = _text(self.status, "status").upper()
        if status not in _STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        if type(self.planning_allowed) is not bool:
            raise TypeError("planning_allowed")

        if self.selected_market is not None:
            if (
                not isinstance(self.selected_market, tuple)
                or len(self.selected_market) != 2
            ):
                raise TypeError("selected_market")
            market = tuple(
                _text(item, "selected_market").upper()
                for item in self.selected_market
            )
            if market not in _MARKETS:
                raise ValueError("selected_market")
            object.__setattr__(self, "selected_market", market)

        if self.direction is not None:
            direction = _text(self.direction, "direction").upper()
            if direction not in _DIRECTIONS:
                raise ValueError("direction")
            object.__setattr__(self, "direction", direction)

        if self.option_right is not None:
            option_right = _text(self.option_right, "option_right").upper()
            if option_right not in _RIGHTS:
                raise ValueError("option_right")
            object.__setattr__(self, "option_right", option_right)

        if self.expiry_date is not None and not isinstance(
            self.expiry_date,
            date,
        ):
            raise TypeError("expiry_date")

        if self.lot_size is not None and (
            type(self.lot_size) is not int
            or isinstance(self.lot_size, bool)
            or self.lot_size <= 0
        ):
            raise ValueError("lot_size")

        if self.maximum_affordable_lots is not None and (
            type(self.maximum_affordable_lots) is not int
            or isinstance(self.maximum_affordable_lots, bool)
            or self.maximum_affordable_lots < 0
        ):
            raise ValueError("maximum_affordable_lots")

        for name, positive in (
            ("strike", True),
            ("premium", True),
            ("bid_price", True),
            ("ask_price", True),
            ("total_capital", False),
            ("reserved_capital", False),
            ("deployable_capital", False),
            ("capital_risk_budget", False),
            ("daily_loss_remaining", False),
            ("existing_open_risk", False),
            ("maximum_new_loss", False),
            ("adjusted_entry_premium", False),
            ("estimated_one_lot_capital", False),
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(self, name),
                    name,
                    positive=positive,
                ),
            )

        for name in ("blockers", "warnings"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        contract_group = (
            self.contract_id,
            self.selected_market,
            self.direction,
            self.option_right,
            self.trading_symbol,
            self.instrument_token,
            self.expiry_date,
            self.strike,
            self.lot_size,
            self.premium,
            self.bid_price,
            self.ask_price,
        )
        authority_group = (
            self.authority_input_id,
            self.authority_result_id,
            self.total_capital,
            self.reserved_capital,
            self.deployable_capital,
            self.capital_risk_budget,
            self.daily_loss_remaining,
            self.existing_open_risk,
            self.maximum_new_loss,
            self.adjusted_entry_premium,
            self.estimated_one_lot_capital,
            self.maximum_affordable_lots,
        )

        if status == "READY":
            if (
                not self.planning_allowed
                or self.blockers
                or any(value is None for value in contract_group)
                or any(value is None for value in authority_group)
                or self.maximum_affordable_lots < 1
                or self.maximum_new_loss <= 0.0
            ):
                raise ValueError("READY coherence")
        elif status == "BLOCKED":
            if (
                self.planning_allowed
                or not self.blockers
                or any(value is None for value in contract_group)
                or any(value is None for value in authority_group)
            ):
                raise ValueError("BLOCKED coherence")
        else:
            if (
                self.planning_allowed
                or not self.blockers
                or any(value is not None for value in contract_group)
                or any(value is not None for value in authority_group)
            ):
                raise ValueError("UNAVAILABLE coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only affordability result")

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, datetime):
                values[name] = value.isoformat()
            elif isinstance(value, date):
                values[name] = value.isoformat()
            elif isinstance(value, tuple):
                values[name] = list(value)
            else:
                values[name] = value
        values["schema_version"] = self.SCHEMA_VERSION
        return values

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
