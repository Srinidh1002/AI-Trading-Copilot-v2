"""Canonical scored option-contract candidate contract."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import ClassVar

from .option_contract_v1 import OptionContractV1


_ALLOWED_STATUSES = frozenset(
    {
        "ELIGIBLE",
        "ELIGIBLE_WITH_WARNINGS",
        "REJECTED",
        "MALFORMED",
        "FAILED",
    }
)

_ALLOWED_MONEYNESS = frozenset(
    {
        "ITM",
        "ATM",
        "OTM",
        "UNKNOWN",
    }
)


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")

    return normalized


def _require_string_tuple(
    value: object,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    normalized: list[str] = []

    for item in value:
        text = _require_text(item, field_name).upper()

        if text in normalized:
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

        normalized.append(text)

    return tuple(normalized)


def _require_score(
    value: object,
    field_name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise TypeError(f"{field_name} must be numeric")

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            f"{field_name} must be between zero and one"
        )

    return normalized


def _require_non_negative(
    value: object,
    field_name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise TypeError(f"{field_name} must be numeric")

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    if normalized < 0.0:
        raise ValueError(
            f"{field_name} must be non-negative"
        )

    return normalized


@dataclass(frozen=True, slots=True)
class OptionContractCandidateV1:
    """Eligibility and score details for one option contract."""

    contract: OptionContractV1
    candidate_status: str
    moneyness: str
    strike_distance_percent: float
    spread_percent: float | None
    liquidity_score: float
    proximity_score: float
    open_interest_score: float
    volume_score: float
    spread_score: float
    implied_volatility_score: float
    intelligence_alignment_score: float
    total_score: float
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    schema_version: ClassVar[str] = (
        "option_contract_candidate.v1"
    )
    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if not isinstance(self.contract, OptionContractV1):
            raise TypeError(
                "contract must be an OptionContractV1"
            )

        status = _require_text(
            self.candidate_status,
            "candidate_status",
        ).upper()

        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"unsupported candidate_status: {status}"
            )

        object.__setattr__(
            self,
            "candidate_status",
            status,
        )

        moneyness = _require_text(
            self.moneyness,
            "moneyness",
        ).upper()

        if moneyness not in _ALLOWED_MONEYNESS:
            raise ValueError(
                f"unsupported moneyness: {moneyness}"
            )

        object.__setattr__(self, "moneyness", moneyness)

        object.__setattr__(
            self,
            "strike_distance_percent",
            _require_non_negative(
                self.strike_distance_percent,
                "strike_distance_percent",
            ),
        )

        if self.spread_percent is not None:
            object.__setattr__(
                self,
                "spread_percent",
                _require_non_negative(
                    self.spread_percent,
                    "spread_percent",
                ),
            )

        for field_name in (
            "liquidity_score",
            "proximity_score",
            "open_interest_score",
            "volume_score",
            "spread_score",
            "implied_volatility_score",
            "intelligence_alignment_score",
            "total_score",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_score(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        rejection_reasons = _require_string_tuple(
            self.rejection_reasons,
            "rejection_reasons",
        )
        warnings = _require_string_tuple(
            self.warnings,
            "warnings",
        )

        object.__setattr__(
            self,
            "rejection_reasons",
            rejection_reasons,
        )
        object.__setattr__(self, "warnings", warnings)

        eligible = status in {
            "ELIGIBLE",
            "ELIGIBLE_WITH_WARNINGS",
        }

        if eligible and rejection_reasons:
            raise ValueError(
                "eligible candidates cannot have rejection reasons"
            )

        if status == "ELIGIBLE" and warnings:
            raise ValueError(
                "ELIGIBLE candidates cannot have warnings"
            )

        if (
            status == "ELIGIBLE_WITH_WARNINGS"
            and not warnings
        ):
            raise ValueError(
                "ELIGIBLE_WITH_WARNINGS requires warnings"
            )

        if (
            status in {"REJECTED", "MALFORMED", "FAILED"}
            and not rejection_reasons
        ):
            raise ValueError(
                "non-eligible candidates require rejection reasons"
            )

        if not eligible and self.total_score != 0.0:
            raise ValueError(
                "non-eligible candidates must have zero total_score"
            )

    @property
    def eligible(self) -> bool:
        return self.candidate_status in {
            "ELIGIBLE",
            "ELIGIBLE_WITH_WARNINGS",
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "contract": self.contract.to_dict(),
            "candidate_status": self.candidate_status,
            "eligible": self.eligible,
            "moneyness": self.moneyness,
            "strike_distance_percent": (
                self.strike_distance_percent
            ),
            "spread_percent": self.spread_percent,
            "liquidity_score": self.liquidity_score,
            "proximity_score": self.proximity_score,
            "open_interest_score": self.open_interest_score,
            "volume_score": self.volume_score,
            "spread_score": self.spread_score,
            "implied_volatility_score": (
                self.implied_volatility_score
            ),
            "intelligence_alignment_score": (
                self.intelligence_alignment_score
            ),
            "total_score": self.total_score,
            "rejection_reasons": list(
                self.rejection_reasons
            ),
            "warnings": list(self.warnings),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }