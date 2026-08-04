"""Typed Task 3B option-contract certification result."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import ClassVar

from services.contracts.option_contract_candidate_v1 import OptionContractCandidateV1
from services.contracts.option_contract_v1 import OptionContractV1

_STATUSES = {"CERTIFIED", "BLOCKED", "UNAVAILABLE"}
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
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or (value <= 0.0 if positive else value < 0.0)
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class SelectedOptionContractCertificationResultV1:
    """One exact certified contract or a typed fail-closed result."""

    SCHEMA_VERSION: ClassVar[str] = (
        "selected_option_contract_certification_result.v1"
    )

    certification_result_id: str
    parent_cycle_id: str
    parent_decision_id: str
    bridge_result_id: str
    selected_child_result_id: str | None
    candidate_id: str | None
    observation_id: str | None
    ranking_result_id: str | None
    universe_id: str | None
    evaluated_at: datetime
    status: str
    selected_market: tuple[str, str] | None
    direction: str | None
    option_right: str | None
    selected_rank: int | None
    selected_candidate: OptionContractCandidateV1 | None
    selected_contract: OptionContractV1 | None
    contract_id: str | None
    trading_symbol: str | None
    instrument_token: str | None
    expiry_date: date | None
    strike: float | None
    lot_size: int | None
    premium: float | None
    bid_price: float | None
    ask_price: float | None
    spread_value: float | None
    spread_fraction: float | None
    quote_timestamp: datetime | None
    contract_age_seconds: float | None
    quote_age_seconds: float | None
    liquidity_score: float | None
    open_interest: float | None
    volume: float | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "certification_result_id",
            "parent_cycle_id",
            "parent_decision_id",
            "bridge_result_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        for name in (
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

        if self.selected_rank is not None and (
            type(self.selected_rank) is not int
            or isinstance(self.selected_rank, bool)
            or self.selected_rank < 1
        ):
            raise ValueError("selected_rank")

        if self.expiry_date is not None and not isinstance(self.expiry_date, date):
            raise TypeError("expiry_date")
        if self.lot_size is not None and (
            type(self.lot_size) is not int
            or isinstance(self.lot_size, bool)
            or self.lot_size <= 0
        ):
            raise ValueError("lot_size")
        if self.quote_timestamp is not None:
            object.__setattr__(
                self,
                "quote_timestamp",
                _aware(self.quote_timestamp, "quote_timestamp"),
            )

        for name, positive, maximum in (
            ("strike", True, None),
            ("premium", True, None),
            ("bid_price", True, None),
            ("ask_price", True, None),
            ("spread_value", False, None),
            ("spread_fraction", False, 1.0),
            ("contract_age_seconds", False, None),
            ("quote_age_seconds", False, None),
            ("liquidity_score", False, 1.0),
            ("open_interest", False, None),
            ("volume", False, None),
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(self, name),
                    name,
                    positive=positive,
                    maximum=maximum,
                ),
            )

        for name in ("blockers", "warnings", "reasons"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        contract_group = (
            self.selected_rank,
            self.selected_candidate,
            self.selected_contract,
            self.contract_id,
            self.trading_symbol,
            self.instrument_token,
            self.expiry_date,
            self.strike,
            self.lot_size,
            self.premium,
            self.bid_price,
            self.ask_price,
            self.spread_value,
            self.spread_fraction,
            self.quote_timestamp,
            self.contract_age_seconds,
            self.quote_age_seconds,
            self.liquidity_score,
            self.open_interest,
            self.volume,
        )

        if status == "CERTIFIED":
            if self.blockers:
                raise ValueError("CERTIFIED cannot contain blockers")
            if any(value is None for value in contract_group):
                raise ValueError("CERTIFIED requires complete contract and quote")
            if type(self.selected_candidate) is not OptionContractCandidateV1:
                raise TypeError("selected_candidate")
            if type(self.selected_contract) is not OptionContractV1:
                raise TypeError("selected_contract")
            if self.selected_candidate.contract is not self.selected_contract:
                raise ValueError("selected candidate contract mismatch")
            contract = self.selected_contract
            if self.selected_market != (contract.underlying_symbol, contract.exchange):
                raise ValueError("selected market mismatch")
            if self.contract_id != contract.contract_id:
                raise ValueError("contract_id mismatch")
            if self.trading_symbol != contract.trading_symbol:
                raise ValueError("trading_symbol mismatch")
            if self.instrument_token != contract.instrument_token:
                raise ValueError("instrument_token mismatch")
            if self.expiry_date != contract.expiry_date:
                raise ValueError("expiry_date mismatch")
            if self.strike != contract.strike or self.lot_size != contract.lot_size:
                raise ValueError("strike or lot size mismatch")
            if self.premium != contract.last_price:
                raise ValueError("premium mismatch")
            if self.bid_price != contract.bid_price or self.ask_price != contract.ask_price:
                raise ValueError("quote mismatch")
            if self.quote_timestamp != contract.market_timestamp:
                raise ValueError("quote_timestamp mismatch")
            if self.liquidity_score != self.selected_candidate.liquidity_score:
                raise ValueError("liquidity_score mismatch")
            if self.open_interest != contract.open_interest or self.volume != contract.volume:
                raise ValueError("liquidity evidence mismatch")
            expected_right = "CALL" if self.direction == "BULLISH" else "PUT"
            if self.option_right != expected_right or contract.option_type != expected_right:
                raise ValueError("direction/right mismatch")
        else:
            if not self.blockers:
                raise ValueError("blocked result requires blockers")
            if any(value is not None for value in contract_group):
                raise ValueError("blocked result cannot expose certified contract")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only certification result")

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, datetime):
                values[name] = value.isoformat()
            elif isinstance(value, date):
                values[name] = value.isoformat()
            elif name == "selected_candidate":
                values[name] = None if value is None else value.to_dict()
            elif name == "selected_contract":
                values[name] = None if value is None else value.to_dict()
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
