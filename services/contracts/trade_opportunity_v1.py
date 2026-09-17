"""Canonical paper-only trade-opportunity integration contract."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, ClassVar, Mapping

from services.core.market_identity import (
    SUPPORTED_MARKET_IDENTITIES,
)


_ALLOWED_STATUSES = frozenset(
    {
        "READY",
        "READY_WITH_WARNINGS",
        "NO_ACTION",
        "BLOCKED",
        "INSUFFICIENT_DATA",
        "CONFLICTING",
        "FAILED",
    }
)

_ALLOWED_ACTIONS = frozenset(
    {
        "BUY",
        "SELL",
        "WAIT",
        "HOLD",
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


def _require_optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _require_text(value, field_name)


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
            f"{field_name} item",
        ).upper()

        if text in normalized:
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

        normalized.append(text)

    return tuple(normalized)


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


def _require_optional_positive_float(
    value: object,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise TypeError(f"{field_name} must be numeric or None")

    normalized = float(value)

    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    if normalized <= 0.0:
        raise ValueError(
            f"{field_name} must be greater than zero"
        )

    return normalized


def _require_optional_positive_int(
    value: object,
    field_name: str,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"{field_name} must be an integer or None"
        )

    if value <= 0:
        raise ValueError(
            f"{field_name} must be greater than zero"
        )

    return value


@dataclass(frozen=True, slots=True)
class TradeOpportunityV1:
    """Integrated evidence for one paper-only trade opportunity."""

    opportunity_id: str
    created_at: datetime

    snapshot_id: str
    decision_id: str
    technical_intelligence_result_id: str
    option_chain_intelligence_result_id: str
    option_contract_ranking_id: str
    session_validation_id: str

    underlying_symbol: str
    exchange: str
    expiry: date | None

    action: str
    directional_bias: str
    option_type: str | None

    contract_id: str | None
    trading_symbol: str | None
    instrument_token: str | None
    strike: float | None
    lot_size: int | None
    reference_option_price: float | None

    technical_strength: float
    option_chain_strength: float
    contract_ranking_score: float
    decision_confidence: float
    opportunity_score: float

    opportunity_status: str

    supporting_evidence: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    schema_version: ClassVar[str] = "trade_opportunity.v1"
    execution_mode: ClassVar[str] = "PAPER"
    live_execution_eligible: ClassVar[bool] = False

    def __post_init__(self) -> None:
        for field_name in (
            "opportunity_id",
            "snapshot_id",
            "decision_id",
            "technical_intelligence_result_id",
            "option_chain_intelligence_result_id",
            "option_contract_ranking_id",
            "session_validation_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_text(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if not isinstance(self.created_at, datetime):
            raise TypeError(
                "created_at must be a datetime"
            )

        if (
            self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise ValueError(
                "created_at must be timezone-aware"
            )

        identity = (
            self.underlying_symbol,
            self.exchange,
        )

        if identity not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError(
                "unsupported market identity"
            )

        if (
            self.expiry is not None
            and (
                isinstance(self.expiry, datetime)
                or not isinstance(self.expiry, date)
            )
        ):
            raise TypeError(
                "expiry must be a date or None"
            )

        action = _require_text(
            self.action,
            "action",
        ).upper()

        if action not in _ALLOWED_ACTIONS:
            raise ValueError(
                f"unsupported action: {action}"
            )

        object.__setattr__(self, "action", action)

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

        option_type = self.option_type

        if option_type is not None:
            option_type = _require_text(
                option_type,
                "option_type",
            ).upper()

            if option_type not in _ALLOWED_OPTION_TYPES:
                raise ValueError(
                    "option_type must be CALL, PUT, or None"
                )

            object.__setattr__(
                self,
                "option_type",
                option_type,
            )

        expected_bias = (
            "BULLISH"
            if action == "BUY"
            else "BEARISH"
            if action == "SELL"
            else None
        )
        expected_option_type = (
            "CALL"
            if action == "BUY"
            else "PUT"
            if action == "SELL"
            else None
        )

        if expected_bias is not None and bias != expected_bias:
            raise ValueError(
                "directional_bias does not match action"
            )

        if option_type != expected_option_type:
            raise ValueError(
                "option_type does not match action"
            )

        for field_name in (
            "contract_id",
            "trading_symbol",
            "instrument_token",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_optional_text(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "strike",
            _require_optional_positive_float(
                self.strike,
                "strike",
            ),
        )
        object.__setattr__(
            self,
            "reference_option_price",
            _require_optional_positive_float(
                self.reference_option_price,
                "reference_option_price",
            ),
        )
        object.__setattr__(
            self,
            "lot_size",
            _require_optional_positive_int(
                self.lot_size,
                "lot_size",
            ),
        )

        for field_name in (
            "technical_strength",
            "option_chain_strength",
            "contract_ranking_score",
            "decision_confidence",
            "opportunity_score",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_unit_score(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        status = _require_text(
            self.opportunity_status,
            "opportunity_status",
        ).upper()

        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"unsupported opportunity_status: {status}"
            )

        object.__setattr__(
            self,
            "opportunity_status",
            status,
        )

        supporting_evidence = _require_string_tuple(
            self.supporting_evidence,
            "supporting_evidence",
        )
        contradictions = _require_string_tuple(
            self.contradictions,
            "contradictions",
        )
        blockers = _require_string_tuple(
            self.blockers,
            "blockers",
        )
        warnings = _require_string_tuple(
            self.warnings,
            "warnings",
        )

        object.__setattr__(
            self,
            "supporting_evidence",
            supporting_evidence,
        )
        object.__setattr__(
            self,
            "contradictions",
            contradictions,
        )
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "warnings", warnings)

        ready = status in {
            "READY",
            "READY_WITH_WARNINGS",
        }

        contract_identity = (
            self.contract_id,
            self.trading_symbol,
            self.strike,
            self.lot_size,
            self.expiry,
        )

        if ready:
            if action not in {"BUY", "SELL"}:
                raise ValueError(
                    "ready opportunity requires BUY or SELL"
                )

            if blockers:
                raise ValueError(
                    "ready opportunity cannot contain blockers"
                )

            if not all(
                value is not None
                for value in contract_identity
            ):
                raise ValueError(
                    "ready opportunity requires complete "
                    "contract identity"
                )

            if status == "READY" and warnings:
                raise ValueError(
                    "READY cannot contain warnings"
                )

            if (
                status == "READY_WITH_WARNINGS"
                and not warnings
            ):
                raise ValueError(
                    "READY_WITH_WARNINGS requires warnings"
                )

        else:
            if any(
                value is not None
                for value in contract_identity
            ) and not all(
                value is not None
                for value in contract_identity
            ):
                raise ValueError(
                    "non-ready opportunity cannot contain "
                    "partial contract identity"
                )

        if status in {
            "BLOCKED",
            "INSUFFICIENT_DATA",
            "CONFLICTING",
            "FAILED",
        } and not blockers:
            raise ValueError(
                f"{status} requires blockers"
            )

        if status == "NO_ACTION":
            if action not in {"WAIT", "HOLD"}:
                raise ValueError(
                    "NO_ACTION requires WAIT or HOLD"
                )

            if blockers:
                raise ValueError(
                    "NO_ACTION cannot contain blockers"
                )

            if option_type is not None:
                raise ValueError(
                    "NO_ACTION cannot contain option type"
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
    def opportunity_ready(self) -> bool:
        return self.opportunity_status in {
            "READY",
            "READY_WITH_WARNINGS",
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "opportunity_id": self.opportunity_id,
            "created_at": self.created_at.isoformat(),
            "snapshot_id": self.snapshot_id,
            "decision_id": self.decision_id,
            "technical_intelligence_result_id": (
                self.technical_intelligence_result_id
            ),
            "option_chain_intelligence_result_id": (
                self.option_chain_intelligence_result_id
            ),
            "option_contract_ranking_id": (
                self.option_contract_ranking_id
            ),
            "session_validation_id": (
                self.session_validation_id
            ),
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "expiry": (
                self.expiry.isoformat()
                if self.expiry is not None
                else None
            ),
            "action": self.action,
            "directional_bias": self.directional_bias,
            "option_type": self.option_type,
            "contract_id": self.contract_id,
            "trading_symbol": self.trading_symbol,
            "instrument_token": self.instrument_token,
            "strike": self.strike,
            "lot_size": self.lot_size,
            "reference_option_price": (
                self.reference_option_price
            ),
            "technical_strength": self.technical_strength,
            "option_chain_strength": (
                self.option_chain_strength
            ),
            "contract_ranking_score": (
                self.contract_ranking_score
            ),
            "decision_confidence": (
                self.decision_confidence
            ),
            "opportunity_score": self.opportunity_score,
            "opportunity_status": self.opportunity_status,
            "opportunity_ready": self.opportunity_ready,
            "supporting_evidence": list(
                self.supporting_evidence
            ),
            "contradictions": list(
                self.contradictions
            ),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
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
        result.pop("opportunity_id")
        result.pop("created_at")
        return result