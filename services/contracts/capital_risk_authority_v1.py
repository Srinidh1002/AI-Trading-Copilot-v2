"""Authoritative PAPER-only capital and risk inputs for Task 4 planning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar


_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}


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
    minimum: float = 0.0,
    positive: bool = False,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise ValueError(name)
    number = float(value)
    if positive and number <= 0.0:
        raise ValueError(name)
    if not positive and number < minimum:
        raise ValueError(name)
    return number


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class ExistingPositionExposureV1:
    """Capital and loss already committed by one existing PAPER position."""

    position_id: str
    underlying_symbol: str
    exchange: str
    reserved_capital: float
    maximum_open_loss: float
    unrealized_loss: float = 0.0
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "position_id",
            _text(self.position_id, "position_id"),
        )
        market = (
            _text(
                self.underlying_symbol,
                "underlying_symbol",
            ).upper(),
            _text(self.exchange, "exchange").upper(),
        )
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(
            self,
            "underlying_symbol",
            market[0],
        )
        object.__setattr__(self, "exchange", market[1])

        for name in (
            "reserved_capital",
            "maximum_open_loss",
            "unrealized_loss",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name),
            )

        if self.maximum_open_loss > self.reserved_capital:
            raise ValueError(
                "maximum_open_loss exceeds reserved_capital"
            )
        if self.unrealized_loss > self.maximum_open_loss:
            raise ValueError(
                "unrealized_loss exceeds maximum_open_loss"
            )
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
        ):
            raise ValueError("PAPER-only position exposure")


@dataclass(frozen=True, slots=True)
class CapitalRiskAuthorityInputV1:
    """Complete caller-supplied capital, risk and contract evidence."""

    SCHEMA_VERSION: ClassVar[str] = "capital_risk_authority_input.v1"

    authority_input_id: str
    selected_market: tuple[str, str]
    evaluated_at: datetime
    available_capital: float
    risk_percentage: float
    maximum_daily_loss: float
    realized_daily_loss: float
    existing_positions: tuple[ExistingPositionExposureV1, ...]
    instrument_lot_size: int
    premium: float
    bid_price: float
    ask_price: float
    minimum_traded_quantity: int
    observed_traded_quantity: int
    slippage_allowance_fraction: float
    estimated_costs_per_lot: float = 0.0
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authority_input_id",
            _text(self.authority_input_id, "authority_input_id"),
        )
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
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        for name in (
            "available_capital",
            "maximum_daily_loss",
            "premium",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name, positive=True),
            )
        for name in (
            "realized_daily_loss",
            "bid_price",
            "ask_price",
            "slippage_allowance_fraction",
            "estimated_costs_per_lot",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name),
            )

        risk = _number(
            self.risk_percentage,
            "risk_percentage",
            positive=True,
        )
        if risk > 1.0:
            raise ValueError(
                "risk_percentage must be a fraction not percent points"
            )
        object.__setattr__(self, "risk_percentage", risk)

        if self.slippage_allowance_fraction > 1.0:
            raise ValueError("slippage_allowance_fraction")
        if self.bid_price > self.ask_price:
            raise ValueError("bid_price exceeds ask_price")
        if not self.bid_price <= self.premium <= self.ask_price:
            raise ValueError(
                "premium must be within supplied bid/ask"
            )
        if self.realized_daily_loss > self.maximum_daily_loss:
            raise ValueError(
                "realized_daily_loss exceeds maximum_daily_loss"
            )

        for name in (
            "instrument_lot_size",
            "minimum_traded_quantity",
            "observed_traded_quantity",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(name)

        if not isinstance(self.existing_positions, tuple):
            raise TypeError("existing_positions")
        if not all(
            type(item) is ExistingPositionExposureV1
            for item in self.existing_positions
        ):
            raise TypeError("existing_positions")
        ids = tuple(
            item.position_id for item in self.existing_positions
        )
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate existing position_id")

        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only authority input")


@dataclass(frozen=True, slots=True)
class CapitalRiskAuthorityResultV1:
    """Deterministic capital and risk budget available to later planning."""

    SCHEMA_VERSION: ClassVar[str] = "capital_risk_authority_result.v1"

    authority_result_id: str
    authority_input_id: str
    selected_market: tuple[str, str]
    evaluated_at: datetime
    status: str
    planning_allowed: bool
    total_capital: float
    reserved_capital: float
    deployable_capital: float
    capital_risk_budget: float
    daily_loss_remaining: float
    existing_open_risk: float
    maximum_new_loss: float
    adjusted_entry_premium: float
    estimated_one_lot_capital: float
    maximum_affordable_lots: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("authority_result_id", "authority_input_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        if (
            not isinstance(self.selected_market, tuple)
            or tuple(self.selected_market) not in _MARKETS
        ):
            raise ValueError("selected_market")
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        status = _text(self.status, "status").upper()
        if status not in {"READY", "BLOCKED"}:
            raise ValueError("status")
        object.__setattr__(self, "status", status)
        if type(self.planning_allowed) is not bool:
            raise TypeError("planning_allowed")

        for name in (
            "total_capital",
            "reserved_capital",
            "deployable_capital",
            "capital_risk_budget",
            "daily_loss_remaining",
            "existing_open_risk",
            "maximum_new_loss",
            "adjusted_entry_premium",
            "estimated_one_lot_capital",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name),
            )
        if (
            type(self.maximum_affordable_lots) is not int
            or self.maximum_affordable_lots < 0
        ):
            raise ValueError("maximum_affordable_lots")

        for name in ("blockers", "warnings"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if self.reserved_capital > self.total_capital:
            raise ValueError("reserved_capital")
        if self.deployable_capital > self.total_capital:
            raise ValueError("deployable_capital")
        if self.maximum_new_loss > min(
            self.capital_risk_budget,
            self.daily_loss_remaining,
        ) + 1e-9:
            raise ValueError("maximum_new_loss")
        if self.maximum_affordable_lots > 0:
            if (
                self.estimated_one_lot_capital
                * self.maximum_affordable_lots
                > self.deployable_capital + 1e-9
            ):
                raise ValueError(
                    "maximum_affordable_lots exceeds capital"
                )

        if status == "READY":
            if (
                not self.planning_allowed
                or self.blockers
                or self.maximum_affordable_lots < 1
                or self.maximum_new_loss <= 0.0
            ):
                raise ValueError("READY coherence")
        else:
            if self.planning_allowed or not self.blockers:
                raise ValueError("BLOCKED coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only authority result")
