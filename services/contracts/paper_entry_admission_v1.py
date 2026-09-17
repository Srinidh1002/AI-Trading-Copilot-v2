"""Immutable PAPER fee, reservation, and duplicate-entry contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned

def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value

def _number(value: object, name: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not isfinite(value):
        raise ValueError(name)
    number = float(value)
    if (positive and number <= 0.0) or (not positive and number < 0.0):
        raise ValueError(name)
    return number

def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))

@dataclass(frozen=True, slots=True)
class PaperFeePolicyV1:
    policy_id: str
    brokerage_per_order: float
    exchange_transaction_fraction: float
    sebi_fraction: float
    stamp_duty_fraction: float
    stt_fraction: float
    gst_fraction_on_charges: float
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        for name in (
            "brokerage_per_order",
            "exchange_transaction_fraction",
            "sebi_fraction",
            "stamp_duty_fraction",
            "stt_fraction",
            "gst_fraction_on_charges",
        ):
            value = _number(getattr(self, name), name)
            if "fraction" in name and value > 1.0:
                raise ValueError(name)
            object.__setattr__(self, name, value)
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only fee policy")

@dataclass(frozen=True, slots=True)
class PaperFeeBreakdownV1:
    policy_id: str
    gross_premium_outlay: float
    brokerage: float
    exchange_transaction_charges: float
    sebi_charges: float
    stamp_duty: float
    stt: float
    gst: float
    total_fees: float
    total_capital_required: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", _text(self.policy_id, "policy_id"))
        for name in (
            "gross_premium_outlay",
            "brokerage",
            "exchange_transaction_charges",
            "sebi_charges",
            "stamp_duty",
            "stt",
            "gst",
            "total_fees",
            "total_capital_required",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        expected_fees = (
            self.brokerage
            + self.exchange_transaction_charges
            + self.sebi_charges
            + self.stamp_duty
            + self.stt
            + self.gst
        )
        if abs(self.total_fees - expected_fees) > 1e-9:
            raise ValueError("total_fees")
        if abs(self.total_capital_required - (self.gross_premium_outlay + self.total_fees)) > 1e-9:
            raise ValueError("total_capital_required")

@dataclass(frozen=True, slots=True)
class ExistingPaperReservationV1:
    reservation_id: str
    recommendation_id: str
    contract: str
    reserved_capital: float
    active: bool = True

    def __post_init__(self) -> None:
        for name in ("reservation_id", "recommendation_id", "contract"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "reserved_capital", _number(self.reserved_capital, "reserved_capital", positive=True))
        if type(self.active) is not bool:
            raise TypeError("active")

@dataclass(frozen=True, slots=True)
class PaperCapitalReservationInputV1:
    reservation_request_id: str
    recommendation_id: str
    contract: str
    evaluated_at: datetime
    available_capital: float
    fill_gross_premium_outlay: float
    maximum_loss: float
    fee_policy: PaperFeePolicyV1
    existing_reservations: tuple[ExistingPaperReservationV1, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("reservation_request_id", "recommendation_id", "contract"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        for name in ("available_capital", "fill_gross_premium_outlay", "maximum_loss"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=True))
        if type(self.fee_policy) is not PaperFeePolicyV1:
            raise TypeError("fee_policy")
        if not isinstance(self.existing_reservations, tuple):
            raise TypeError("existing_reservations")
        if not all(type(item) is ExistingPaperReservationV1 for item in self.existing_reservations):
            raise TypeError("existing_reservations")
        ids = [item.reservation_id for item in self.existing_reservations]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate reservation_id")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.broker_order_submission is not False:
            raise ValueError("PAPER-only reservation input")

@dataclass(frozen=True, slots=True)
class PaperCapitalReservationResultV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_capital_reservation_result.v1"
    reservation_result_id: str
    reservation_request_id: str
    recommendation_id: str
    contract: str
    evaluated_at: datetime
    status: str
    fee_breakdown: PaperFeeBreakdownV1
    existing_reserved_capital: float
    newly_reserved_capital: float
    total_reserved_capital: float
    remaining_capital: float
    maximum_loss: float
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("reservation_result_id", "reservation_request_id", "recommendation_id", "contract"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        if self.status not in {"RESERVED", "REJECTED"}:
            raise ValueError("status")
        if type(self.fee_breakdown) is not PaperFeeBreakdownV1:
            raise TypeError("fee_breakdown")
        for name in (
            "existing_reserved_capital",
            "newly_reserved_capital",
            "total_reserved_capital",
            "remaining_capital",
            "maximum_loss",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        if self.status == "RESERVED":
            if self.blockers or self.newly_reserved_capital <= 0.0:
                raise ValueError("RESERVED coherence")
        else:
            if not self.blockers or self.newly_reserved_capital != 0.0:
                raise ValueError("REJECTED coherence")
        if abs(self.total_reserved_capital - (self.existing_reserved_capital + self.newly_reserved_capital)) > 1e-9:
            raise ValueError("total_reserved_capital")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.broker_order_submission is not False:
            raise ValueError("PAPER-only reservation result")
