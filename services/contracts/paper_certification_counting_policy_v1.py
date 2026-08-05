"""Versioned PAPER certification counting policy."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import ClassVar


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


@dataclass(frozen=True, slots=True)
class PaperCertificationCountingPolicyV1:
    """Immutable rules for official prediction certification counting."""

    SCHEMA_VERSION: ClassVar[str] = (
        "paper_certification_counting_policy.v1"
    )

    policy_id: str
    policy_version: str
    accepted_system_version: str
    accepted_provider_version: str
    require_live_real_time_source: bool = True
    require_real_time_market_session: bool = True
    require_valid_evidence: bool = True
    require_completed_outcome: bool = True
    include_wait: bool = True
    include_no_trade: bool = True
    exclude_data_incidents: bool = True
    counter_reset_allowed: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "policy_id",
            "policy_version",
            "accepted_system_version",
            "accepted_provider_version",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        for name in (
            "require_live_real_time_source",
            "require_real_time_market_session",
            "require_valid_evidence",
            "require_completed_outcome",
            "include_wait",
            "include_no_trade",
            "exclude_data_incidents",
            "counter_reset_allowed",
            "live_execution_eligible",
            "broker_order_submission",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if self.require_live_real_time_source is not True:
            raise ValueError(
                "official counting requires live real-time source"
            )
        if self.require_real_time_market_session is not True:
            raise ValueError(
                "official counting requires real-time market session"
            )
        if self.require_valid_evidence is not True:
            raise ValueError(
                "official counting requires valid evidence"
            )
        if self.require_completed_outcome is not True:
            raise ValueError(
                "official counting requires completed outcome"
            )
        if self.include_wait is not True:
            raise ValueError(
                "official counting must include WAIT"
            )
        if self.include_no_trade is not True:
            raise ValueError(
                "official counting must include NO_TRADE"
            )
        if self.exclude_data_incidents is not True:
            raise ValueError(
                "official counting must exclude data incidents"
            )
        if self.counter_reset_allowed is not False:
            raise ValueError(
                "official counters cannot be reset"
            )
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only certification counting policy"
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
