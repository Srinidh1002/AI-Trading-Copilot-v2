"""Typed contracts for Task 7A deterministic replay certification."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar


_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_SCENARIOS = {
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "GAP",
    "REVERSAL",
    "FALSE_BREAKOUT",
    "STALE_DATA",
    "MISSING_OPTION_CHAIN",
    "ONE_MARKET_UNAVAILABLE",
    "BOTH_BLOCKED",
    "DUPLICATE_ENTRY",
    "PARTIAL_EXITS",
    "ALL_TARGETS",
    "STOP_HIT",
    "EARLY_SAFETY_EXIT",
    "RESTART_RECOVERY",
}
_EXPECTED_OUTCOMES = {
    "CLOSED_TRADE",
    "NO_TRADE",
    "BLOCKED",
    "FAILED",
}
_RESULT_STATUSES = {
    "CLOSED_TRADE",
    "NO_TRADE",
    "BLOCKED",
    "FAILED",
}
_CLOSURE_REASONS = {
    "TARGET_3",
    "STOP",
    "EARLY_SAFETY_EXIT",
    "MANUAL_CERTIFIED_CLOSE",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str or not (cleaned := value.strip()):
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


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _nonnegative_number(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class ReplayScenarioV1:
    """One deterministic NIFTY or SENSEX replay case."""

    SCHEMA_VERSION: ClassVar[str] = "replay_scenario.v1"

    scenario_id: str
    sequence: int
    market: tuple[str, str]
    scenario_type: str
    expected_outcome: str
    fixture_id: str
    replay_started_at: datetime
    tags: tuple[str, ...] = ()
    expected_actions: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    network_access_allowed: bool = False
    broker_submission_enabled: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        for name in ("scenario_id", "fixture_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        if (
            type(self.sequence) is not int
            or isinstance(self.sequence, bool)
            or self.sequence <= 0
        ):
            raise ValueError("sequence")

        if not isinstance(self.market, tuple) or len(self.market) != 2:
            raise TypeError("market")
        market = tuple(_text(item, "market").upper() for item in self.market)
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(self, "market", market)

        scenario_type = _text(
            self.scenario_type,
            "scenario_type",
        ).upper()
        if scenario_type not in _SCENARIOS:
            raise ValueError("scenario_type")
        object.__setattr__(self, "scenario_type", scenario_type)

        outcome = _text(
            self.expected_outcome,
            "expected_outcome",
        ).upper()
        if outcome not in _EXPECTED_OUTCOMES:
            raise ValueError("expected_outcome")
        object.__setattr__(self, "expected_outcome", outcome)

        object.__setattr__(
            self,
            "replay_started_at",
            _aware(self.replay_started_at, "replay_started_at"),
        )
        for name in ("tags", "expected_actions"):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if (
            self.execution_mode != "PAPER"
            or self.network_access_allowed is not False
            or self.broker_submission_enabled is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("offline PAPER-only replay scenario")


@dataclass(frozen=True, slots=True)
class ReplayTradeResultV1:
    """Terminal result for one replay scenario."""

    SCHEMA_VERSION: ClassVar[str] = "replay_trade_result.v1"

    result_id: str
    scenario_id: str
    sequence: int
    market: tuple[str, str]
    scenario_type: str
    status: str
    opened: bool
    closed: bool
    opened_at: datetime | None
    closed_at: datetime | None
    closure_reason: str | None
    realized_pnl: float
    action_history: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    network_access_used: bool = False
    broker_submission_enabled: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        for name in ("result_id", "scenario_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        if (
            type(self.sequence) is not int
            or isinstance(self.sequence, bool)
            or self.sequence <= 0
        ):
            raise ValueError("sequence")

        if not isinstance(self.market, tuple) or len(self.market) != 2:
            raise TypeError("market")
        market = tuple(_text(item, "market").upper() for item in self.market)
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(self, "market", market)

        scenario_type = _text(
            self.scenario_type,
            "scenario_type",
        ).upper()
        if scenario_type not in _SCENARIOS:
            raise ValueError("scenario_type")
        object.__setattr__(self, "scenario_type", scenario_type)

        status = _text(self.status, "status").upper()
        if status not in _RESULT_STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        if type(self.opened) is not bool or type(self.closed) is not bool:
            raise TypeError("opened/closed")

        opened_at = (
            None
            if self.opened_at is None
            else _aware(self.opened_at, "opened_at")
        )
        closed_at = (
            None
            if self.closed_at is None
            else _aware(self.closed_at, "closed_at")
        )
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "closed_at", closed_at)

        closure_reason = self.closure_reason
        if closure_reason is not None:
            closure_reason = _text(
                closure_reason,
                "closure_reason",
            ).upper()
            if closure_reason not in _CLOSURE_REASONS:
                raise ValueError("closure_reason")
            object.__setattr__(
                self,
                "closure_reason",
                closure_reason,
            )

        object.__setattr__(
            self,
            "realized_pnl",
            float(self.realized_pnl),
        )
        if not isfinite(self.realized_pnl):
            raise ValueError("realized_pnl")

        for name in (
            "action_history",
            "blockers",
            "warnings",
            "errors",
        ):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if status == "CLOSED_TRADE":
            if not self.opened or not self.closed:
                raise ValueError("closed trade must open and close")
            if opened_at is None or closed_at is None:
                raise ValueError("closed trade requires timestamps")
            if closed_at < opened_at:
                raise ValueError("closed_at")
            if self.closure_reason is None:
                raise ValueError("closure_reason")
            if not self.action_history:
                raise ValueError("action_history")
            if self.blockers or self.errors:
                raise ValueError("closed trade cannot contain blockers/errors")
        else:
            if self.opened or self.closed:
                raise ValueError("non-trade result cannot open or close")
            if opened_at is not None or closed_at is not None:
                raise ValueError("non-trade result cannot contain timestamps")
            if self.closure_reason is not None:
                raise ValueError("non-trade result cannot contain closure")
            if self.realized_pnl != 0.0:
                raise ValueError("non-trade result must have zero pnl")

        if status == "BLOCKED" and not self.blockers:
            raise ValueError("blocked result requires blockers")
        if status == "FAILED" and not self.errors:
            raise ValueError("failed result requires errors")

        if (
            self.execution_mode != "PAPER"
            or self.network_access_used is not False
            or self.broker_submission_enabled is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("offline PAPER-only replay result")


@dataclass(frozen=True, slots=True)
class ReplayCertificationLedgerV1:
    """Immutable ledger for all Task 7A replay outcomes."""

    SCHEMA_VERSION: ClassVar[str] = "replay_certification_ledger.v1"

    ledger_id: str
    generated_at: datetime
    results: tuple[ReplayTradeResultV1, ...]
    required_closed_trades_per_market: int = 60
    execution_mode: str = "PAPER"
    network_access_used: bool = False
    broker_submission_enabled: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ledger_id",
            _text(self.ledger_id, "ledger_id"),
        )
        object.__setattr__(
            self,
            "generated_at",
            _aware(self.generated_at, "generated_at"),
        )

        if not isinstance(self.results, tuple):
            raise TypeError("results")
        if any(type(item) is not ReplayTradeResultV1 for item in self.results):
            raise TypeError("results")

        if (
            type(self.required_closed_trades_per_market) is not int
            or isinstance(self.required_closed_trades_per_market, bool)
            or self.required_closed_trades_per_market <= 0
        ):
            raise ValueError("required_closed_trades_per_market")

        ids = tuple(item.result_id for item in self.results)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate result_id")
        scenario_ids = tuple(item.scenario_id for item in self.results)
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("duplicate scenario_id")

        sequences_by_market: dict[tuple[str, str], list[int]] = {
            market: [] for market in _MARKETS
        }
        for item in self.results:
            sequences_by_market[item.market].append(item.sequence)
        for sequences in sequences_by_market.values():
            if len(sequences) != len(set(sequences)):
                raise ValueError("duplicate market sequence")

        if (
            self.execution_mode != "PAPER"
            or self.network_access_used is not False
            or self.broker_submission_enabled is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("offline PAPER-only replay ledger")

    @property
    def nifty_closed_trade_count(self) -> int:
        return sum(
            item.status == "CLOSED_TRADE"
            and item.market == ("NIFTY", "NSE")
            for item in self.results
        )

    @property
    def sensex_closed_trade_count(self) -> int:
        return sum(
            item.status == "CLOSED_TRADE"
            and item.market == ("SENSEX", "BSE")
            for item in self.results
        )

    @property
    def no_trade_count(self) -> int:
        return sum(item.status == "NO_TRADE" for item in self.results)

    @property
    def blocked_count(self) -> int:
        return sum(item.status == "BLOCKED" for item in self.results)

    @property
    def failed_count(self) -> int:
        return sum(item.status == "FAILED" for item in self.results)

    @property
    def is_complete(self) -> bool:
        return (
            self.nifty_closed_trade_count
            >= self.required_closed_trades_per_market
            and self.sensex_closed_trade_count
            >= self.required_closed_trades_per_market
            and self.failed_count == 0
        )
