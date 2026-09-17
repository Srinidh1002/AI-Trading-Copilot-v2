import json
from datetime import datetime, time, timedelta

from services.certification.task9_collector_observability_store import (
    Task9CollectorObservabilityStore,
)
from services.certification.task9_live_collector_session_resolver import (
    build_task9_live_collector_session_resolver,
)
from services.contracts.task9_collector_observability_v1 import (
    Task9CollectorEventType,
    Task9CollectorEventV1,
    Task9CollectorRunSummaryV1,
)
from services.market.task9_live_tick_stream import (
    IST,
    Task9LiveTickJournal,
    Task9LiveTickStream,
    normalize_task9_websocket_tick,
)


NOW = datetime(
    2026,
    8,
    18,
    10,
    0,
    tzinfo=IST,
)


def _resolver():
    return build_task9_live_collector_session_resolver(
        nfo_new_entry_cutoff=time(15, 20),
        bfo_new_entry_cutoff=time(15, 20),
    )


def test_optional_provider_fields_round_trip_without_sequence_authority(
    tmp_path,
):
    journal = Task9LiveTickJournal(
        tmp_path,
        session_state_resolver=_resolver(),
    )

    tick = normalize_task9_websocket_tick(
        exchange="NSE",
        symbol_token="99926000",
        provider_timestamp=NOW,
        received_at=NOW,
        ltp=25000,
        volume=12345,
        open_price=24950,
        high_price=25050,
        low_price=24900,
        close_price=24975,
        open_interest=555,
        subscription_mode=3,
    )

    assert journal.append(tick)

    restored = (
        Task9LiveTickJournal(
            tmp_path
        ).load(
            NOW.date()
        )[0]
    )

    assert restored.volume == 12345
    assert restored.open_price == 24950
    assert restored.high_price == 25050
    assert restored.low_price == 24900
    assert restored.close_price == 24975
    assert restored.open_interest == 555
    assert restored.subscription_mode == 3

    raw = (
        tmp_path
        / f"ticks-{NOW.date().isoformat()}.jsonl"
    ).read_text(
        encoding="utf-8"
    )

    assert "sequence_number" not in raw
    assert (
        "open_interest_change_percentage"
        not in raw
    )


def test_event_store_is_durable_and_paper_only(
    tmp_path,
):
    store = (
        Task9CollectorObservabilityStore(
            tmp_path
        )
    )

    event = Task9CollectorEventV1(
        event_id="run-1:00000001:CONNECTED",
        collector_run_id="run-1",
        event_type=(
            Task9CollectorEventType.CONNECTED
        ),
        observed_at=NOW,
    )

    store.append_event(event)

    path = (
        tmp_path
        / "collector-observability"
        / "run-1"
        / "events.jsonl"
    )

    value = json.loads(
        path.read_text(
            encoding="utf-8"
        ).strip()
    )

    assert (
        value["event_type"]
        == "CONNECTED"
    )

    assert (
        value["execution_mode"]
        == "PAPER"
    )

    assert (
        value["broker_order_submission"]
        is False
    )

    assert (
        value["live_execution_eligible"]
        is False
    )


def test_summary_store_persists_required_run_authority(
    tmp_path,
):
    store = (
        Task9CollectorObservabilityStore(
            tmp_path
        )
    )

    summary = Task9CollectorRunSummaryV1(
        collector_run_id="run-2",
        started_at=NOW,
        stopped_at=(
            NOW
            + timedelta(minutes=1)
        ),
        connected_at=NOW,
        markets_subscribed=(
            "NIFTY",
            "SENSEX",
        ),
        nifty_last_tick_received_at=NOW,
        sensex_last_tick_received_at=NOW,
        reconnect_count=2,
        event_ids=(
            "event-1",
            "event-2",
        ),
        close_reason="SUPERVISOR_EXIT",
        session_close_state="NOT_REACHED",
    )

    store.save_summary(
        summary
    )

    path = (
        tmp_path
        / "collector-observability"
        / "run-2"
        / "summary.json"
    )

    value = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert value[
        "markets_subscribed"
    ] == [
        "NIFTY",
        "SENSEX",
    ]

    assert (
        value["reconnect_count"]
        == 2
    )


def test_stream_emits_canonical_no_tick_per_stale_market(
    tmp_path,
):
    emitted = []

    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=_resolver(),
        ),
        websocket_factory=lambda **_: None,
        credentials={},
        collector_run_id="run-3",
        event_sink=emitted.append,
    )

    stream._session_open = True
    stream._session_opened_at = NOW

    stream.last_valid_tick_received_at_by_market[
        "NIFTY"
    ] = (
        NOW + timedelta(seconds=20)
    )

    stream.latest_provider_timestamp_by_market[
        "NIFTY"
    ] = (
        NOW + timedelta(seconds=20)
    )

    stale = stream._stale_markets(
        NOW + timedelta(seconds=31)
    )

    assert stale == (
        "SENSEX",
    )

    for market in stale:
        never_received = (
            stream.last_valid_tick_received_at_by_market[
                market
            ]
            is None
        )

        stream._event(
            f"STALE:{market}",
            canonical_type=(
                Task9CollectorEventType.NO_TICK
                if never_received
                else Task9CollectorEventType.STALE
            ),
            market=market,
            observed_at=(
                NOW
                + timedelta(seconds=31)
            ),
            detail_code=(
                "NO_VALID_MARKET_TICK"
            ),
        )

    assert len(emitted) == 1
    assert (
        emitted[0].event_type
        is Task9CollectorEventType.NO_TICK
    )
    assert (
        emitted[0].market
        == "SENSEX"
    )


def test_event_vocabulary_contains_entire_frozen_9862_contract():
    assert {
        item.value
        for item
        in Task9CollectorEventType
    } == {
        "CONNECTED",
        "SUBSCRIBED",
        "NO_TICK",
        "HEARTBEAT",
        "STALE",
        "DISCONNECTED",
        "RECONNECTING",
        "RECONNECTED",
        "PROVIDER_ERROR",
        "PARSE_ERROR",
        "DROPPED_MESSAGE",
        "SESSION_CLOSE",
        "STOPPED",
    }
