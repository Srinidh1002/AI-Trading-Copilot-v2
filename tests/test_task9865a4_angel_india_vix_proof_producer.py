from datetime import datetime, timedelta, timezone
import inspect
from zoneinfo import ZoneInfo

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_india_vix_proof_producer import (
    produce_task9_angel_india_vix_proof,
)
from services.certification.task9_angel_india_vix_readiness import (
    Task9AngelIndiaVixReadinessStatus,
    evaluate_task9_angel_india_vix,
)
from services.contracts.task9_angel_india_vix_proof_v1 import (
    Task9AngelIndiaVixProbeStatus,
)
from services.paper_orchestration.india_vix_live_reader import (
    IndiaVixLiveReader,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


NOW = datetime(
    2026,
    8,
    17,
    6,
    15,
    tzinfo=timezone.utc,
)


def _master():
    return [
        {
            "symbol": "India VIX",
            "name": "INDIA VIX",
            "exch_seg": "NSE",
            "instrumenttype": "AMXIDX",
            "token": "99926017",
        }
    ]


def _row(
    *,
    timestamp=None,
):
    stamp = (
        timestamp
        if timestamp is not None
        else NOW - timedelta(seconds=1)
    )

    return {
        "exchange": "NSE",
        "symbolToken": "99926017",
        "tradingSymbol": "India VIX",
        "ltp": 14.5,
        "close": 14.1,
        "exchFeedTime": (
            stamp.astimezone(
                ZoneInfo("Asia/Kolkata")
            ).strftime(
                "%d-%b-%Y %H:%M:%S"
            )
        ),
    }


class _Client:
    def __init__(self, row):
        self.row = row
        self.calls = 0

    def get_market_data(
        self,
        mode,
        exchange_tokens,
    ):
        self.calls += 1

        assert mode == "FULL"
        assert exchange_tokens == {
            "NSE": ["99926017"]
        }

        return {
            "status": True,
            "data": {
                "fetched": [
                    self.row
                ]
            },
        }


def _ready_capture():
    client = _Client(
        _row()
    )

    values = iter((
        NOW,
        NOW,
    ))

    reader = IndiaVixLiveReader(
        master_fetcher=_master,
        market_client=client,
        clock=lambda: next(values),
    )

    return (
        reader.capture(
            "task9865a4-ready"
        ),
        reader,
        client,
    )


def test_ready_capture_becomes_available_proof():
    capture, _, _ = (
        _ready_capture()
    )

    proof = (
        produce_task9_angel_india_vix_proof(
            capture
        )
    )

    assert (
        proof.status
        is Task9AngelIndiaVixProbeStatus.AVAILABLE
    )

    assert proof.market == "INDIA_VIX"
    assert proof.exchange == "NSE"
    assert proof.instrument_type == "AMXIDX"

    assert proof.provider_timestamp == (
        capture.provider_timestamp
    )
    assert proof.ltp == capture.current_value
    assert (
        proof.previous_close
        == capture.previous_close
    )
    assert proof.identity_verified is True


def test_ready_proof_is_ready_in_existing_task9_readiness():
    capture, _, _ = (
        _ready_capture()
    )

    proof = (
        produce_task9_angel_india_vix_proof(
            capture
        )
    )

    readiness = (
        evaluate_task9_angel_india_vix(
            authority=(
                build_task9_angel_capability_session()
            ),
            runtime_config=_config(),
            proof=proof,
        )
    )

    assert (
        readiness.status
        is Task9AngelIndiaVixReadinessStatus.READY
    )


def test_unavailable_capture_stays_optional_unavailable():
    client = _Client({
        "exchange": "NSE",
        "symbolToken": "WRONG",
        "tradingSymbol": "India VIX",
        "ltp": 14.5,
        "close": 14.1,
        "exchFeedTime": (
            NOW.astimezone(
                ZoneInfo("Asia/Kolkata")
            ).strftime(
                "%d-%b-%Y %H:%M:%S"
            )
        ),
    })

    reader = IndiaVixLiveReader(
        master_fetcher=_master,
        market_client=client,
        clock=lambda: NOW,
    )

    capture = reader.capture(
        "task9865a4-unavailable"
    )

    proof = (
        produce_task9_angel_india_vix_proof(
            capture
        )
    )

    assert (
        proof.status
        is Task9AngelIndiaVixProbeStatus.UNAVAILABLE
    )
    assert proof.sanitized_reason == (
        "INDIA_VIX_QUOTE_IDENTITY_MISMATCH"
    )

    readiness = (
        evaluate_task9_angel_india_vix(
            authority=(
                build_task9_angel_capability_session()
            ),
            runtime_config=_config(),
            proof=proof,
        )
    )

    assert (
        readiness.status
        is Task9AngelIndiaVixReadinessStatus.UNAVAILABLE_OPTIONAL
    )


def test_stale_capture_does_not_become_available():
    client = _Client(
        _row(
            timestamp=(
                NOW - timedelta(minutes=10)
            )
        )
    )

    reader = IndiaVixLiveReader(
        master_fetcher=_master,
        market_client=client,
        clock=lambda: NOW,
    )

    capture = reader.capture(
        "task9865a4-stale"
    )

    assert capture.source_status == "STALE"

    proof = (
        produce_task9_angel_india_vix_proof(
            capture
        )
    )

    assert (
        proof.status
        is Task9AngelIndiaVixProbeStatus.UNAVAILABLE
    )
    assert proof.identity_verified is True
    assert proof.ltp == capture.current_value
    assert (
        proof.previous_close
        == capture.previous_close
    )
    assert proof.sanitized_reason == (
        "INDIA_VIX_PROVIDER_TIMESTAMP_NOT_FRESH"
    )


def test_producer_adds_no_second_vix_request():
    capture, reader, client = (
        _ready_capture()
    )

    first = (
        produce_task9_angel_india_vix_proof(
            capture
        )
    )

    second = (
        produce_task9_angel_india_vix_proof(
            capture
        )
    )

    assert first == second
    assert reader.master_resolution_count == 1
    assert reader.quote_count == 1
    assert client.calls == 1


def test_proof_remains_paper_only():
    capture, _, _ = (
        _ready_capture()
    )

    proof = (
        produce_task9_angel_india_vix_proof(
            capture
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


def test_producer_has_no_transport_arguments():
    parameters = inspect.signature(
        produce_task9_angel_india_vix_proof
    ).parameters

    assert tuple(parameters) == (
        "capture",
    )
