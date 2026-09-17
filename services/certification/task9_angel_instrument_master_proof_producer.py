"""Task 9 Angel instrument-master proof production.

This authority performs no network acquisition.

It converts one already-fetched Angel instrument-master snapshot plus
its validated provenance metadata into the immutable Task 9 startup
proof contract.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from services.contracts.task9_angel_instrument_master_proof_v1 import (
    Task9AngelInstrumentMasterProbeStatus,
    Task9AngelInstrumentMasterProofV1,
)


_SOURCE_REF = "angel-openapi-scrip-master"


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


def _corrupt(
    *,
    observed_at: datetime,
    fetched_at: datetime | None,
    record_count: int | None,
    nifty: bool,
    sensex: bool,
    reason: str,
) -> Task9AngelInstrumentMasterProofV1:
    stamp = observed_at.isoformat()

    return Task9AngelInstrumentMasterProofV1(
        proof_id=(
            "task9-angel-instrument-master:"
            f"corrupt:{stamp}"
        ),
        observed_at=observed_at,
        status=(
            Task9AngelInstrumentMasterProbeStatus.CORRUPT
        ),
        fetched_at=fetched_at,
        record_count=record_count,
        nifty_nfo_identity_present=nifty,
        sensex_bfo_identity_present=sensex,
        source_ref=_SOURCE_REF,
        incident_ref=None,
        sanitized_reason=reason,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


def _identity_present(
    records: Sequence[Mapping[str, object]],
    *,
    underlying: str,
    exchange: str,
) -> bool:
    for record in records:
        if (
            str(
                record.get(
                    "name",
                    "",
                )
            ).strip().upper()
            == underlying
            and str(
                record.get(
                    "exch_seg",
                    "",
                )
            ).strip().upper()
            == exchange
            and str(
                record.get(
                    "instrumenttype",
                    "",
                )
            ).strip().upper()
            == "OPTIDX"
        ):
            return True

    return False


def produce_task9_angel_instrument_master_proof(
    *,
    records: Sequence[Mapping[str, object]],
    metadata: Mapping[str, object],
    observed_at: datetime,
) -> Task9AngelInstrumentMasterProofV1:
    """Produce Task 9 proof from one retained master acquisition."""

    observed_at = _aware(
        observed_at,
        "observed_at",
    )

    if (
        isinstance(records, (str, bytes))
        or not isinstance(records, Sequence)
    ):
        raise TypeError("records")

    if not isinstance(metadata, Mapping):
        raise TypeError("metadata")

    normalized_records = []

    for record in records:
        if not isinstance(record, Mapping):
            raise TypeError(
                "instrument master record"
            )

        normalized_records.append(record)

    record_count = len(
        normalized_records
    )

    nifty = _identity_present(
        normalized_records,
        underlying="NIFTY",
        exchange="NFO",
    )

    sensex = _identity_present(
        normalized_records,
        underlying="SENSEX",
        exchange="BFO",
    )

    if metadata.get("validated") is not True:
        return _corrupt(
            observed_at=observed_at,
            fetched_at=None,
            record_count=record_count,
            nifty=nifty,
            sensex=sensex,
            reason=(
                "INSTRUMENT_MASTER_METADATA_NOT_VALIDATED"
            ),
        )

    raw_count = metadata.get(
        "record_count"
    )

    if (
        type(raw_count) is not int
        or isinstance(raw_count, bool)
        or raw_count <= 0
        or raw_count != record_count
    ):
        return _corrupt(
            observed_at=observed_at,
            fetched_at=None,
            record_count=record_count,
            nifty=nifty,
            sensex=sensex,
            reason=(
                "INSTRUMENT_MASTER_RECORD_COUNT_MISMATCH"
            ),
        )

    raw_fetched_at = metadata.get(
        "fetched_at_epoch_seconds"
    )

    if (
        isinstance(raw_fetched_at, bool)
        or not isinstance(
            raw_fetched_at,
            (int, float),
        )
        or not math.isfinite(
            float(raw_fetched_at)
        )
    ):
        return _corrupt(
            observed_at=observed_at,
            fetched_at=None,
            record_count=record_count,
            nifty=nifty,
            sensex=sensex,
            reason=(
                "INSTRUMENT_MASTER_FETCH_TIMESTAMP_INVALID"
            ),
        )

    fetched_at = datetime.fromtimestamp(
        float(raw_fetched_at),
        tz=timezone.utc,
    )

    if fetched_at > observed_at:
        return _corrupt(
            observed_at=observed_at,
            fetched_at=None,
            record_count=record_count,
            nifty=nifty,
            sensex=sensex,
            reason=(
                "INSTRUMENT_MASTER_FETCH_TIMESTAMP_FUTURE"
            ),
        )

    return Task9AngelInstrumentMasterProofV1(
        proof_id=(
            "task9-angel-instrument-master:"
            f"{fetched_at.isoformat()}:"
            f"{record_count}"
        ),
        observed_at=observed_at,
        status=(
            Task9AngelInstrumentMasterProbeStatus.AVAILABLE
        ),
        fetched_at=fetched_at,
        record_count=record_count,
        nifty_nfo_identity_present=nifty,
        sensex_bfo_identity_present=sensex,
        source_ref=_SOURCE_REF,
        incident_ref=None,
        sanitized_reason=None,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "produce_task9_angel_instrument_master_proof",
)
