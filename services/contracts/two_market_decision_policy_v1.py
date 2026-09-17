"""Exact NIFTY/SENSEX decision policy for one parent PAPER cycle."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import ClassVar


_EXACT_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))
_SCORE_FIELDS = ("score", "confidence")


def _positive_finite(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class TwoMarketDecisionPolicyV1:
    """Immutable freshness, skew, eligibility, and tie policy."""

    SCHEMA_VERSION: ClassVar[str] = "two_market_decision_policy.v1"

    max_candidate_age_seconds: float
    max_timestamp_skew_seconds: float
    score_field: str = "score"
    confidence_tie_break: bool = True
    deterministic_market_order: tuple[tuple[str, str], ...] = _EXACT_MARKETS
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_candidate_age_seconds",
            _positive_finite(
                self.max_candidate_age_seconds,
                "max_candidate_age_seconds",
            ),
        )
        object.__setattr__(
            self,
            "max_timestamp_skew_seconds",
            _positive_finite(
                self.max_timestamp_skew_seconds,
                "max_timestamp_skew_seconds",
            ),
        )

        if self.score_field not in _SCORE_FIELDS:
            raise ValueError("score_field")
        if type(self.confidence_tie_break) is not bool:
            raise TypeError("confidence_tie_break")

        if self.deterministic_market_order != _EXACT_MARKETS:
            raise ValueError(
                "deterministic_market_order must be exact NIFTY/SENSEX order"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only policy")
