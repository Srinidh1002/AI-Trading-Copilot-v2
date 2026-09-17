from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from .paper_market_observation_v1 import (
    _aware_datetime,
    _finite_number,
    _freeze_json_value,
    _freeze_warnings,
    _nonblank_text,
    _plain_json_value,
)
from .paper_trade_fill_v1 import PaperTradeFillV1
from services.core.market_identity import is_supported_market_identity


def _exact_nonnegative_int(value: object, field_name: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an exact int")
    if value < 0:
        raise ValueError(f"{field_name} must be nonnegative")
    return value


def _exact_positive_int(value: object, field_name: str) -> int:
    value = _exact_nonnegative_int(value, field_name)
    if value == 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _finite_signed_number(value: object, field_name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return numeric


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def _freeze_fill_tuple(value: object, field_name: str) -> tuple[PaperTradeFillV1, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{field_name} must be an exact tuple")
    if any(type(fill) is not PaperTradeFillV1 for fill in value):
        raise TypeError(f"{field_name} must contain exact PaperTradeFillV1 values")
    return value


@dataclass(frozen=True, slots=True)
class PaperTradePositionV1:
    position_id: str
    trade_plan_id: str
    integrated_trade_plan_result_id: str
    lifecycle_policy_id: str
    lifecycle_state_id: str
    selected_option_contract_id: str
    market: str
    underlying_symbol: str
    option_symbol: str
    direction: str
    option_type: str
    strike: float
    expiry: str
    entry_fill: PaperTradeFillV1
    entry_price: float
    opened_at: datetime
    initial_lot_count: int
    lot_size: int
    initial_quantity: int
    remaining_lot_count: int
    remaining_quantity: int
    target_1_lot_count: int
    target_2_lot_count: int
    target_3_lot_count: int
    runner_lot_count: int
    stop_loss: float
    target_1: float
    target_2: float
    target_3: float
    estimated_premium_outlay: float
    estimated_risk_amount: float
    estimated_total_trading_cost: float
    estimated_total_capital_requirement: float
    lifecycle_state: str = "OPEN"
    exit_fills: tuple[PaperTradeFillV1, ...] = ()
    realized_gross_pnl: float = 0.0
    realized_net_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"
    exchange: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "position_id",
            "trade_plan_id",
            "integrated_trade_plan_result_id",
            "lifecycle_policy_id",
            "lifecycle_state_id",
            "selected_option_contract_id",
            "market",
            "underlying_symbol",
            "option_symbol",
            "direction",
            "option_type",
            "expiry",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonblank_text(getattr(self, field_name), field_name),
            )

        if self.exchange is not None:
            object.__setattr__(
                self,
                "exchange",
                _nonblank_text(self.exchange, "exchange"),
            )
            if not is_supported_market_identity(
                self.underlying_symbol,
                self.exchange,
            ):
                raise ValueError("exchange must match underlying_symbol")

        if type(self.entry_fill) is not PaperTradeFillV1:
            raise TypeError("entry_fill must be an exact PaperTradeFillV1")
        if self.entry_fill.fill_type != "ENTRY":
            raise ValueError("entry_fill must have fill_type ENTRY")
        if self.entry_fill.fill_reason != "ENTRY_ACTIVATED":
            raise ValueError("entry_fill must use ENTRY_ACTIVATED")
        if self.entry_fill.side != "BUY":
            raise ValueError("entry_fill must use BUY")

        identity_pairs = (
            ("position_id", self.position_id, self.entry_fill.position_id),
            ("trade_plan_id", self.trade_plan_id, self.entry_fill.trade_plan_id),
            (
                "integrated_trade_plan_result_id",
                self.integrated_trade_plan_result_id,
                self.entry_fill.integrated_trade_plan_result_id,
            ),
            (
                "selected_option_contract_id",
                self.selected_option_contract_id,
                self.entry_fill.selected_option_contract_id,
            ),
        )
        for field_name, position_value, fill_value in identity_pairs:
            if position_value != fill_value:
                raise ValueError(f"{field_name} must match entry_fill")

        object.__setattr__(
            self,
            "entry_price",
            _finite_number(
                self.entry_price,
                "entry_price",
                required=True,
                minimum=0.0,
                strictly_greater=True,
            ),
        )
        if not _close(self.entry_price, self.entry_fill.fill_price):
            raise ValueError("entry_price must equal entry_fill.fill_price")

        object.__setattr__(
            self,
            "opened_at",
            _aware_datetime(self.opened_at, "opened_at"),
        )
        if self.opened_at != self.entry_fill.filled_at:
            raise ValueError("opened_at must equal entry_fill.filled_at")

        object.__setattr__(
            self,
            "initial_lot_count",
            _exact_positive_int(self.initial_lot_count, "initial_lot_count"),
        )
        object.__setattr__(
            self,
            "lot_size",
            _exact_positive_int(self.lot_size, "lot_size"),
        )
        object.__setattr__(
            self,
            "initial_quantity",
            _exact_positive_int(self.initial_quantity, "initial_quantity"),
        )
        object.__setattr__(
            self,
            "remaining_lot_count",
            _exact_nonnegative_int(self.remaining_lot_count, "remaining_lot_count"),
        )
        object.__setattr__(
            self,
            "remaining_quantity",
            _exact_nonnegative_int(self.remaining_quantity, "remaining_quantity"),
        )
        for field_name in (
            "target_1_lot_count",
            "target_2_lot_count",
            "target_3_lot_count",
            "runner_lot_count",
        ):
            object.__setattr__(
                self,
                field_name,
                _exact_nonnegative_int(getattr(self, field_name), field_name),
            )

        if self.initial_quantity != self.initial_lot_count * self.lot_size:
            raise ValueError("initial_quantity is incoherent")
        if self.entry_fill.filled_lot_count != self.initial_lot_count:
            raise ValueError("entry fill lots must equal initial_lot_count")
        if self.entry_fill.lot_size != self.lot_size:
            raise ValueError("entry fill lot_size must match position lot_size")
        if self.entry_fill.filled_quantity != self.initial_quantity:
            raise ValueError("entry fill quantity must equal initial_quantity")

        if self.lifecycle_state not in {"OPEN", "PARTIALLY_EXITED", "CLOSED_TARGET_1", "CLOSED_TARGET_2", "CLOSED_TARGET_3", "CLOSED_STOP", "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED"}:
            raise ValueError("unsupported position lifecycle_state")
        if self.remaining_quantity != self.remaining_lot_count * self.lot_size:
            raise ValueError("remaining quantity is incoherent")

        allocation_total = (
            self.target_1_lot_count
            + self.target_2_lot_count
            + self.target_3_lot_count
            + self.runner_lot_count
        )
        if allocation_total not in (0, self.initial_lot_count):
            raise ValueError(
                "target and runner allocations must sum to zero or initial lots"
            )

        object.__setattr__(
            self,
            "strike",
            _finite_number(
                self.strike,
                "strike",
                required=True,
                minimum=0.0,
                strictly_greater=True,
            ),
        )
        for field_name in ("stop_loss", "target_1", "target_2", "target_3"):
            object.__setattr__(
                self,
                field_name,
                _finite_number(
                    getattr(self, field_name),
                    field_name,
                    required=True,
                    minimum=0.0,
                    strictly_greater=True,
                ),
            )
        if not self.stop_loss < self.target_1 < self.target_2 < self.target_3:
            raise ValueError("stop and target values must be strictly ordered")

        for field_name in (
            "estimated_premium_outlay",
            "estimated_risk_amount",
            "estimated_total_trading_cost",
            "estimated_total_capital_requirement",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite_number(
                    getattr(self, field_name),
                    field_name,
                    required=True,
                    minimum=0.0,
                ),
            )
        if (
            self.estimated_total_capital_requirement
            + 1e-9
            < self.estimated_premium_outlay + self.estimated_total_trading_cost
        ):
            raise ValueError(
                "total capital requirement cannot be below premium outlay plus cost"
            )

        object.__setattr__(
            self,
            "exit_fills",
            _freeze_fill_tuple(self.exit_fills, "exit_fills"),
        )
        exit_quantity = 0
        seen_fill_ids: set[str] = set()
        for fill in self.exit_fills:
            if fill.fill_type != "EXIT" or fill.side != "SELL": raise ValueError("exit fill semantics")
            if (fill.position_id, fill.trade_plan_id, fill.integrated_trade_plan_result_id, fill.selected_option_contract_id) != (self.position_id, self.trade_plan_id, self.integrated_trade_plan_result_id, self.selected_option_contract_id): raise ValueError("exit fill identity")
            if fill.fill_id in seen_fill_ids: raise ValueError("duplicate exit fill")
            seen_fill_ids.add(fill.fill_id); exit_quantity += fill.filled_quantity
        if exit_quantity != self.initial_quantity - self.remaining_quantity: raise ValueError("exit quantity is incoherent")
        terminal = self.lifecycle_state.startswith("CLOSED_") or self.lifecycle_state == "CANCELLED"
        if self.lifecycle_state == "OPEN" and (self.exit_fills or self.remaining_quantity != self.initial_quantity): raise ValueError("OPEN invariants")
        if self.lifecycle_state == "PARTIALLY_EXITED" and (not self.exit_fills or not 0 < self.remaining_quantity < self.initial_quantity): raise ValueError("partial exit invariants")
        if terminal and (not self.exit_fills or self.remaining_quantity != 0): raise ValueError("terminal exit invariants")
        if self.lifecycle_state == "CANCELLED" and not any(fill.fill_reason == "CANCELLED" and fill.target_name is None for fill in self.exit_fills): raise ValueError("cancellation evidence")

        for field_name in (
            "realized_gross_pnl",
            "realized_net_pnl",
            "unrealized_pnl",
            "total_pnl",
        ):
            numeric = _finite_signed_number(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, numeric)
            if self.lifecycle_state == "OPEN" and field_name in {"realized_gross_pnl", "realized_net_pnl"} and not _close(numeric, 0.0): raise ValueError(f"{field_name} must be zero for an OPEN position")
        if terminal and (not _close(self.unrealized_pnl, 0.0) or not _close(self.total_pnl, self.realized_net_pnl)): raise ValueError("terminal pnl")
        if not terminal and not _close(self.total_pnl, self.realized_net_pnl + self.unrealized_pnl): raise ValueError("total pnl")

        object.__setattr__(self, "blockers", _freeze_warnings(self.blockers))
        object.__setattr__(
            self,
            "decision_reasons",
            _freeze_warnings(self.decision_reasons),
        )
        object.__setattr__(self, "warnings", _freeze_warnings(self.warnings))
        if self.blockers:
            raise ValueError("OPEN position must not contain blockers")

        object.__setattr__(
            self,
            "metadata",
            _freeze_json_value(self.metadata),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible is not False:
            raise ValueError("live_execution_eligible must be False")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if field_name == "entry_fill":
                result[field_name] = self.entry_fill.to_dict()
            elif field_name == "exit_fills":
                result[field_name] = [fill.to_dict() for fill in self.exit_fills]
            elif field_name == "opened_at":
                result[field_name] = self.opened_at.isoformat()
            elif field_name in ("blockers", "decision_reasons", "warnings"):
                result[field_name] = list(value)
            elif field_name == "metadata":
                result[field_name] = _plain_json_value(self.metadata)
            else:
                result[field_name] = value
        return result

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("position_id")
        result.pop("opened_at")
        return result
