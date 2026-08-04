"""Exact two-market parent decision result for NIFTY and SENSEX."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)


_EXACT_ORDER = (("NIFTY", "NSE"), ("SENSEX", "BSE"))
_DECISIONS = {"SELECTED", "NO_TRADE"}
_REASONS = {"SELECTED", "INELIGIBLE", "STALE", "SKEW_BLOCKED", "CHILD_FAILED", "LOWER_RANK", "TIE_BREAK_LOSS"}


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
class TwoMarketDecisionEntryV1:
    """Retained per-market comparison outcome."""

    child: TwoMarketChildTerminalResultV1
    eligible_for_comparison: bool
    rank_value: float
    outcome_reason: str
    rationale: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.child) is not TwoMarketChildTerminalResultV1:
            raise TypeError("child")
        if type(self.eligible_for_comparison) is not bool:
            raise TypeError("eligible_for_comparison")
        if (
            type(self.rank_value) not in (int, float)
            or isinstance(self.rank_value, bool)
            or not isfinite(self.rank_value)
            or not 0.0 <= self.rank_value <= 100.0
        ):
            raise ValueError("rank_value")
        object.__setattr__(self, "rank_value", float(self.rank_value))

        reason = _text(self.outcome_reason, "outcome_reason").upper()
        if reason not in _REASONS:
            raise ValueError("outcome_reason")
        object.__setattr__(self, "outcome_reason", reason)
        object.__setattr__(
            self,
            "rationale",
            _messages(self.rationale, "rationale"),
        )

        if self.eligible_for_comparison:
            if self.child.terminal_status != "COMPLETED":
                raise ValueError("eligible entry requires completed child")
            if self.child.candidate.eligibility != "ELIGIBLE":
                raise ValueError("eligible entry requires eligible candidate")
            if self.rank_value <= 0.0:
                raise ValueError("eligible entry requires positive rank")
        elif self.rank_value != 0.0:
            raise ValueError("ineligible entry must use zero rank")


@dataclass(frozen=True, slots=True)
class TwoMarketDecisionResultV1:
    """Parent result retaining exactly NIFTY and SENSEX terminal outcomes."""

    SCHEMA_VERSION: ClassVar[str] = "two_market_decision_result.v1"

    decision_result_id: str
    parent_cycle_id: str
    requested_at: datetime
    completed_at: datetime
    entries: tuple[TwoMarketDecisionEntryV1, TwoMarketDecisionEntryV1]
    decision: str
    selected_market: tuple[str, str] | None
    selected_candidate_id: str | None
    timestamp_skew_seconds: float
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("decision_result_id", "parent_cycle_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        requested = _aware(self.requested_at, "requested_at")
        completed = _aware(self.completed_at, "completed_at")
        if requested > completed:
            raise ValueError("requested_at must not exceed completed_at")
        object.__setattr__(self, "requested_at", requested)
        object.__setattr__(self, "completed_at", completed)

        if not isinstance(self.entries, tuple) or len(self.entries) != 2:
            raise ValueError("entries must contain exactly two markets")
        if not all(type(item) is TwoMarketDecisionEntryV1 for item in self.entries):
            raise TypeError("entries")
        order = tuple(
            (item.child.underlying_symbol, item.child.exchange)
            for item in self.entries
        )
        if order != _EXACT_ORDER:
            raise ValueError("entries must be exact ordered NIFTY/SENSEX pair")
        if any(item.child.parent_cycle_id != self.parent_cycle_id for item in self.entries):
            raise ValueError("child parent_cycle_id mismatch")

        decision = _text(self.decision, "decision").upper()
        if decision not in _DECISIONS:
            raise ValueError("decision")
        object.__setattr__(self, "decision", decision)

        if (
            type(self.timestamp_skew_seconds) not in (int, float)
            or isinstance(self.timestamp_skew_seconds, bool)
            or not isfinite(self.timestamp_skew_seconds)
            or self.timestamp_skew_seconds < 0.0
        ):
            raise ValueError("timestamp_skew_seconds")
        object.__setattr__(
            self,
            "timestamp_skew_seconds",
            float(self.timestamp_skew_seconds),
        )

        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))

        selected_entries = tuple(
            item for item in self.entries if item.outcome_reason == "SELECTED"
        )
        if decision == "SELECTED":
            if len(selected_entries) != 1:
                raise ValueError("SELECTED requires exactly one selected entry")
            selected = selected_entries[0]
            expected_market = (
                selected.child.underlying_symbol,
                selected.child.exchange,
            )
            expected_id = selected.child.candidate.candidate_id
            if self.selected_market != expected_market:
                raise ValueError("selected_market mismatch")
            if self.selected_candidate_id != expected_id:
                raise ValueError("selected_candidate_id mismatch")
        else:
            if selected_entries:
                raise ValueError("NO_TRADE cannot contain selected entry")
            if self.selected_market is not None or self.selected_candidate_id is not None:
                raise ValueError("NO_TRADE must not identify a selected market")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only decision result")
