"""Policy for exact selected option-contract certification."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import ClassVar


def _positive(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


def _fraction(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(name)
    return float(value)


def _non_negative(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0.0
    ):
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class SelectedOptionContractCertificationPolicyV1:
    """Explicit fail-closed thresholds for one selected contract."""

    SCHEMA_VERSION: ClassVar[str] = (
        "selected_option_contract_certification_policy.v1"
    )

    maximum_ranking_age_seconds: float
    maximum_contract_age_seconds: float
    maximum_quote_age_seconds: float
    maximum_spread_fraction: float
    minimum_liquidity_score: float
    minimum_open_interest: float
    minimum_volume: float
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "maximum_ranking_age_seconds",
            _positive(
                self.maximum_ranking_age_seconds,
                "maximum_ranking_age_seconds",
            ),
        )
        object.__setattr__(
            self,
            "maximum_contract_age_seconds",
            _positive(
                self.maximum_contract_age_seconds,
                "maximum_contract_age_seconds",
            ),
        )
        object.__setattr__(
            self,
            "maximum_quote_age_seconds",
            _positive(
                self.maximum_quote_age_seconds,
                "maximum_quote_age_seconds",
            ),
        )
        object.__setattr__(
            self,
            "maximum_spread_fraction",
            _fraction(
                self.maximum_spread_fraction,
                "maximum_spread_fraction",
            ),
        )
        object.__setattr__(
            self,
            "minimum_liquidity_score",
            _fraction(
                self.minimum_liquidity_score,
                "minimum_liquidity_score",
            ),
        )
        object.__setattr__(
            self,
            "minimum_open_interest",
            _non_negative(
                self.minimum_open_interest,
                "minimum_open_interest",
            ),
        )
        object.__setattr__(
            self,
            "minimum_volume",
            _non_negative(
                self.minimum_volume,
                "minimum_volume",
            ),
        )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only certification policy")
