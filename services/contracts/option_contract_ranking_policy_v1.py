"""Canonical policy for deterministic option-contract ranking."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping


_ALLOWED_EXPIRY_POLICIES = frozenset(
    {
        "EARLIEST_ELIGIBLE",
        "ALL_ELIGIBLE",
        "EXPLICIT_EXPIRY_ONLY",
    }
)

_ALLOWED_INTELLIGENCE_POLICIES = frozenset(
    {
        "REQUIRE_DIRECTIONAL",
        "ALLOW_NEUTRAL",
        "IGNORE",
    }
)

_ALLOWED_REFERENCE_PRICE_POLICIES = frozenset(
    {
        "MID",
        "ASK",
        "LAST",
        "BEST_AVAILABLE",
    }
)


def _require_finite(
    value: object,
    field_name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise TypeError(f"{field_name} must be numeric")

    normalized = float(value)

    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    return normalized


def _require_non_negative(
    value: object,
    field_name: str,
) -> float:
    normalized = _require_finite(value, field_name)

    if normalized < 0.0:
        raise ValueError(
            f"{field_name} must be non-negative"
        )

    return normalized


def _require_positive(
    value: object,
    field_name: str,
) -> float:
    normalized = _require_finite(value, field_name)

    if normalized <= 0.0:
        raise ValueError(
            f"{field_name} must be greater than zero"
        )

    return normalized


def _require_unit_interval(
    value: object,
    field_name: str,
) -> float:
    normalized = _require_finite(value, field_name)

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            f"{field_name} must be between zero and one"
        )

    return normalized


def _require_positive_int(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")

    if value <= 0:
        raise ValueError(
            f"{field_name} must be greater than zero"
        )

    return value


def _require_policy_value(
    value: object,
    field_name: str,
    allowed: frozenset[str],
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip().upper()

    if normalized not in allowed:
        raise ValueError(
            f"unsupported {field_name}: {normalized}"
        )

    return normalized


@dataclass(frozen=True, slots=True)
class OptionContractRankingPolicyV1:
    """Thresholds and weights for canonical contract ranking."""

    maximum_universe_age_seconds: float = 300.0
    maximum_contract_age_seconds: float = 300.0
    maximum_future_skew_seconds: float = 5.0

    require_trusted_universe: bool = True
    require_bid_ask: bool = True
    require_volume: bool = True
    require_open_interest: bool = True
    require_implied_volatility: bool = False

    maximum_spread_percent: float = 5.0
    minimum_volume: float = 100.0
    minimum_open_interest: float = 500.0
    minimum_implied_volatility: float = 0.0
    maximum_implied_volatility: float = 200.0
    maximum_strike_distance_percent: float = 5.0

    expiry_policy: str = "EARLIEST_ELIGIBLE"
    intelligence_policy: str = "REQUIRE_DIRECTIONAL"
    reference_price_policy: str = "BEST_AVAILABLE"

    liquidity_weight: float = 0.25
    proximity_weight: float = 0.20
    open_interest_weight: float = 0.15
    volume_weight: float = 0.15
    spread_weight: float = 0.10
    implied_volatility_weight: float = 0.05
    intelligence_alignment_weight: float = 0.10

    maximum_ranked_candidates: int = 10
    metadata: Mapping[str, Any] = field(default_factory=dict)

    schema_version: ClassVar[str] = (
        "option_contract_ranking_policy.v1"
    )
    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False

    def __post_init__(self) -> None:
        for field_name in (
            "require_trusted_universe",
            "require_bid_ask",
            "require_volume",
            "require_open_interest",
            "require_implied_volatility",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(
                    f"{field_name} must be a boolean"
                )

        for field_name in (
            "maximum_universe_age_seconds",
            "maximum_contract_age_seconds",
            "maximum_future_skew_seconds",
            "maximum_spread_percent",
            "minimum_volume",
            "minimum_open_interest",
            "minimum_implied_volatility",
            "maximum_implied_volatility",
            "maximum_strike_distance_percent",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_negative(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.maximum_universe_age_seconds == 0.0:
            raise ValueError(
                "maximum_universe_age_seconds must be positive"
            )

        if self.maximum_contract_age_seconds == 0.0:
            raise ValueError(
                "maximum_contract_age_seconds must be positive"
            )

        if (
            self.maximum_implied_volatility
            < self.minimum_implied_volatility
        ):
            raise ValueError(
                "maximum_implied_volatility cannot be below "
                "minimum_implied_volatility"
            )

        if self.maximum_spread_percent == 0.0:
            raise ValueError(
                "maximum_spread_percent must be positive"
            )

        if self.maximum_strike_distance_percent == 0.0:
            raise ValueError(
                "maximum_strike_distance_percent must be positive"
            )

        object.__setattr__(
            self,
            "expiry_policy",
            _require_policy_value(
                self.expiry_policy,
                "expiry_policy",
                _ALLOWED_EXPIRY_POLICIES,
            ),
        )
        object.__setattr__(
            self,
            "intelligence_policy",
            _require_policy_value(
                self.intelligence_policy,
                "intelligence_policy",
                _ALLOWED_INTELLIGENCE_POLICIES,
            ),
        )
        object.__setattr__(
            self,
            "reference_price_policy",
            _require_policy_value(
                self.reference_price_policy,
                "reference_price_policy",
                _ALLOWED_REFERENCE_PRICE_POLICIES,
            ),
        )

        weight_fields = (
            "liquidity_weight",
            "proximity_weight",
            "open_interest_weight",
            "volume_weight",
            "spread_weight",
            "implied_volatility_weight",
            "intelligence_alignment_weight",
        )

        for field_name in weight_fields:
            object.__setattr__(
                self,
                field_name,
                _require_unit_interval(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        total_weight = sum(
            getattr(self, field_name)
            for field_name in weight_fields
        )

        if not math.isclose(
            total_weight,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                "ranking weights must sum to exactly one"
            )

        object.__setattr__(
            self,
            "maximum_ranked_candidates",
            _require_positive_int(
                self.maximum_ranked_candidates,
                "maximum_ranked_candidates",
            ),
        )

        try:
            json.dumps(
                self.metadata,
                sort_keys=True,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "metadata must be safe JSON data"
            ) from exc

        object.__setattr__(
            self,
            "metadata",
            dict(self.metadata),
        )

    @property
    def weights(self) -> dict[str, float]:
        return {
            "liquidity": self.liquidity_weight,
            "proximity": self.proximity_weight,
            "open_interest": self.open_interest_weight,
            "volume": self.volume_weight,
            "spread": self.spread_weight,
            "implied_volatility": (
                self.implied_volatility_weight
            ),
            "intelligence_alignment": (
                self.intelligence_alignment_weight
            ),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "maximum_universe_age_seconds": (
                self.maximum_universe_age_seconds
            ),
            "maximum_contract_age_seconds": (
                self.maximum_contract_age_seconds
            ),
            "maximum_future_skew_seconds": (
                self.maximum_future_skew_seconds
            ),
            "require_trusted_universe": (
                self.require_trusted_universe
            ),
            "require_bid_ask": self.require_bid_ask,
            "require_volume": self.require_volume,
            "require_open_interest": (
                self.require_open_interest
            ),
            "require_implied_volatility": (
                self.require_implied_volatility
            ),
            "maximum_spread_percent": (
                self.maximum_spread_percent
            ),
            "minimum_volume": self.minimum_volume,
            "minimum_open_interest": (
                self.minimum_open_interest
            ),
            "minimum_implied_volatility": (
                self.minimum_implied_volatility
            ),
            "maximum_implied_volatility": (
                self.maximum_implied_volatility
            ),
            "maximum_strike_distance_percent": (
                self.maximum_strike_distance_percent
            ),
            "expiry_policy": self.expiry_policy,
            "intelligence_policy": self.intelligence_policy,
            "reference_price_policy": (
                self.reference_price_policy
            ),
            "weights": self.weights,
            "maximum_ranked_candidates": (
                self.maximum_ranked_candidates
            ),
            "metadata": dict(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }


DEFAULT_OPTION_CONTRACT_RANKING_POLICY = (
    OptionContractRankingPolicyV1()
)