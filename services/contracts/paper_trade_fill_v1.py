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
    _freeze_source_timestamps,
    _freeze_warnings,
    _nonblank_text,
    _plain_json_value,
)


FILL_TYPES = frozenset({"ENTRY", "EXIT"})
FILL_REASONS = frozenset(
    {
        "ENTRY_ACTIVATED",
        "TARGET_1",
        "TARGET_2",
        "TARGET_3",
        "STOP",
        "INVALIDATION",
        "SESSION_CLOSE",
        "EXPIRY_CLOSE",
        "CANCELLED",
        "RUNNER_CLOSE",
    }
)
FILL_SIDES = frozenset({"BUY", "SELL"})
TARGET_NAMES = {
    "TARGET_1": "T1",
    "TARGET_2": "T2",
    "TARGET_3": "T3",
}


def _positive_exact_int(value: object, field_name: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an exact int")
    if value <= 0:
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


@dataclass(frozen=True, slots=True)
class PaperTradeFillV1:
    fill_id: str
    trade_plan_id: str
    integrated_trade_plan_result_id: str
    position_id: str
    observation_id: str
    selected_option_contract_id: str
    fill_type: str
    fill_reason: str
    side: str
    filled_lot_count: int
    lot_size: int
    filled_quantity: int
    fill_price: float
    gross_notional: float
    estimated_trading_cost: float
    net_cash_effect: float
    filled_at: datetime
    source: str
    target_name: str | None = None
    warnings: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "fill_id",
            "trade_plan_id",
            "integrated_trade_plan_result_id",
            "position_id",
            "observation_id",
            "selected_option_contract_id",
            "source",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonblank_text(getattr(self, field_name), field_name),
            )

        if self.fill_type not in FILL_TYPES:
            raise ValueError("unsupported fill_type")
        if self.fill_reason not in FILL_REASONS:
            raise ValueError("unsupported fill_reason")
        if self.side not in FILL_SIDES:
            raise ValueError("unsupported side")

        object.__setattr__(
            self,
            "filled_lot_count",
            _positive_exact_int(self.filled_lot_count, "filled_lot_count"),
        )
        object.__setattr__(
            self,
            "lot_size",
            _positive_exact_int(self.lot_size, "lot_size"),
        )
        object.__setattr__(
            self,
            "filled_quantity",
            _positive_exact_int(self.filled_quantity, "filled_quantity"),
        )
        expected_quantity = self.filled_lot_count * self.lot_size
        if self.filled_quantity != expected_quantity:
            raise ValueError("filled_quantity must equal lots multiplied by lot_size")

        object.__setattr__(
            self,
            "fill_price",
            _finite_number(
                self.fill_price,
                "fill_price",
                required=True,
                minimum=0.0,
                strictly_greater=True,
            ),
        )
        object.__setattr__(
            self,
            "gross_notional",
            _finite_number(
                self.gross_notional,
                "gross_notional",
                required=True,
                minimum=0.0,
                strictly_greater=True,
            ),
        )
        object.__setattr__(
            self,
            "estimated_trading_cost",
            _finite_number(
                self.estimated_trading_cost,
                "estimated_trading_cost",
                required=True,
                minimum=0.0,
            ),
        )
        object.__setattr__(
            self,
            "net_cash_effect",
            _finite_signed_number(self.net_cash_effect, "net_cash_effect"),
        )

        expected_notional = self.filled_quantity * self.fill_price
        if not _close(self.gross_notional, expected_notional):
            raise ValueError("gross_notional is incoherent")

        if self.fill_type == "ENTRY":
            if self.side != "BUY":
                raise ValueError("ENTRY fill must use BUY")
            if self.fill_reason != "ENTRY_ACTIVATED":
                raise ValueError("ENTRY fill must use ENTRY_ACTIVATED")
            if self.target_name is not None:
                raise ValueError("ENTRY fill must not have target_name")
        else:
            if self.side != "SELL":
                raise ValueError("EXIT fill must use SELL")
            if self.fill_reason == "ENTRY_ACTIVATED":
                raise ValueError("EXIT fill cannot use ENTRY_ACTIVATED")

        expected_target = TARGET_NAMES.get(self.fill_reason)
        if expected_target is None:
            if self.target_name is not None:
                raise ValueError("non-target fill must not have target_name")
        elif self.target_name != expected_target:
            raise ValueError(
                f"{self.fill_reason} requires target_name={expected_target}"
            )

        expected_cash = (
            -(self.gross_notional + self.estimated_trading_cost)
            if self.side == "BUY"
            else self.gross_notional - self.estimated_trading_cost
        )
        if not _close(self.net_cash_effect, expected_cash):
            raise ValueError("net_cash_effect is incoherent")

        object.__setattr__(
            self,
            "filled_at",
            _aware_datetime(self.filled_at, "filled_at"),
        )
        object.__setattr__(self, "warnings", _freeze_warnings(self.warnings))
        object.__setattr__(
            self,
            "source_timestamps",
            _freeze_source_timestamps(self.source_timestamps),
        )
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
            if field_name == "filled_at":
                result[field_name] = self.filled_at.isoformat()
            elif field_name == "source_timestamps":
                result[field_name] = {
                    key: timestamp.isoformat()
                    for key, timestamp in self.source_timestamps.items()
                }
            elif field_name == "warnings":
                result[field_name] = list(self.warnings)
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
        for field_name in ("fill_id", "filled_at", "source_timestamps"):
            result.pop(field_name)
        return result
