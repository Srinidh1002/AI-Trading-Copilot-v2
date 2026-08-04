"""Versioned India VIX previous-close source policy."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import ClassVar, Mapping


@dataclass(frozen=True, slots=True)
class IndiaVixPreviousClosePolicyV1:
    """Authoritative provider-field policy for India VIX previous close."""

    SCHEMA_VERSION: ClassVar[str] = "india_vix_previous_close_policy.v1"

    policy_id: str = "INDIA_VIX_PREVIOUS_CLOSE_POLICY_2026_08_03"
    effective_from: date = date(2026, 8, 3)
    primary_provider_field: str = "close"
    permitted_fallback_fields: tuple[str, ...] = ()
    require_provider_issued_timestamp: bool = True
    maximum_quote_age_seconds: float = 300.0
    maximum_future_skew_seconds: float = 5.0
    execution_modes: tuple[str, ...] = ("PAPER", "MANUAL_LIVE")

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ValueError("policy_id")
        if type(self.effective_from) is not date:
            raise TypeError("effective_from")
        if self.primary_provider_field != "close":
            raise ValueError("primary_provider_field")
        if type(self.permitted_fallback_fields) is not tuple:
            raise TypeError("permitted_fallback_fields")
        if self.permitted_fallback_fields:
            raise ValueError("fallback fields are not certified")
        if type(self.require_provider_issued_timestamp) is not bool:
            raise TypeError("require_provider_issued_timestamp")
        if self.require_provider_issued_timestamp is not True:
            raise ValueError("provider timestamp is required")
        for name in (
            "maximum_quote_age_seconds",
            "maximum_future_skew_seconds",
        ):
            value = getattr(self, name)
            if (
                type(value) not in (int, float)
                or isinstance(value, bool)
                or float(value) < 0.0
            ):
                raise ValueError(name)
            object.__setattr__(self, name, float(value))
        if self.maximum_quote_age_seconds != 300.0:
            raise ValueError("maximum_quote_age_seconds")
        if self.maximum_future_skew_seconds != 5.0:
            raise ValueError("maximum_future_skew_seconds")
        if self.execution_modes != ("PAPER", "MANUAL_LIVE"):
            raise ValueError("execution_modes")

    def resolve(
        self,
        provider_row: Mapping[str, object],
    ) -> tuple[float | None, str | None, tuple[str, ...]]:
        if not isinstance(provider_row, Mapping):
            raise TypeError("provider_row")

        value = provider_row.get(self.primary_provider_field)
        if (
            isinstance(value, bool)
            or type(value) not in (int, float)
            or float(value) <= 0.0
        ):
            return (
                None,
                None,
                ("INDIA_VIX_PREVIOUS_CLOSE_UNAVAILABLE",),
            )

        return (
            float(value),
            self.primary_provider_field,
            (),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "effective_from": self.effective_from.isoformat(),
            "primary_provider_field": self.primary_provider_field,
            "permitted_fallback_fields": list(
                self.permitted_fallback_fields
            ),
            "require_provider_issued_timestamp": (
                self.require_provider_issued_timestamp
            ),
            "maximum_quote_age_seconds": (
                self.maximum_quote_age_seconds
            ),
            "maximum_future_skew_seconds": (
                self.maximum_future_skew_seconds
            ),
            "execution_modes": list(self.execution_modes),
            "schema_version": self.SCHEMA_VERSION,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )


DEFAULT_INDIA_VIX_PREVIOUS_CLOSE_POLICY = (
    IndiaVixPreviousClosePolicyV1()
)
