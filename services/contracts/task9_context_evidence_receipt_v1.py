"""Durable references to canonical broader/external evidence used by Task 9."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from services.contracts.broader_market_intelligence_result_v1 import (
    BroaderMarketIntelligenceResultV1,
)
from services.contracts.external_market_context_result_v1 import (
    ExternalMarketContextResultV1,
)


_MARKETS = {
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
}

_BROADER_STATUSES = {
    "READY",
    "READY_WITH_WARNINGS",
    "INSUFFICIENT_DATA",
    "STALE",
    "UNAVAILABLE",
    "BLOCKED",
    "CONFLICTING",
}

_EXTERNAL_STATUSES = {
    "READY",
    "READY_WITH_WARNINGS",
    "CONFLICTING",
    "UNAVAILABLE",
    "BLOCKED",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip()


def _optional_text(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _timestamps(
    value: Mapping[str, datetime],
) -> Mapping[str, datetime]:
    if not isinstance(value, Mapping):
        raise TypeError("source_timestamps")

    result: dict[str, datetime] = {}

    for key, timestamp in value.items():
        normalized_key = _text(
            key,
            "source_timestamps key",
        )

        result[normalized_key] = _aware(
            timestamp,
            "source_timestamps value",
        )

    return MappingProxyType(
        dict(sorted(result.items()))
    )


@dataclass(frozen=True, slots=True)
class Task9ContextEvidenceReceiptV1:
    receipt_id: str
    official_run_id: str
    parent_cycle_id: str
    prediction_id: str
    observation_id: str

    underlying_symbol: str
    exchange: str
    evaluated_at: datetime

    broader_market_present: bool
    broader_market_result_id: str | None
    broader_market_status: str

    external_context_present: bool
    external_context_result_id: str | None
    external_context_status: str

    source_timestamps: Mapping[str, datetime] = field(
        default_factory=dict
    )

    external_provider_snapshot_id: str | None = None
    provenance: tuple[str, ...] = (
        "TASK9_RETAINED_CANONICAL_EVIDENCE",
    )

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = (
        "task9_context_evidence_receipt.v1"
    )

    def __post_init__(self) -> None:
        for name in (
            "receipt_id",
            "official_run_id",
            "parent_cycle_id",
            "prediction_id",
            "observation_id",
            "underlying_symbol",
            "exchange",
        ):
            object.__setattr__(
                self,
                name,
                _text(
                    getattr(self, name),
                    name,
                ),
            )

        identity = (
            self.underlying_symbol,
            self.exchange,
        )

        if identity not in _MARKETS:
            raise ValueError("market identity")

        _aware(
            self.evaluated_at,
            "evaluated_at",
        )

        if type(self.broader_market_present) is not bool:
            raise TypeError(
                "broader_market_present"
            )

        if type(self.external_context_present) is not bool:
            raise TypeError(
                "external_context_present"
            )

        object.__setattr__(
            self,
            "broader_market_result_id",
            _optional_text(
                self.broader_market_result_id,
                "broader_market_result_id",
            ),
        )

        object.__setattr__(
            self,
            "external_context_result_id",
            _optional_text(
                self.external_context_result_id,
                "external_context_result_id",
            ),
        )

        broader_status = _text(
            self.broader_market_status,
            "broader_market_status",
        ).upper()

        external_status = _text(
            self.external_context_status,
            "external_context_status",
        ).upper()

        if broader_status not in _BROADER_STATUSES:
            raise ValueError(
                "broader_market_status"
            )

        if external_status not in _EXTERNAL_STATUSES:
            raise ValueError(
                "external_context_status"
            )

        object.__setattr__(
            self,
            "broader_market_status",
            broader_status,
        )

        object.__setattr__(
            self,
            "external_context_status",
            external_status,
        )

        if self.broader_market_present:
            if self.broader_market_result_id is None:
                raise ValueError(
                    "present broader market requires result id"
                )
        else:
            if (
                self.broader_market_result_id is not None
                or self.broader_market_status
                != "UNAVAILABLE"
            ):
                raise ValueError(
                    "missing broader market must be explicit unavailable"
                )

        if self.external_context_present:
            if self.external_context_result_id is None:
                raise ValueError(
                    "present external context requires result id"
                )
        else:
            if (
                self.external_context_result_id is not None
                or self.external_context_status
                != "UNAVAILABLE"
            ):
                raise ValueError(
                    "missing external context must be explicit unavailable"
                )

        object.__setattr__(
            self,
            "source_timestamps",
            _timestamps(
                self.source_timestamps
            ),
        )

        object.__setattr__(
            self,
            "external_provider_snapshot_id",
            _optional_text(
                self.external_provider_snapshot_id,
                "external_provider_snapshot_id",
            ),
        )

        if (
            not isinstance(self.provenance, tuple)
            or not self.provenance
        ):
            raise TypeError("provenance")

        provenance = tuple(
            _text(item, "provenance item")
            for item in self.provenance
        )

        if len(provenance) != len(set(provenance)):
            raise ValueError("provenance")

        object.__setattr__(
            self,
            "provenance",
            provenance,
        )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 context evidence must remain PAPER-only"
            )

        if (
            self.schema_version
            != "task9_context_evidence_receipt.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "official_run_id": self.official_run_id,
            "parent_cycle_id": self.parent_cycle_id,
            "prediction_id": self.prediction_id,
            "observation_id": self.observation_id,
            "underlying_symbol": self.underlying_symbol,
            "exchange": self.exchange,
            "evaluated_at": (
                self.evaluated_at.isoformat()
            ),
            "broader_market_present": (
                self.broader_market_present
            ),
            "broader_market_result_id": (
                self.broader_market_result_id
            ),
            "broader_market_status": (
                self.broader_market_status
            ),
            "external_context_present": (
                self.external_context_present
            ),
            "external_context_result_id": (
                self.external_context_result_id
            ),
            "external_context_status": (
                self.external_context_status
            ),
            "source_timestamps": {
                key: value.isoformat()
                for key, value
                in self.source_timestamps.items()
            },
            "external_provider_snapshot_id": (
                self.external_provider_snapshot_id
            ),
            "provenance": list(
                self.provenance
            ),
            "execution_mode": (
                self.execution_mode
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }


def task9_context_evidence_receipt_from_dict(
    value: Mapping[str, object],
) -> Task9ContextEvidenceReceiptV1:
    if not isinstance(value, Mapping):
        raise TypeError("context evidence receipt")

    timestamps_raw = value.get(
        "source_timestamps"
    )

    if not isinstance(
        timestamps_raw,
        Mapping,
    ):
        raise ValueError(
            "source_timestamps"
        )

    timestamps = {
        str(key): datetime.fromisoformat(
            str(timestamp)
        )
        for key, timestamp
        in timestamps_raw.items()
    }

    provenance_raw = value.get(
        "provenance"
    )

    if not isinstance(
        provenance_raw,
        list,
    ):
        raise ValueError("provenance")

    return Task9ContextEvidenceReceiptV1(
        receipt_id=value.get("receipt_id"),
        official_run_id=value.get(
            "official_run_id"
        ),
        parent_cycle_id=value.get(
            "parent_cycle_id"
        ),
        prediction_id=value.get(
            "prediction_id"
        ),
        observation_id=value.get(
            "observation_id"
        ),
        underlying_symbol=value.get(
            "underlying_symbol"
        ),
        exchange=value.get("exchange"),
        evaluated_at=datetime.fromisoformat(
            str(value.get("evaluated_at"))
        ),
        broader_market_present=value.get(
            "broader_market_present"
        ),
        broader_market_result_id=value.get(
            "broader_market_result_id"
        ),
        broader_market_status=value.get(
            "broader_market_status"
        ),
        external_context_present=value.get(
            "external_context_present"
        ),
        external_context_result_id=value.get(
            "external_context_result_id"
        ),
        external_context_status=value.get(
            "external_context_status"
        ),
        source_timestamps=timestamps,
        external_provider_snapshot_id=value.get(
            "external_provider_snapshot_id"
        ),
        provenance=tuple(
            provenance_raw
        ),
        execution_mode=value.get(
            "execution_mode"
        ),
        broker_order_submission=value.get(
            "broker_order_submission"
        ),
        live_execution_eligible=value.get(
            "live_execution_eligible"
        ),
        schema_version=value.get(
            "schema_version"
        ),
    )


def build_task9_context_evidence_receipt(
    *,
    receipt_id: str,
    official_run_id: str,
    parent_cycle_id: str,
    prediction_id: str,
    observation_id: str,
    underlying_symbol: str,
    exchange: str,
    evaluated_at: datetime,
    broader_market: (
        BroaderMarketIntelligenceResultV1
        | None
    ),
    external_context: (
        ExternalMarketContextResultV1
        | None
    ),
    external_provider_snapshot_id: (
        str | None
    ) = None,
) -> Task9ContextEvidenceReceiptV1:
    identity = (
        underlying_symbol,
        exchange,
    )

    if broader_market is not None:
        if (
            type(broader_market)
            is not BroaderMarketIntelligenceResultV1
            or (
                broader_market.underlying_symbol,
                broader_market.exchange,
            )
            != identity
        ):
            raise ValueError(
                "broader market identity"
            )

    if external_context is not None:
        if (
            type(external_context)
            is not ExternalMarketContextResultV1
            or (
                external_context.underlying_symbol,
                external_context.exchange,
            )
            != identity
        ):
            raise ValueError(
                "external context identity"
            )

    timestamps: dict[str, datetime] = {}

    if broader_market is not None:
        timestamps.update(
            {
                f"BROADER:{key}": value
                for key, value
                in broader_market.source_timestamps.items()
            }
        )

    if external_context is not None:
        timestamps.update(
            {
                f"EXTERNAL:{key}": value
                for key, value
                in external_context.source_timestamps.items()
            }
        )

    return Task9ContextEvidenceReceiptV1(
        receipt_id=receipt_id,
        official_run_id=official_run_id,
        parent_cycle_id=parent_cycle_id,
        prediction_id=prediction_id,
        observation_id=observation_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        evaluated_at=evaluated_at,
        broader_market_present=(
            broader_market is not None
        ),
        broader_market_result_id=(
            None
            if broader_market is None
            else broader_market
            .broader_market_intelligence_result_id
        ),
        broader_market_status=(
            "UNAVAILABLE"
            if broader_market is None
            else broader_market.intelligence_status
        ),
        external_context_present=(
            external_context is not None
        ),
        external_context_result_id=(
            None
            if external_context is None
            else external_context
            .external_market_context_result_id
        ),
        external_context_status=(
            "UNAVAILABLE"
            if external_context is None
            else external_context.context_status
        ),
        source_timestamps=timestamps,
        external_provider_snapshot_id=(
            external_provider_snapshot_id
        ),
    )


__all__ = (
    "Task9ContextEvidenceReceiptV1",
    "build_task9_context_evidence_receipt",
    "task9_context_evidence_receipt_from_dict",
)
