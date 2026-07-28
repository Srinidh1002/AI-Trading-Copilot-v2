"""Canonical result contract for option-contract ranking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Mapping

from services.core.market_identity import (
    SUPPORTED_MARKET_IDENTITIES,
)

from .option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)


_ALLOWED_STATUSES = frozenset(
    {
        "RANKED",
        "RANKED_WITH_WARNINGS",
        "NO_ELIGIBLE_CONTRACTS",
        "BLOCKED",
        "INSUFFICIENT_DATA",
        "FAILED",
    }
)

_ALLOWED_BIASES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "MIXED",
        "UNAVAILABLE",
    }
)

_ALLOWED_OPTION_TYPES = frozenset(
    {
        "CALL",
        "PUT",
    }
)


def _require_text(
    value: object,
    field_name: str,
) -> str:
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
        text = _require_text(
            item,
            field_name,
        ).upper()

        if text in normalized:
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

        normalized.append(text)

    return tuple(normalized)


def _require_candidate_tuple(
    value: object,
    field_name: str,
) -> tuple[OptionContractCandidateV1, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    if not all(
        isinstance(item, OptionContractCandidateV1)
        for item in value
    ):
        raise TypeError(
            f"{field_name} must contain only "
            "OptionContractCandidateV1 values"
        )

    contract_ids = tuple(
        item.contract.contract_id
        for item in value
    )

    if len(set(contract_ids)) != len(contract_ids):
        raise ValueError(
            f"{field_name} must not contain duplicate contracts"
        )

    return value


@dataclass(frozen=True, slots=True)
class OptionContractRankingResultV1:
    """Immutable output from canonical contract ranking."""

    ranking_id: str
    ranked_at: datetime
    universe_id: str | None
    intelligence_result_id: str | None

    underlying_symbol: str
    exchange: str
    directional_bias: str
    required_option_type: str | None

    ranking_status: str
    ranked_candidates: tuple[
        OptionContractCandidateV1,
        ...
    ] = ()
    rejected_candidates: tuple[
        OptionContractCandidateV1,
        ...
    ] = ()

    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    schema_version: ClassVar[str] = (
        "option_contract_ranking_result.v1"
    )
    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ranking_id",
            _require_text(
                self.ranking_id,
                "ranking_id",
            ),
        )

        if not isinstance(self.ranked_at, datetime):
            raise TypeError(
                "ranked_at must be a datetime"
            )

        if self.ranked_at.tzinfo is None:
            raise ValueError(
                "ranked_at must be timezone-aware"
            )

        if self.universe_id is not None:
            object.__setattr__(
                self,
                "universe_id",
                _require_text(
                    self.universe_id,
                    "universe_id",
                ),
            )

        if self.intelligence_result_id is not None:
            object.__setattr__(
                self,
                "intelligence_result_id",
                _require_text(
                    self.intelligence_result_id,
                    "intelligence_result_id",
                ),
            )

        identity = (
            self.underlying_symbol,
            self.exchange,
        )

        if identity not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError(
                "unsupported market identity"
            )

        bias = _require_text(
            self.directional_bias,
            "directional_bias",
        ).upper()

        if bias not in _ALLOWED_BIASES:
            raise ValueError(
                f"unsupported directional_bias: {bias}"
            )

        object.__setattr__(
            self,
            "directional_bias",
            bias,
        )

        option_type = self.required_option_type

        if option_type is not None:
            option_type = _require_text(
                option_type,
                "required_option_type",
            ).upper()

            if option_type not in _ALLOWED_OPTION_TYPES:
                raise ValueError(
                    "required_option_type must be "
                    "CALL, PUT, or None"
                )

            object.__setattr__(
                self,
                "required_option_type",
                option_type,
            )

        expected_option_type = (
            "CALL"
            if bias == "BULLISH"
            else "PUT"
            if bias == "BEARISH"
            else None
        )

        if option_type != expected_option_type:
            raise ValueError(
                "required_option_type does not match "
                "directional_bias"
            )

        status = _require_text(
            self.ranking_status,
            "ranking_status",
        ).upper()

        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"unsupported ranking_status: {status}"
            )

        object.__setattr__(
            self,
            "ranking_status",
            status,
        )

        ranked_candidates = _require_candidate_tuple(
            self.ranked_candidates,
            "ranked_candidates",
        )
        rejected_candidates = _require_candidate_tuple(
            self.rejected_candidates,
            "rejected_candidates",
        )

        ranked_ids = {
            candidate.contract.contract_id
            for candidate in ranked_candidates
        }
        rejected_ids = {
            candidate.contract.contract_id
            for candidate in rejected_candidates
        }

        if ranked_ids & rejected_ids:
            raise ValueError(
                "a contract cannot be both ranked and rejected"
            )

        for candidate in ranked_candidates:
            if not candidate.eligible:
                raise ValueError(
                    "ranked_candidates must be eligible"
                )

            if (
                candidate.contract.underlying_symbol,
                candidate.contract.exchange,
            ) != identity:
                raise ValueError(
                    "ranked candidate identity mismatch"
                )

            if (
                option_type is not None
                and candidate.contract.option_type
                != option_type
            ):
                raise ValueError(
                    "ranked candidate option type mismatch"
                )

        for candidate in rejected_candidates:
            if candidate.eligible:
                raise ValueError(
                    "rejected_candidates must be ineligible"
                )

            if (
                candidate.contract.underlying_symbol,
                candidate.contract.exchange,
            ) != identity:
                raise ValueError(
                    "rejected candidate identity mismatch"
                )

        expected_order = tuple(
            sorted(
                ranked_candidates,
                key=lambda candidate: (
                    -candidate.total_score,
                    candidate.strike_distance_percent,
                    (
                        candidate.spread_percent
                        if candidate.spread_percent is not None
                        else float("inf")
                    ),
                    candidate.contract.expiry_date,
                    candidate.contract.strike,
                    candidate.contract.contract_id,
                ),
            )
        )

        if ranked_candidates != expected_order:
            raise ValueError(
                "ranked_candidates are not in canonical order"
            )

        blockers = _require_string_tuple(
            self.blockers,
            "blockers",
        )
        warnings = _require_string_tuple(
            self.warnings,
            "warnings",
        )
        diagnostics = _require_string_tuple(
            self.diagnostics,
            "diagnostics",
        )

        object.__setattr__(
            self,
            "blockers",
            blockers,
        )
        object.__setattr__(
            self,
            "warnings",
            warnings,
        )
        object.__setattr__(
            self,
            "diagnostics",
            diagnostics,
        )

        successful_status = status in {
            "RANKED",
            "RANKED_WITH_WARNINGS",
        }

        if successful_status and blockers:
            raise ValueError(
                "successful ranking cannot contain blockers"
            )

        if status == "RANKED":
            if not ranked_candidates:
                raise ValueError(
                    "RANKED requires ranked candidates"
                )

            if warnings:
                raise ValueError(
                    "RANKED cannot contain warnings"
                )

        if status == "RANKED_WITH_WARNINGS":
            if not ranked_candidates:
                raise ValueError(
                    "RANKED_WITH_WARNINGS requires "
                    "ranked candidates"
                )

            if not warnings:
                raise ValueError(
                    "RANKED_WITH_WARNINGS requires warnings"
                )

        if status == "NO_ELIGIBLE_CONTRACTS":
            if ranked_candidates:
                raise ValueError(
                    "NO_ELIGIBLE_CONTRACTS cannot contain "
                    "ranked candidates"
                )

            if not rejected_candidates:
                raise ValueError(
                    "NO_ELIGIBLE_CONTRACTS requires "
                    "rejected candidates"
                )

        if status in {
            "BLOCKED",
            "INSUFFICIENT_DATA",
            "FAILED",
        }:
            if ranked_candidates:
                raise ValueError(
                    f"{status} cannot contain ranked candidates"
                )

            if not blockers:
                raise ValueError(
                    f"{status} requires blockers"
                )

        if successful_status and option_type is None:
            raise ValueError(
                "successful directional ranking requires "
                "an option type"
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
    def selected_candidate(
        self,
    ) -> OptionContractCandidateV1 | None:
        if not self.ranked_candidates:
            return None

        return self.ranked_candidates[0]

    @property
    def eligible_candidate_count(self) -> int:
        return len(self.ranked_candidates)

    @property
    def rejected_candidate_count(self) -> int:
        return len(self.rejected_candidates)

    def to_dict(self) -> dict[str, object]:
        selected = self.selected_candidate

        return {
            "schema_version": self.schema_version,
            "ranking_id": self.ranking_id,
            "ranked_at": self.ranked_at.isoformat(),
            "universe_id": self.universe_id,
            "intelligence_result_id": (
                self.intelligence_result_id
            ),
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "directional_bias": self.directional_bias,
            "required_option_type": (
                self.required_option_type
            ),
            "ranking_status": self.ranking_status,
            "selected_contract_id": (
                selected.contract.contract_id
                if selected is not None
                else None
            ),
            "ranked_candidates": [
                candidate.to_dict()
                for candidate in self.ranked_candidates
            ],
            "rejected_candidates": [
                candidate.to_dict()
                for candidate in self.rejected_candidates
            ],
            "eligible_candidate_count": (
                self.eligible_candidate_count
            ),
            "rejected_candidate_count": (
                self.rejected_candidate_count
            ),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "diagnostics": list(self.diagnostics),
            "metadata": dict(self.metadata),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def semantic_dict(self) -> dict[str, object]:
        result = self.to_dict()
        result.pop("ranking_id")
        result.pop("ranked_at")
        return result