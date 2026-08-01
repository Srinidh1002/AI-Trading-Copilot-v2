"""Read-only operator application snapshot contract for Task 6."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar


_ACTIONS = {"CALL", "PUT", "WAIT", "NO_TRADE", "HOLD", "EXIT"}
_HEALTH = {"HEALTHY", "DEGRADED", "BLOCKED"}
_MODES = {"PAPER", "LIVE"}


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
    allow_negative: bool = False,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise ValueError(name)
    result = float(value)
    if positive and result <= 0.0:
        raise ValueError(name)
    if not positive and not allow_negative and result < 0.0:
        raise ValueError(name)
    return result


def _optional_number(
    value: object,
    name: str,
    *,
    positive: bool = False,
    allow_negative: bool = False,
) -> float | None:
    if value is None:
        return None
    return _number(
        value,
        name,
        positive=positive,
        allow_negative=allow_negative,
    )


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class OperatorMarketStateV1:
    market: str
    exchange: str
    score: float
    confidence: float
    eligible: bool
    direction: str
    data_fresh: bool
    reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        market = _text(self.market, "market").upper()
        exchange = _text(self.exchange, "exchange").upper()
        if (market, exchange) not in {
            ("NIFTY", "NSE"),
            ("SENSEX", "BSE"),
        }:
            raise ValueError("market identity")
        object.__setattr__(self, "market", market)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(
            self,
            "score",
            _number(
                self.score,
                "score",
                allow_negative=True,
            ),
        )
        confidence = _number(self.confidence, "confidence")
        if confidence > 1.0:
            raise ValueError("confidence")
        object.__setattr__(self, "confidence", confidence)
        for name in ("eligible", "data_fresh"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)
        direction = _text(self.direction, "direction").upper()
        if direction not in {"BULLISH", "BEARISH", "NEUTRAL"}:
            raise ValueError("direction")
        object.__setattr__(self, "direction", direction)
        object.__setattr__(
            self,
            "reasons",
            _messages(self.reasons, "reasons"),
        )
        object.__setattr__(
            self,
            "rejection_reasons",
            _messages(
                self.rejection_reasons,
                "rejection_reasons",
            ),
        )


@dataclass(frozen=True, slots=True)
class OperatorRecommendationStateV1:
    action: str
    selected_market: str | None
    contract: str | None
    entry_price: float | None
    stop_loss: float | None
    target_1: float | None
    target_2: float | None
    target_3: float | None
    confidence: float
    explanation: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        action = _text(self.action, "action").upper()
        if action not in _ACTIONS:
            raise ValueError("action")
        object.__setattr__(self, "action", action)

        if self.selected_market is not None:
            market = _text(
                self.selected_market,
                "selected_market",
            ).upper()
            if market not in {"NIFTY", "SENSEX"}:
                raise ValueError("selected_market")
            object.__setattr__(
                self,
                "selected_market",
                market,
            )

        if self.contract is not None:
            object.__setattr__(
                self,
                "contract",
                _text(self.contract, "contract"),
            )

        for name in (
            "entry_price",
            "stop_loss",
            "target_1",
            "target_2",
            "target_3",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(self, name),
                    name,
                    positive=True,
                ),
            )

        confidence = _number(self.confidence, "confidence")
        if confidence > 1.0:
            raise ValueError("confidence")
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(
            self,
            "explanation",
            _messages(self.explanation, "explanation"),
        )

        executable = action in {"CALL", "PUT"}
        geometry = (
            self.selected_market,
            self.contract,
            self.entry_price,
            self.stop_loss,
            self.target_1,
            self.target_2,
            self.target_3,
        )
        if executable and any(value is None for value in geometry):
            raise ValueError("executable recommendation geometry")
        if not executable and any(value is not None for value in geometry):
            raise ValueError("non-executable recommendation geometry")
        if executable and not (
            self.stop_loss
            < self.entry_price
            < self.target_1
            < self.target_2
            < self.target_3
        ):
            raise ValueError("recommendation geometry")


@dataclass(frozen=True, slots=True)
class OperatorCapitalStateV1:
    supplied_capital: float
    usable_capital: float
    lots: int
    quantity: int
    capital_required: float
    maximum_loss: float
    daily_risk_used: float

    def __post_init__(self) -> None:
        for name in (
            "supplied_capital",
            "usable_capital",
            "capital_required",
            "maximum_loss",
            "daily_risk_used",
        ):
            object.__setattr__(
                self,
                name,
                _number(getattr(self, name), name),
            )
        for name in ("lots", "quantity"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(name)
        if self.usable_capital > self.supplied_capital:
            raise ValueError("usable_capital")
        if self.capital_required > self.usable_capital:
            raise ValueError("capital_required")
        if self.maximum_loss > self.supplied_capital:
            raise ValueError("maximum_loss")


@dataclass(frozen=True, slots=True)
class OperatorActiveTradeStateV1:
    active: bool
    contract: str | None
    current_premium: float | None
    unrealized_pnl: float
    target_status: str
    stop_status: str
    instruction: str
    confidence_deteriorating: bool

    def __post_init__(self) -> None:
        if type(self.active) is not bool:
            raise TypeError("active")
        if type(self.confidence_deteriorating) is not bool:
            raise TypeError("confidence_deteriorating")

        if self.contract is not None:
            object.__setattr__(
                self,
                "contract",
                _text(self.contract, "contract"),
            )
        object.__setattr__(
            self,
            "current_premium",
            _optional_number(
                self.current_premium,
                "current_premium",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "unrealized_pnl",
            _number(
                self.unrealized_pnl,
                "unrealized_pnl",
                allow_negative=True,
            ),
        )
        for name in ("target_status", "stop_status"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        instruction = _text(
            self.instruction,
            "instruction",
        ).upper()
        if instruction not in {
            "NONE",
            "HOLD",
            "HOLD_WITH_CAUTION",
            "EXIT",
        }:
            raise ValueError("instruction")
        object.__setattr__(self, "instruction", instruction)

        if self.active:
            if self.contract is None or self.current_premium is None:
                raise ValueError("active trade fields")
        else:
            if (
                self.contract is not None
                or self.current_premium is not None
                or self.unrealized_pnl != 0.0
                or instruction != "NONE"
            ):
                raise ValueError("inactive trade fields")


@dataclass(frozen=True, slots=True)
class OperatorSystemHealthV1:
    status: str
    data_fresh: bool
    data_connection: str
    broker_connection: str
    mode: str
    broker_submission_enabled: bool
    emergency_halt: bool
    runtime_healthy: bool
    journal_healthy: bool
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        status = _text(self.status, "status").upper()
        if status not in _HEALTH:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        mode = _text(self.mode, "mode").upper()
        if mode not in _MODES:
            raise ValueError("mode")
        object.__setattr__(self, "mode", mode)

        for name in (
            "data_connection",
            "broker_connection",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        for name in (
            "data_fresh",
            "broker_submission_enabled",
            "emergency_halt",
            "runtime_healthy",
            "journal_healthy",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if mode == "PAPER" and self.broker_submission_enabled:
            raise ValueError("PAPER broker submission must be disabled")

        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )


@dataclass(frozen=True, slots=True)
class OperatorApplicationSnapshotV1:
    SCHEMA_VERSION: ClassVar[str] = "operator_application_snapshot.v1"

    snapshot_id: str
    generated_at: datetime
    nifty: OperatorMarketStateV1
    sensex: OperatorMarketStateV1
    selected_market: str | None
    losing_market: str | None
    losing_market_reasons: tuple[str, ...]
    recommendation: OperatorRecommendationStateV1
    capital: OperatorCapitalStateV1
    active_trade: OperatorActiveTradeStateV1
    system_health: OperatorSystemHealthV1
    read_only: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "snapshot_id",
            _text(self.snapshot_id, "snapshot_id"),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )

        expected_types = {
            "nifty": OperatorMarketStateV1,
            "sensex": OperatorMarketStateV1,
            "recommendation": OperatorRecommendationStateV1,
            "capital": OperatorCapitalStateV1,
            "active_trade": OperatorActiveTradeStateV1,
            "system_health": OperatorSystemHealthV1,
        }
        for name, expected in expected_types.items():
            if type(getattr(self, name)) is not expected:
                raise TypeError(name)

        if self.nifty.market != "NIFTY":
            raise ValueError("nifty market")
        if self.sensex.market != "SENSEX":
            raise ValueError("sensex market")

        for name in ("selected_market", "losing_market"):
            value = getattr(self, name)
            if value is not None:
                market = _text(value, name).upper()
                if market not in {"NIFTY", "SENSEX"}:
                    raise ValueError(name)
                object.__setattr__(self, name, market)

        if (
            self.selected_market is not None
            and self.losing_market is not None
            and self.selected_market == self.losing_market
        ):
            raise ValueError("selected and losing market match")

        object.__setattr__(
            self,
            "losing_market_reasons",
            _messages(
                self.losing_market_reasons,
                "losing_market_reasons",
            ),
        )

        if self.recommendation.selected_market != self.selected_market:
            raise ValueError("recommendation selected market mismatch")

        if type(self.read_only) is not bool or self.read_only is not True:
            raise ValueError("operator snapshot must be read-only")
        if self.system_health.broker_submission_enabled:
            raise ValueError("operator snapshot cannot enable broker submission")
