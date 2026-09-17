"""Canonical policy for deterministic trade-opportunity integration."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping


_ALLOWED_DECISION_POLICIES = frozenset(
    {
        "REQUIRE_DIRECTIONAL",
        "ALLOW_ANALYSIS_ONLY",
    }
)

_ALLOWED_SESSION_POLICIES = frozenset(
    {
        "REQUIRE_ANALYSIS_ALLOWED",
        "REQUIRE_PAPER_PREPARATION_ALLOWED",
    }
)


def _require_unit_score(
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

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            f"{field_name} must be between zero and one"
        )

    return normalized


def _require_positive(
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

    if normalized <= 0.0:
        raise ValueError(
            f"{field_name} must be greater than zero"
        )

    return normalized


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
class TradeOpportunityPolicyV1:
    """Thresholds and weights for canonical opportunity integration."""

    technical_weight: float = 0.30
    option_chain_weight: float = 0.25
    contract_ranking_weight: float = 0.25
    decision_confidence_weight: float = 0.20

    minimum_technical_strength: float = 0.35
    minimum_option_chain_strength: float = 0.35
    minimum_contract_ranking_score: float = 0.50
    minimum_decision_confidence: float = 0.50
    minimum_opportunity_score: float = 0.60

    maximum_source_age_seconds: float = 300.0
    maximum_future_skew_seconds: float = 5.0

    decision_policy: str = "REQUIRE_DIRECTIONAL"
    session_policy: str = (
        "REQUIRE_PAPER_PREPARATION_ALLOWED"
    )

    require_matching_direction: bool = True
    require_ready_technical_intelligence: bool = True
    require_ready_option_chain_intelligence: bool = True
    require_ranked_contract: bool = True

    metadata: Mapping[str, Any] = field(default_factory=dict)

    schema_version: ClassVar[str] = (
        "trade_opportunity_policy.v1"
    )
    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False

    def __post_init__(self) -> None:
        weight_fields = (
            "technical_weight",
            "option_chain_weight",
            "contract_ranking_weight",
            "decision_confidence_weight",
        )

        for field_name in weight_fields:
            object.__setattr__(
                self,
                field_name,
                _require_unit_score(
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
                "opportunity weights must sum to exactly one"
            )

        for field_name in (
            "minimum_technical_strength",
            "minimum_option_chain_strength",
            "minimum_contract_ranking_score",
            "minimum_decision_confidence",
            "minimum_opportunity_score",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_unit_score(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        for field_name in (
            "maximum_source_age_seconds",
            "maximum_future_skew_seconds",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_positive(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "decision_policy",
            _require_policy_value(
                self.decision_policy,
                "decision_policy",
                _ALLOWED_DECISION_POLICIES,
            ),
        )

        object.__setattr__(
            self,
            "session_policy",
            _require_policy_value(
                self.session_policy,
                "session_policy",
                _ALLOWED_SESSION_POLICIES,
            ),
        )

        for field_name in (
            "require_matching_direction",
            "require_ready_technical_intelligence",
            "require_ready_option_chain_intelligence",
            "require_ranked_contract",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(
                    f"{field_name} must be a boolean"
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
            "technical": self.technical_weight,
            "option_chain": self.option_chain_weight,
            "contract_ranking": self.contract_ranking_weight,
            "decision_confidence": (
                self.decision_confidence_weight
            ),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "weights": self.weights,
            "minimum_technical_strength": (
                self.minimum_technical_strength
            ),
            "minimum_option_chain_strength": (
                self.minimum_option_chain_strength
            ),
            "minimum_contract_ranking_score": (
                self.minimum_contract_ranking_score
            ),
            "minimum_decision_confidence": (
                self.minimum_decision_confidence
            ),
            "minimum_opportunity_score": (
                self.minimum_opportunity_score
            ),
            "maximum_source_age_seconds": (
                self.maximum_source_age_seconds
            ),
            "maximum_future_skew_seconds": (
                self.maximum_future_skew_seconds
            ),
            "decision_policy": self.decision_policy,
            "session_policy": self.session_policy,
            "require_matching_direction": (
                self.require_matching_direction
            ),
            "require_ready_technical_intelligence": (
                self.require_ready_technical_intelligence
            ),
            "require_ready_option_chain_intelligence": (
                self.require_ready_option_chain_intelligence
            ),
            "require_ranked_contract": (
                self.require_ranked_contract
            ),
            "metadata": dict(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }


DEFAULT_TRADE_OPPORTUNITY_POLICY = TradeOpportunityPolicyV1()