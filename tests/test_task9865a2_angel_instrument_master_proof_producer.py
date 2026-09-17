from datetime import datetime, timedelta, timezone
import inspect

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_instrument_master_proof_producer import (
    produce_task9_angel_instrument_master_proof,
)
from services.certification.task9_angel_instrument_master_readiness import (
    Task9AngelInstrumentMasterReadinessStatus,
    evaluate_task9_angel_instrument_master,
)
from services.contracts.task9_angel_instrument_master_proof_v1 import (
    Task9AngelInstrumentMasterProbeStatus,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


NOW = datetime(
    2026,
    8,
    17,
    5,
    10,
    tzinfo=timezone.utc,
)


def _records(
    *,
    nifty=True,
    sensex=True,
):
    values = [
        {
            "name": "OTHER",
            "exch_seg": "NFO",
            "instrumenttype": "OPTSTK",
            "token": "1",
        },
    ]

    if nifty:
        values.append(
            {
                "name": "NIFTY",
                "exch_seg": "NFO",
                "instrumenttype": "OPTIDX",
                "symbol": "NIFTY27AUG2624500CE",
                "token": "1001",
            }
        )

    if sensex:
        values.append(
            {
                "name": "SENSEX",
                "exch_seg": "BFO",
                "instrumenttype": "OPTIDX",
                "symbol": "SENSEX27AUG2678500CE",
                "token": "2001",
            }
        )

    return values


def _metadata(
    records,
    *,
    validated=True,
    fetched_at=None,
    record_count=None,
):
    fetched_at = (
        NOW - timedelta(seconds=10)
        if fetched_at is None
        else fetched_at
    )

    return {
        "source": "angel-one-instrument-master",
        "source_url": "provider-master-endpoint",
        "fetched_at_epoch_seconds": (
            fetched_at.timestamp()
        ),
        "record_count": (
            len(records)
            if record_count is None
            else record_count
        ),
        "validated": validated,
    }


def test_available_master_proof_maps_retained_snapshot():
    records = _records()

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(records),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.AVAILABLE
    )
    assert proof.record_count == len(records)
    assert (
        proof.fetched_at
        == NOW - timedelta(seconds=10)
    )
    assert (
        proof.nifty_nfo_identity_present
        is True
    )
    assert (
        proof.sensex_bfo_identity_present
        is True
    )


def test_identity_presence_comes_from_actual_records():
    records = _records(
        nifty=False,
        sensex=True,
    )

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(records),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.AVAILABLE
    )
    assert (
        proof.nifty_nfo_identity_present
        is False
    )
    assert (
        proof.sensex_bfo_identity_present
        is True
    )


def test_wrong_instrument_type_does_not_prove_identity():
    records = [
        {
            "name": "NIFTY",
            "exch_seg": "NFO",
            "instrumenttype": "FUTIDX",
        },
        {
            "name": "SENSEX",
            "exch_seg": "BFO",
            "instrumenttype": "OPTIDX",
        },
    ]

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(records),
            observed_at=NOW,
        )
    )

    assert (
        proof.nifty_nfo_identity_present
        is False
    )
    assert (
        proof.sensex_bfo_identity_present
        is True
    )


def test_unvalidated_metadata_becomes_corrupt_proof():
    records = _records()

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(
                records,
                validated=False,
            ),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.CORRUPT
    )
    assert proof.sanitized_reason == (
        "INSTRUMENT_MASTER_METADATA_NOT_VALIDATED"
    )


def test_record_count_mismatch_becomes_corrupt_proof():
    records = _records()

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(
                records,
                record_count=len(records) + 1,
            ),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.CORRUPT
    )
    assert proof.sanitized_reason == (
        "INSTRUMENT_MASTER_RECORD_COUNT_MISMATCH"
    )


def test_invalid_fetch_timestamp_becomes_corrupt_proof():
    records = _records()

    metadata = _metadata(records)
    metadata[
        "fetched_at_epoch_seconds"
    ] = float("nan")

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=metadata,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.CORRUPT
    )


def test_missing_market_identity_is_failed_by_existing_readiness():
    records = _records(
        nifty=False,
    )

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(records),
            observed_at=NOW,
        )
    )

    readiness = (
        evaluate_task9_angel_instrument_master(
            authority=(
                build_task9_angel_capability_session()
            ),
            runtime_config=_config(),
            proof=proof,
        )
    )

    assert (
        readiness.status
        is Task9AngelInstrumentMasterReadinessStatus.FAILED_FATAL
    )


def test_proof_remains_paper_only():
    records = _records()

    proof = (
        produce_task9_angel_instrument_master_proof(
            records=records,
            metadata=_metadata(records),
            observed_at=NOW,
        )
    )

    assert proof.execution_mode == "PAPER"
    assert (
        proof.broker_order_submission
        is False
    )
    assert (
        proof.live_execution_eligible
        is False
    )


def test_producer_has_no_transport_owner_argument():
    parameters = inspect.signature(
        produce_task9_angel_instrument_master_proof
    ).parameters

    assert tuple(parameters) == (
        "records",
        "metadata",
        "observed_at",
    )
