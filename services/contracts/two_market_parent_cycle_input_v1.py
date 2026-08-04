"""Exact NIFTY/SENSEX parent-cycle input for deterministic PAPER coordination."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)


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


@dataclass(frozen=True, slots=True)
class TwoMarketParentCycleInputV1:
    """Explicit IDs and timestamps for one exact two-market parent cycle."""

    SCHEMA_VERSION: ClassVar[str] = "two_market_parent_cycle_input.v1"

    parent_cycle_id: str
    decision_result_id: str
    nifty_child_result_id: str
    sensex_child_result_id: str
    nifty_observation_id: str
    sensex_observation_id: str
    requested_at: datetime
    completed_at: datetime
    decision_policy: TwoMarketDecisionPolicyV1
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "parent_cycle_id",
            "decision_result_id",
            "nifty_child_result_id",
            "sensex_child_result_id",
            "nifty_observation_id",
            "sensex_observation_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        if len(
            {
                self.nifty_child_result_id,
                self.sensex_child_result_id,
            }
        ) != 2:
            raise ValueError("child result IDs must be distinct")
        if len(
            {
                self.nifty_observation_id,
                self.sensex_observation_id,
            }
        ) != 2:
            raise ValueError("observation IDs must be distinct")

        requested = _aware(self.requested_at, "requested_at")
        completed = _aware(self.completed_at, "completed_at")
        if requested > completed:
            raise ValueError("requested_at must not exceed completed_at")
        object.__setattr__(self, "requested_at", requested)
        object.__setattr__(self, "completed_at", completed)

        if type(self.decision_policy) is not TwoMarketDecisionPolicyV1:
            raise TypeError("decision_policy")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only parent cycle input")
