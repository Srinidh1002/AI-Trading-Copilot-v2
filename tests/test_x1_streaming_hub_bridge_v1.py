from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.x1.observation_tracker_v1 import (
    ObservationQualityV1,
    ObservationTrackerV1,
)
from services.x1.streaming_hub_bridge_v1 import (
    StreamingHubBridgeV1,
)

BASE = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)


def make_bridge(*, now=BASE):
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: now)
    bridge = StreamingHubBridgeV1(hub=hub, tracker=tracker)
    return hub, tracker, bridge


def rec(
    *,
    symbol="NSE:NIFTY50-INDEX",
    ltp=100.0,
    ts=None,
    timestamp_source="PROVIDER",
    received_at=None,
    canonical_id="NIFTY:UNDERLYING",
    market="NIFTY",
    instrument_type="UNDERLYING",
):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "ltp": ltp,
        "ts": ts or BASE,
        "timestamp_source": timestamp_source,
        "received_at": received_at or BASE,
        "canonical_instrument_id": canonical_id,
        "market_symbol": market,
        "instrument_type": instrument_type,
    }


def test_valid_observation_is_published_into_hub():
    hub, _, bridge = make_bridge()
    result = bridge.handle_observation(
        rec(ltp=23456.75),
        connection_generation=1,
        current_generation=1,
    )
    assert result.accepted is True
    assert result.quality is ObservationQualityV1.VALID
    assert result.quote_id is not None
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id="NIFTY:UNDERLYING",
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.last_price == 23456.75


def test_duplicate_is_not_published_as_new_evidence():
    hub, _, bridge = make_bridge()
    first = bridge.handle_observation(
        rec(ltp=100.0),
        connection_generation=1,
        current_generation=1,
    )
    assert first.accepted is True
    second = bridge.handle_observation(
        rec(ltp=100.0),
        connection_generation=1,
        current_generation=1,
    )
    assert second.accepted is False
    assert (
        second.quality is ObservationQualityV1.SUSPECTED_DUPLICATE
    )
    assert second.quote_id is None


def test_out_of_order_is_not_published():
    hub, _, bridge = make_bridge()
    bridge.handle_observation(
        rec(ts=BASE + timedelta(seconds=2)),
        connection_generation=1,
        current_generation=1,
    )
    ooo = bridge.handle_observation(
        rec(ts=BASE + timedelta(seconds=1)),
        connection_generation=1,
        current_generation=1,
    )
    assert ooo.accepted is False
    assert ooo.quality is ObservationQualityV1.OUT_OF_ORDER


def test_stale_generation_is_not_published():
    hub, _, bridge = make_bridge()
    stale = bridge.handle_observation(
        rec(),
        connection_generation=1,
        current_generation=2,
    )
    assert stale.accepted is False
    assert stale.quality is ObservationQualityV1.STALE_GENERATION


def test_future_dated_is_not_published():
    hub, _, bridge = make_bridge()
    future_ts = BASE + timedelta(seconds=60)
    result = bridge.handle_observation(
        rec(ts=future_ts),
        connection_generation=1,
        current_generation=1,
    )
    assert result.accepted is False
    assert result.quality is ObservationQualityV1.FUTURE_DATED


def test_missing_canonical_id_is_not_published():
    hub, _, bridge = make_bridge()
    result = bridge.handle_observation(
        rec(canonical_id=""),
        connection_generation=1,
        current_generation=1,
    )
    assert result.accepted is False
    assert result.quality is ObservationQualityV1.MALFORMED


def test_malformed_price_is_not_published():
    hub, _, bridge = make_bridge()
    bad = rec()
    bad["ltp"] = 0
    result = bridge.handle_observation(
        bad, connection_generation=1, current_generation=1
    )
    assert result.accepted is False
    assert result.quality is ObservationQualityV1.MALFORMED


def test_underlying_uses_underlying_exchange():
    hub, _, bridge = make_bridge()
    result = bridge.handle_observation(
        rec(market="NIFTY", instrument_type="UNDERLYING"),
        connection_generation=1,
        current_generation=1,
    )
    assert result.accepted is True
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NSE",
        instrument_type="UNDERLYING",
        canonical_instrument_id="NIFTY:UNDERLYING",
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.exchange == "NSE"


def test_future_uses_derivative_exchange():
    hub, _, bridge = make_bridge()
    future_record = rec(
        symbol="NSE:NIFTY26SEPFUT",
        canonical_id="NIFTY:FUTURE:2026-09-30",
        instrument_type="FUTURE",
    )
    result = bridge.handle_observation(
        future_record,
        connection_generation=1,
        current_generation=1,
    )
    assert result.accepted is True
    quote = hub.get_quote(
        provider="FYERS",
        market_symbol="NIFTY",
        exchange="NFO",
        instrument_type="FUTURE",
        canonical_instrument_id="NIFTY:FUTURE:2026-09-30",
        max_age_seconds=60,
        now=BASE,
    )
    assert quote.exchange == "NFO"


def test_hub_failure_is_returned_not_raised():
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    bridge = StreamingHubBridgeV1(hub=hub, tracker=tracker)

    # Force hub.publish_quote to fail by monkey-patching the instance.
    original = hub.publish_quote

    def boom(_):
        raise RuntimeError("forced")

    hub.publish_quote = boom  # type: ignore[method-assign]
    try:
        result = bridge.handle_observation(
            rec(),
            connection_generation=1,
            current_generation=1,
        )
        assert result.accepted is False
        assert (
            result.reason_code is not None
            and result.reason_code.startswith("hub_publish:")
        )
    finally:
        hub.publish_quote = original  # type: ignore[method-assign]


def test_tracker_failure_is_returned_not_raised():
    hub = SharedMarketDataHubV2()
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    bridge = StreamingHubBridgeV1(hub=hub, tracker=tracker)

    def boom(*args, **kwargs):
        raise RuntimeError("forced")

    tracker.classify = boom  # type: ignore[method-assign]
    result = bridge.handle_observation(
        rec(),
        connection_generation=1,
        current_generation=1,
    )
    assert result.accepted is False
    assert (
        result.reason_code is not None
        and result.reason_code.startswith("tracker:")
    )
