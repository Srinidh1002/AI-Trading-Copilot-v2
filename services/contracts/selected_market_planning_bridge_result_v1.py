"""Selected-market authorization result before contract and capital planning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)


_ACTIONS = {"CALL", "PUT", "WAIT", "NO_TRADE"}
_DIRECTIONS = {"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE", "CONFLICTING"}
_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}


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


def _optional_score(value: object, name: str) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or not 0.0 <= value <= 100.0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class SelectedMarketPlanningBridgeResultV1:
    """One selected planner handoff or an explicit blocked terminal result."""

    SCHEMA_VERSION: ClassVar[str] = (
        "selected_market_planning_bridge_result.v1"
    )

    bridge_result_id: str
    parent_cycle_id: str
    parent_decision_id: str
    evaluated_at: datetime
    action: str
    planning_allowed: bool
    selected_market: tuple[str, str] | None
    selected_candidate: MarketAnalysisCandidateV1 | None
    selected_child_result_id: str | None
    selected_child_action: str
    candidate_id: str | None
    observation_id: str | None
    direction: str | None
    confidence: float | None
    score: float | None
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
        for name in (
            "bridge_result_id",
            "parent_cycle_id",
            "parent_decision_id",
        ):
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

        selected_child_action = _text(
            self.selected_child_action,
            "selected_child_action",
        ).upper()
        if selected_child_action not in _ACTIONS:
            raise ValueError("selected_child_action")
        object.__setattr__(
            self,
            "selected_child_action",
            selected_child_action,
        )

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

        for name in (
            "selected_child_result_id",
            "candidate_id",
            "observation_id",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(getattr(self, name), name),
            )

        if self.direction is not None:
            direction = _text(self.direction, "direction").upper()
            if direction not in _DIRECTIONS:
                raise ValueError("direction")
            object.__setattr__(self, "direction", direction)

        for name in ("confidence", "score"):
            object.__setattr__(
                self,
                name,
                _optional_score(getattr(self, name), name),
            )

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

        if action != selected_child_action:
            raise ValueError("selected_child_action must equal action")

        if action in {"CALL", "PUT", "WAIT"}:
            if type(self.selected_candidate) is not MarketAnalysisCandidateV1:
                raise TypeError(
                    "selected action requires exact selected candidate"
                )
            if self.selected_market is None:
                raise ValueError("selected action requires selected market")
            if self.selected_child_result_id is None:
                raise ValueError(
                    "selected action requires selected_child_result_id"
                )
            if self.candidate_id is None or self.observation_id is None:
                raise ValueError(
                    "selected action requires candidate and observation identity"
                )
            if self.direction is None:
                raise ValueError("selected action requires direction")
            if self.confidence is None or self.score is None:
                raise ValueError("selected action requires confidence and score")

            expected_market = (
                self.selected_candidate.underlying_symbol,
                self.selected_candidate.exchange,
            )
            if self.selected_market != expected_market:
                raise ValueError("selected candidate identity mismatch")
            if self.candidate_id != self.selected_candidate.candidate_id:
                raise ValueError("candidate_id mismatch")
            if self.observation_id != self.selected_candidate.observation_id:
                raise ValueError("observation_id mismatch")
            if self.direction != self.selected_candidate.direction:
                raise ValueError("direction mismatch")
            if self.confidence != self.selected_candidate.confidence:
                raise ValueError("confidence mismatch")
            if self.score != self.selected_candidate.score:
                raise ValueError("score mismatch")

        if action in {"CALL", "PUT"}:
            if not self.planning_allowed:
                raise ValueError("CALL/PUT requires planning_allowed")
            expected_direction = (
                "BULLISH" if action == "CALL" else "BEARISH"
            )
            if self.direction != expected_direction:
                raise ValueError("action/direction mismatch")
            if self.selected_candidate.eligibility != "ELIGIBLE":
                raise ValueError("selected candidate must be ELIGIBLE")
            if self.blockers:
                raise ValueError("CALL/PUT cannot contain blockers")
        elif action == "WAIT":
            if self.planning_allowed:
                raise ValueError("WAIT cannot allow planning")
            if not self.blockers:
                raise ValueError("WAIT requires blocker")
        else:
            if self.planning_allowed:
                raise ValueError("NO_TRADE cannot allow planning")
            if any(
                value is not None
                for value in (
                    self.selected_market,
                    self.selected_candidate,
                    self.selected_child_result_id,
                    self.candidate_id,
                    self.observation_id,
                    self.direction,
                    self.confidence,
                    self.score,
                )
            ):
                raise ValueError(
                    "NO_TRADE cannot retain selected identity"
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
            raise ValueError("losing market requires outcome reason")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only bridge result")
