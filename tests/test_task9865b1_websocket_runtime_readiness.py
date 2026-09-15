import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.certification.task9_websocket_runtime_proof_producer import (
    produce_task9_websocket_runtime_proof,
)
from services.certification.task9_websocket_runtime_readiness import (
    project_task9_websocket_runtime_to_report,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9ProviderCapability,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_websocket_runtime_proof_v1 import (
    Task9WebsocketRuntimeProbeStatus,
)
from services.market.task9_live_tick_stream import (
    Task9LiveTickJournal,
    normalize_task9_websocket_tick,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


IST = ZoneInfo("Asia/Kolkata")

MARKET_DATE = date(
    2026,
    8,
    17,
)

NOW = datetime(
    2026,
    8,
    17,
    12,
    0,
    0,
    tzinfo=IST,
)


def _open_state(**_):
    from datetime import time

    from services.contracts.task9_market_session_policy_v1 import (
        Task9MarketSegment,
        Task9SessionPhase,
    )
    from services.contracts.task9_market_session_state_v1 import (
        Task9SegmentSessionStateV1,
    )

    market = _["market"]
    evaluated_at = _["evaluated_at"]
    market_date = _["market_date"]

    return Task9SegmentSessionStateV1(
        segment=(
            Task9MarketSegment.NFO_OPTIONS
            if market == "NIFTY"
            else Task9MarketSegment.BFO_OPTIONS
        ),
        market_date=market_date,
        evaluated_at=evaluated_at,
        timezone="Asia/Kolkata",
        phase=Task9SessionPhase.OPEN,
        market_open=True,
        new_entries_allowed=True,
        position_monitoring_allowed=True,
        close_drain_required=False,
        session_open_time=time(9, 15),
        new_entry_cutoff=time(15, 30),
        position_monitoring_until=time(15, 40),
        session_close_time=time(15, 40),
        calendar_status="TRADING_DAY",
        policy_id="task9865b1-session",
        policy_version="1",
    )


def _lock(root):
    path = (
        root
        / "task9-live-websocket-collector.lock"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps({
            "pid": 12345,
            "acquired_at": NOW.isoformat(),
            "ownership_token": "owner123",
        }),
        encoding="utf-8",
    )


def _seed(root):
    journal = Task9LiveTickJournal(
        root,
        session_state_resolver=_open_state,
    )

    for exchange, token, price in (
        ("NSE", "99926000", 25000.0),
        ("BSE", "99919000", 80000.0),
    ):
        journal.append(
            normalize_task9_websocket_tick(
                exchange=exchange,
                symbol_token=token,
                provider_timestamp=(
                    NOW - timedelta(seconds=1)
                ),
                received_at=(
                    NOW - timedelta(seconds=1)
                ),
                ltp=price,
            )
        )


def test_durable_lock_plus_fresh_two_market_ticks_is_ready(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.READY
    )

    assert proof.collector_lock_present
    assert proof.collector_lock_valid


def test_missing_lock_blocks_even_with_ticks(
    tmp_path,
):
    _seed(tmp_path)

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.NOT_READY
    )


def test_one_market_missing_blocks(
    tmp_path,
):
    _lock(tmp_path)

    journal = Task9LiveTickJournal(
        tmp_path,
        session_state_resolver=_open_state,
    )

    journal.append(
        normalize_task9_websocket_tick(
            exchange="NSE",
            symbol_token="99926000",
            provider_timestamp=NOW,
            received_at=NOW,
            ltp=25000.0,
        )
    )

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.NOT_READY
    )

    assert (
        "SENSEX_WEBSOCKET_TICK_MISSING"
        in proof.sanitized_reason
    )


def test_stale_tick_blocks(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=(
            NOW + timedelta(seconds=31)
        ),
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.NOT_READY
    )


def test_ready_proof_projects_required_websocket_row_to_ready(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    report = project_task9_websocket_runtime_to_report(
        report=build_task9_provider_capability_report(
            _config()
        ),
        proof=proof,
    )

    row = next(
        item
        for item in report.capability_states
        if (
            item.provider_family
            is Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
            and item.capability
            is Task9ProviderCapability.MARKET_DATA_WEBSOCKET
        )
    )

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )


def test_producer_has_no_network_or_socket_requirement(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert proof.execution_mode == "PAPER"
    assert proof.broker_order_submission is False
    assert proof.live_execution_eligible is False


def test_websocket_generic_projection_metadata_is_scalar_only():
    from services.certification.task9_provider_capability_report_builder import (
        build_task9_provider_capability_report,
    )
    from services.certification.task9_websocket_runtime_proof_producer import (
        produce_task9_websocket_runtime_proof,
    )
    from services.certification.task9_websocket_runtime_readiness import (
        project_task9_websocket_runtime_to_report,
    )
    from services.contracts.task9_provider_capability_report_v1 import (
        Task9ProviderCapability,
        Task9ProviderFamily,
    )

    from tests.test_task9_runtime_config_snapshot_v1 import (
        _config,
    )

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        proof = produce_task9_websocket_runtime_proof(
            live_stream_root=root,
            market_date=_config().market_date,
            observed_at=NOW,
            maximum_tick_age_seconds=300.0,
        )

        report = build_task9_provider_capability_report(
            _config()
        )

        projected = project_task9_websocket_runtime_to_report(
            report=report,
            proof=proof,
        )

        rows = tuple(
            row
            for row in projected.capability_states
            if (
                row.provider_family
                is Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
                and row.capability
                is Task9ProviderCapability.MARKET_DATA_WEBSOCKET
            )
        )

        assert len(rows) == 1

        assert all(
            type(value)
            in {
                str,
                int,
                float,
                bool,
            }
            for value
            in rows[0].metadata.values()
        )

        assert all(
            value is not None
            for value
            in rows[0].metadata.values()
        )


def test_iso_string_market_date_matches_production_runtime_config_boundary(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE.isoformat(),
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.READY
    )
    assert proof.collector_lock_present is True
    assert proof.collector_lock_valid is True
    assert proof.nifty_tick_received_at is not None
    assert proof.sensex_tick_received_at is not None
    assert proof.sanitized_reason is None


def test_post_observation_ticks_do_not_invalidate_frozen_websocket_snapshot(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    path = (
        tmp_path
        / f"ticks-{MARKET_DATE.isoformat()}.jsonl"
    )

    future = NOW + timedelta(seconds=2)

    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        for (
            market,
            exchange,
            token,
            ltp,
        ) in (
            (
                "NIFTY",
                "NSE",
                "99926000",
                25001.0,
            ),
            (
                "SENSEX",
                "BSE",
                "99919000",
                80001.0,
            ),
        ):
            handle.write(
                json.dumps({
                    "market": market,
                    "exchange": exchange,
                    "symbol_token": token,
                    "provider_timestamp": (
                        future.isoformat()
                    ),
                    "received_at": (
                        future.isoformat()
                    ),
                    "ltp": ltp,
                    "source": "LIVE_WEBSOCKET",
                })
                + "\n"
            )

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.READY
    )
    assert proof.sanitized_reason is None

    # The rows appended after the frozen observation boundary
    # must not become the proof's authoritative ticks.
    assert proof.nifty_tick_received_at <= NOW
    assert proof.sensex_tick_received_at <= NOW


def test_provider_future_timestamp_received_by_observation_still_fails_closed(
    tmp_path,
):
    _lock(tmp_path)
    _seed(tmp_path)

    path = (
        tmp_path
        / f"ticks-{MARKET_DATE.isoformat()}.jsonl"
    )

    provider_future = (
        NOW + timedelta(seconds=2)
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps({
                "market": "NIFTY",
                "exchange": "NSE",
                "symbol_token": "99926000",
                "provider_timestamp": (
                    provider_future.isoformat()
                ),
                # It was already received at the proof boundary,
                # therefore its future provider timestamp is a
                # genuine temporal inconsistency.
                "received_at": NOW.isoformat(),
                "ltp": 25001.0,
                "source": "LIVE_WEBSOCKET",
            })
            + "\n"
        )

    proof = produce_task9_websocket_runtime_proof(
        live_stream_root=tmp_path,
        market_date=MARKET_DATE,
        observed_at=NOW,
        maximum_tick_age_seconds=30.0,
    )

    assert (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.NOT_READY
    )

    assert (
        "NIFTY_WEBSOCKET_TIMESTAMP_FUTURE"
        in proof.sanitized_reason
    )

