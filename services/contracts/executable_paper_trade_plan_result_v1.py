"""Typed Task 5 executable PAPER trade-plan result."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import ClassVar

from services.contracts.entry_zone_evaluation_result_v1 import (
    EntryZoneEvaluationResultV1,
)
from services.contracts.stop_loss_evaluation_result_v1 import (
    StopLossEvaluationResultV1,
)
from services.contracts.three_target_evaluation_result_v1 import (
    ThreeTargetEvaluationResultV1,
)


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


def _optional_int(
    value: object,
    name: str,
    *,
    positive: bool = False,
) -> int | None:
    if value is None:
        return None
    if (
        type(value) is not int
        or isinstance(value, bool)
        or (value <= 0 if positive else value < 0)
    ):
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class ExecutablePaperTradePlanResultV1:
    """Final Task 5 executable PAPER intent; never submits an order."""

    SCHEMA_VERSION: ClassVar[str] = "executable_paper_trade_plan_result.v1"

    executable_plan_id: str
    task4_planning_result_id: str
    affordability_result_id: str
    certification_result_id: str
    parent_cycle_id: str
    parent_decision_id: str
    bridge_result_id: str
    candidate_id: str | None
    observation_id: str | None
    ranking_result_id: str | None
    contract_id: str | None
    selected_market: tuple[str, str] | None
    direction: str | None
    option_right: str | None
    trading_symbol: str | None
    instrument_token: str | None
    expiry_date: date | None
    strike: float | None
    evaluated_at: datetime
    status: str
    executable: bool
    entry_result: EntryZoneEvaluationResultV1 | None
    stop_loss_result: StopLossEvaluationResultV1 | None
    target_result: ThreeTargetEvaluationResultV1 | None
    lot_size: int | None = None
    planned_lot_count: int | None = None
    planned_quantity: int | None = None
    risk_per_unit: float | None = None
    risk_per_lot: float | None = None
    maximum_authorized_loss: float | None = None
    estimated_entry_premium: float | None = None
    estimated_premium_outlay: float | None = None
    estimated_costs_per_lot: float | None = None
    estimated_total_costs: float | None = None
    estimated_total_capital_requirement: float | None = None
    estimated_maximum_loss: float | None = None
    maximum_affordable_lots: int | None = None
    risk_based_lot_limit: int | None = None
    policy_lot_limit: int | None = None
    target_1_lot_count: int | None = None
    target_2_lot_count: int | None = None
    target_3_lot_count: int | None = None
    runner_lot_count: int | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "executable_plan_id",
            "task4_planning_result_id",
            "affordability_result_id",
            "certification_result_id",
            "parent_cycle_id",
            "parent_decision_id",
            "bridge_result_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        for name in (
            "candidate_id",
            "observation_id",
            "ranking_result_id",
            "contract_id",
            "trading_symbol",
            "instrument_token",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(getattr(self, name), name),
            )

        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))

        status = _text(self.status, "status").upper()
        if status not in _STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        if type(self.executable) is not bool:
            raise TypeError("executable")

        if self.selected_market is not None:
            if not isinstance(self.selected_market, tuple) or len(self.selected_market) != 2:
                raise TypeError("selected_market")
            market = tuple(_text(item, "selected_market").upper() for item in self.selected_market)
            if market not in _MARKETS:
                raise ValueError("selected_market")
            object.__setattr__(self, "selected_market", market)

        if self.direction is not None:
            direction = _text(self.direction, "direction").upper()
            if direction not in _DIRECTIONS:
                raise ValueError("direction")
            object.__setattr__(self, "direction", direction)

        if self.option_right is not None:
            right = _text(self.option_right, "option_right").upper()
            if right not in _RIGHTS:
                raise ValueError("option_right")
            object.__setattr__(self, "option_right", right)

        if self.expiry_date is not None and not isinstance(self.expiry_date, date):
            raise TypeError("expiry_date")

        for name, expected in (
            ("entry_result", EntryZoneEvaluationResultV1),
            ("stop_loss_result", StopLossEvaluationResultV1),
            ("target_result", ThreeTargetEvaluationResultV1),
        ):
            value = getattr(self, name)
            if value is not None and type(value) is not expected:
                raise TypeError(name)

        for name in (
            "lot_size",
            "planned_lot_count",
            "planned_quantity",
            "maximum_affordable_lots",
            "risk_based_lot_limit",
            "policy_lot_limit",
            "target_1_lot_count",
            "target_2_lot_count",
            "target_3_lot_count",
            "runner_lot_count",
        ):
            object.__setattr__(
                self,
                name,
                _optional_int(
                    getattr(self, name),
                    name,
                    positive=name in {"lot_size", "planned_lot_count", "planned_quantity"},
                ),
            )

        for name, positive in (
            ("strike", True),
            ("risk_per_unit", True),
            ("risk_per_lot", True),
            ("maximum_authorized_loss", True),
            ("estimated_entry_premium", True),
            ("estimated_premium_outlay", True),
            ("estimated_costs_per_lot", False),
            ("estimated_total_costs", False),
            ("estimated_total_capital_requirement", True),
            ("estimated_maximum_loss", True),
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(getattr(self, name), name, positive=positive),
            )

        for name in ("blockers", "warnings"):
            object.__setattr__(self, name, _messages(getattr(self, name), name))

        identity_group = (
            self.contract_id,
            self.selected_market,
            self.direction,
            self.option_right,
            self.trading_symbol,
            self.instrument_token,
            self.expiry_date,
            self.strike,
        )
        plan_group = (
            self.entry_result,
            self.stop_loss_result,
            self.target_result,
            self.lot_size,
            self.planned_lot_count,
            self.planned_quantity,
            self.risk_per_unit,
            self.risk_per_lot,
            self.maximum_authorized_loss,
            self.estimated_entry_premium,
            self.estimated_premium_outlay,
            self.estimated_costs_per_lot,
            self.estimated_total_costs,
            self.estimated_total_capital_requirement,
            self.estimated_maximum_loss,
            self.maximum_affordable_lots,
            self.risk_based_lot_limit,
            self.policy_lot_limit,
            self.target_1_lot_count,
            self.target_2_lot_count,
            self.target_3_lot_count,
            self.runner_lot_count,
        )

        if status == "READY":
            if (
                not self.executable
                or self.blockers
                or any(value is None for value in identity_group)
                or any(value is None for value in plan_group)
                or self.entry_result.status != "READY"
                or self.stop_loss_result.status != "READY"
                or self.target_result.status != "READY"
                or self.planned_quantity != self.planned_lot_count * self.lot_size
                or self.estimated_premium_outlay
                != self.estimated_entry_premium * self.planned_quantity
                or self.estimated_total_costs
                != self.estimated_costs_per_lot * self.planned_lot_count
                or self.estimated_total_capital_requirement
                != self.estimated_premium_outlay + self.estimated_total_costs
                or self.estimated_maximum_loss
                != self.risk_per_lot * self.planned_lot_count
                or self.planned_lot_count
                > min(
                    self.maximum_affordable_lots,
                    self.risk_based_lot_limit,
                    self.policy_lot_limit,
                )
                or sum(
                    (
                        self.target_1_lot_count,
                        self.target_2_lot_count,
                        self.target_3_lot_count,
                        self.runner_lot_count,
                    )
                )
                != self.planned_lot_count
            ):
                raise ValueError("READY coherence")
        elif status == "BLOCKED":
            if self.executable or not self.blockers:
                raise ValueError("BLOCKED coherence")
        else:
            if (
                self.executable
                or not self.blockers
                or any(value is not None for value in identity_group)
                or any(value is not None for value in plan_group)
            ):
                raise ValueError("UNAVAILABLE coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only executable plan")

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
            elif name in {"entry_result", "stop_loss_result", "target_result"}:
                values[name] = None if value is None else value.to_dict()
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
