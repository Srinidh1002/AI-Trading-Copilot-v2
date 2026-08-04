"""Immutable P3-5A position-sizing result contract; no formula is implemented."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping


_STATUSES = {"APPROVED", "INSUFFICIENT_CAPITAL", "INVALID_RISK", "LIMIT_EXCEEDED", "BLOCKED", "FAILED"}
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
_IDENTITIES = SUPPORTED_MARKET_IDENTITIES


def _positive(value: Any, name: str, *, required: bool = False) -> float | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite and positive.")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive.")
    return number


def _count(value: Any, name: str, *, required: bool = False) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or (required and value == 0):
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


@dataclass(frozen=True, slots=True)
class PositionSizeResultV1:
    sizing_result_id: str
    created_at: datetime
    snapshot_id: str
    analysis_id: str | None
    decision_id: str
    selection_id: str | None
    trade_plan_id: str | None
    contract_id: str | None
    underlying_symbol: str
    exchange: str
    action: str
    option_type: str | None
    trading_symbol: str | None
    expiry_date: date | None
    strike: float | None
    lot_size: int | None
    entry_price: float | None
    stop_loss_price: float | None
    target_price: float | None
    available_capital: float | None
    capital_limit: float | None
    risk_limit: float | None
    per_unit_risk: float | None
    per_lot_risk: float | None
    requested_lots: int | None
    approved_lots: int | None
    quantity: int | None
    capital_required: float | None
    maximum_loss: float | None
    reward_amount: float | None
    reward_risk_ratio: float | None
    sizing_status: str
    risk_approved: bool
    paper_preparation_eligible: bool
    execution_eligible: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "position_size_result.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != "position_size_result.v1" or self.sizing_status not in _STATUSES:
            raise ValueError("Unsupported position-size-result schema or status.")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware.")
        for name in ("sizing_result_id", "snapshot_id", "decision_id"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} is required.")
        for name in ("selection_id", "trade_plan_id", "contract_id", "trading_symbol"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be non-empty when supplied.")
        if self.analysis_id is not None and (not isinstance(self.analysis_id, str) or not self.analysis_id.strip()):
            raise ValueError("analysis_id must be non-empty when supplied.")
        if (self.underlying_symbol, self.exchange) not in _IDENTITIES:
            raise ValueError("Unsupported underlying/exchange identity.")
        if self.sizing_status == "APPROVED":
            if self.action not in {"BUY", "SELL"} or self.option_type not in {"CALL", "PUT"}:
                raise ValueError("Approved sizing requires a directional option identity.")
            if (self.action, self.option_type) not in {("BUY", "CALL"), ("SELL", "PUT")}:
                raise ValueError("Action and option type disagree.")
        else:
            if self.action not in {"BUY", "SELL", "WAIT"}:
                raise ValueError("Unsupported non-approved action.")
            if self.option_type is not None and self.option_type not in {"CALL", "PUT"}:
                raise ValueError("Unsupported option type.")
            if self.action == "WAIT" and self.option_type is not None:
                raise ValueError("WAIT cannot fabricate an option type.")
            if self.option_type is not None and (self.action, self.option_type) not in {("BUY", "CALL"), ("SELL", "PUT")}:
                raise ValueError("Action and option type disagree.")
        if self.expiry_date is not None and (not isinstance(self.expiry_date, date) or isinstance(self.expiry_date, datetime)):
            raise ValueError("expiry_date must be a date.")
        object.__setattr__(self, "strike", _positive(self.strike, "strike"))
        if self.lot_size is not None and (isinstance(self.lot_size, bool) or not isinstance(self.lot_size, int) or self.lot_size <= 0):
            raise ValueError("lot_size must be a positive integer.")
        for name in ("entry_price", "stop_loss_price", "target_price", "available_capital", "capital_limit", "risk_limit", "per_unit_risk", "per_lot_risk", "capital_required", "maximum_loss", "reward_amount", "reward_risk_ratio"):
            object.__setattr__(self, name, _positive(getattr(self, name), name))
        for name in ("requested_lots", "approved_lots", "quantity"):
            object.__setattr__(self, name, _count(getattr(self, name), name))
        for name in ("risk_approved", "paper_preparation_eligible", "execution_eligible"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean.")
        blockers = _texts(self.blockers, "blockers")
        warnings = _texts(self.warnings, "warnings")
        if self.execution_eligible:
            raise ValueError("P3-5A never permits execution eligibility.")
        if self.sizing_status == "APPROVED":
            if not self.risk_approved or not self.paper_preparation_eligible or blockers:
                raise ValueError("Approved sizing requires risk approval without blockers.")
            if any(getattr(self, name) is None for name in ("selection_id", "trade_plan_id", "contract_id", "trading_symbol", "expiry_date", "strike", "lot_size", "option_type")):
                raise ValueError("Approved sizing requires complete contract identity.")
            for name in ("entry_price", "stop_loss_price", "target_price", "available_capital", "capital_limit", "risk_limit", "per_unit_risk", "per_lot_risk", "requested_lots", "approved_lots", "quantity", "capital_required", "maximum_loss", "reward_amount", "reward_risk_ratio"):
                if getattr(self, name) is None:
                    raise ValueError("Approved sizing requires complete sizing data.")
            if self.approved_lots > self.requested_lots or self.quantity != self.approved_lots * self.lot_size:
                raise ValueError("Approved lot and quantity values are inconsistent.")
        elif self.risk_approved or self.paper_preparation_eligible or not blockers:
            raise ValueError("Non-approved sizing requires blockers and no eligibility.")
        try:
            json.dumps(self.metadata, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be safe JSON data.") from exc
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        value = {name: getattr(self, name) for name in self.__dataclass_fields__}
        value["created_at"] = self.created_at.isoformat()
        value["expiry_date"] = self.expiry_date.isoformat() if self.expiry_date is not None else None
        value["blockers"] = list(self.blockers)
        value["warnings"] = list(self.warnings)
        value["metadata"] = dict(sorted(self.metadata.items()))
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("sizing_result_id")
        value.pop("created_at")
        return value


def _texts(values: Any, name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of strings.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence of strings.") from exc
    if any(not isinstance(value, str) or not value.strip() for value in result):
        raise ValueError(f"{name} must contain non-empty strings.")
    return result
