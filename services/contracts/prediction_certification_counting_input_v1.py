"""Immutable input for one certification-counting decision."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from services.contracts.prediction_outcome_record_v1 import (
    PredictionOutcomeRecordV1,
)
from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)


_SOURCE_KINDS = {
    "LIVE_REAL_TIME",
    "REPLAY",
    "BACKTEST",
    "DIAGNOSTIC",
    "FIXTURE",
    "DEVELOPMENT",
}
_SESSION_STATUSES = {
    "REAL_TIME_MARKET_SESSION",
    "OUT_OF_SESSION",
    "UNKNOWN",
}
_EVIDENCE_STATUSES = {
    "VALID",
    "INVALID",
    "DATA_INCIDENT",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
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


def _messages(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    return tuple(
        dict.fromkeys(
            _text(item, name)
            for item in value
        )
    )


@dataclass(frozen=True, slots=True)
class PredictionCertificationCountingInputV1:
    """Supplied provenance required to classify one prediction."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_certification_counting_input.v1"
    )

    prediction: PredictionRecordV1
    outcome: PredictionOutcomeRecordV1 | None
    record_source: str
    session_status: str
    evidence_status: str
    record_run_id: str
    official_run_id: str
    official_start_at: datetime
    observed_system_version: str
    observed_policy_version: str
    observed_provider_version: str
    evaluated_at: datetime
    data_incident_codes: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.prediction) is not PredictionRecordV1:
            raise TypeError("prediction")
        if (
            self.outcome is not None
            and type(self.outcome)
            is not PredictionOutcomeRecordV1
        ):
            raise TypeError("outcome")

        source = _text(
            self.record_source,
            "record_source",
        ).upper()
        session = _text(
            self.session_status,
            "session_status",
        ).upper()
        evidence = _text(
            self.evidence_status,
            "evidence_status",
        ).upper()

        if source not in _SOURCE_KINDS:
            raise ValueError("record_source")
        if session not in _SESSION_STATUSES:
            raise ValueError("session_status")
        if evidence not in _EVIDENCE_STATUSES:
            raise ValueError("evidence_status")

        object.__setattr__(self, "record_source", source)
        object.__setattr__(self, "session_status", session)
        object.__setattr__(self, "evidence_status", evidence)

        for name in (
            "record_run_id",
            "official_run_id",
            "observed_system_version",
            "observed_policy_version",
            "observed_provider_version",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        start = _aware(
            self.official_start_at,
            "official_start_at",
        )
        evaluated = _aware(
            self.evaluated_at,
            "evaluated_at",
        )
        if evaluated < self.prediction.completed_at:
            raise ValueError(
                "evaluated_at cannot precede prediction completion"
            )

        object.__setattr__(
            self,
            "official_start_at",
            start,
        )
        object.__setattr__(
            self,
            "evaluated_at",
            evaluated,
        )
        object.__setattr__(
            self,
            "data_incident_codes",
            _messages(
                self.data_incident_codes,
                "data_incident_codes",
            ),
        )

        if (
            evidence == "DATA_INCIDENT"
            and not self.data_incident_codes
        ):
            raise ValueError(
                "DATA_INCIDENT requires incident code"
            )
        if (
            evidence != "DATA_INCIDENT"
            and self.data_incident_codes
        ):
            raise ValueError(
                "incident codes require DATA_INCIDENT"
            )

        if self.outcome is not None:
            if (
                self.outcome.prediction_id
                != self.prediction.prediction_id
                or self.outcome.parent_cycle_id
                != self.prediction.parent_cycle_id
                or self.outcome.underlying_symbol
                != self.prediction.underlying_symbol
                or self.outcome.exchange
                != self.prediction.exchange
                or self.outcome.predicted_action
                != self.prediction.predicted_action
            ):
                raise ValueError(
                    "prediction/outcome identity mismatch"
                )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only certification counting input"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "prediction": self.prediction.to_dict(),
            "outcome": (
                self.outcome.to_dict()
                if self.outcome is not None
                else None
            ),
            "record_source": self.record_source,
            "session_status": self.session_status,
            "evidence_status": self.evidence_status,
            "record_run_id": self.record_run_id,
            "official_run_id": self.official_run_id,
            "official_start_at": self.official_start_at.isoformat(),
            "observed_system_version": (
                self.observed_system_version
            ),
            "observed_policy_version": (
                self.observed_policy_version
            ),
            "observed_provider_version": (
                self.observed_provider_version
            ),
            "evaluated_at": self.evaluated_at.isoformat(),
            "data_incident_codes": list(
                self.data_incident_codes
            ),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
