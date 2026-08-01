"""Selected-market authorization result before capital and P6 planning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)


_ACTIONS = {"CALL", "PUT", "WAIT", "NO_TRADE"}
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


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class SelectedMarketPlanningBridgeResultV1:
    """One selected market or an explicit non-planning terminal action."""

    SCHEMA_VERSION: ClassVar[str] = (
        "selected_market_planning_bridge_result.v1"
    )

    bridge_result_id: str
    parent_cycle_id: str
    evaluated_at: datetime
    action: str
    planning_allowed: bool
    selected_market: tuple[str, str] | None
    selected_candidate: MarketAnalysisCandidateV1 | None
    losing_market: tuple[str, str] | None
    losing_outcome_reason: str | None
    losing_rationale: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("bridge_result_id", "parent_cycle_id"):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        action = _text(self.action, "action").upper()
        if action not in _ACTIONS:
            raise ValueError("action")
        object.__setattr__(self, "action", action)

        if type(self.planning_allowed) is not bool:
            raise TypeError("planning_allowed")

        if self.selected_market is not None:
            if (
                not isinstance(self.selected_market, tuple)
                or len(self.selected_market) != 2
            ):
                raise TypeError("selected_market")
            normalized = tuple(
                _text(item, "selected_market").upper()
                for item in self.selected_market
            )
            if normalized not in _MARKETS:
                raise ValueError("selected_market")
            object.__setattr__(self, "selected_market", normalized)

        if self.losing_market is not None:
            if (
                not isinstance(self.losing_market, tuple)
                or len(self.losing_market) != 2
            ):
                raise TypeError("losing_market")
            normalized_loser = tuple(
                _text(item, "losing_market").upper()
                for item in self.losing_market
            )
            if normalized_loser not in _MARKETS:
                raise ValueError("losing_market")
            object.__setattr__(self, "losing_market", normalized_loser)

        if self.losing_outcome_reason is not None:
            object.__setattr__(
                self,
                "losing_outcome_reason",
                _text(
                    self.losing_outcome_reason,
                    "losing_outcome_reason",
                ).upper(),
            )

        for name in (
            "losing_rationale",
            "reasons",
            "invalidation_conditions",
            "blockers",
            "warnings",
        ):
            object.__setattr__(
                self,
                name,
                _messages(getattr(self, name), name),
            )

        if action in {"CALL", "PUT"}:
            if not self.planning_allowed:
                raise ValueError(
                    "CALL/PUT requires planning_allowed"
                )
            if type(self.selected_candidate) is not MarketAnalysisCandidateV1:
                raise TypeError(
                    "CALL/PUT requires exact selected candidate"
                )
            expected_market = (
                self.selected_candidate.underlying_symbol,
                self.selected_candidate.exchange,
            )
            if self.selected_market != expected_market:
                raise ValueError("selected candidate identity mismatch")
            expected_direction = (
                "BULLISH" if action == "CALL" else "BEARISH"
            )
            if self.selected_candidate.direction != expected_direction:
                raise ValueError("action/direction mismatch")
            if self.selected_candidate.eligibility != "ELIGIBLE":
                raise ValueError("selected candidate must be ELIGIBLE")
            if self.blockers:
                raise ValueError("CALL/PUT cannot contain blockers")
        else:
            if self.planning_allowed:
                raise ValueError(
                    "WAIT/NO_TRADE cannot allow planning"
                )
            if action == "NO_TRADE":
                if (
                    self.selected_market is not None
                    or self.selected_candidate is not None
                ):
                    raise ValueError(
                        "NO_TRADE cannot retain selected market"
                    )
            elif self.selected_candidate is not None:
                if type(self.selected_candidate) is not MarketAnalysisCandidateV1:
                    raise TypeError("selected_candidate")
                expected_market = (
                    self.selected_candidate.underlying_symbol,
                    self.selected_candidate.exchange,
                )
                if self.selected_market != expected_market:
                    raise ValueError(
                        "WAIT candidate identity mismatch"
                    )

        if self.losing_market is None:
            if (
                self.losing_outcome_reason is not None
                or self.losing_rationale
            ):
                raise ValueError(
                    "losing diagnostics require losing market"
                )
        elif self.losing_outcome_reason is None:
            raise ValueError(
                "losing market requires outcome reason"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only bridge result")
