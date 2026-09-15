from datetime import datetime, time, timedelta

from services.certification.task9_live_collector_session_resolver import (
    build_task9_live_collector_session_resolver,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.market.task9_live_tick_stream import (
    IST,
    Task9LiveTickJournal,
    Task9LiveTickStream,
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


def test_live_collector_resolver_returns_correct_market_segments():
    resolver = _resolver()

    nifty = resolver(
        market="NIFTY",
        evaluated_at=NOW,
        market_date=NOW.date(),
    )

    sensex = resolver(
        market="SENSEX",
        evaluated_at=NOW,
        market_date=NOW.date(),
    )

    assert (
        nifty.segment
        is Task9MarketSegment.NFO_OPTIONS
    )

    assert (
        sensex.segment
        is Task9MarketSegment.BFO_OPTIONS
    )

    assert (
        nifty.phase
        is Task9SessionPhase.OPEN
    )

    assert (
        sensex.phase
        is Task9SessionPhase.OPEN
    )


def test_one_market_tick_never_keeps_other_market_fresh(
    tmp_path,
):
    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=_resolver(),
        ),
        websocket_factory=lambda **_: None,
        credentials={},
    )

    stream._session_open = True
    stream._session_opened_at = NOW

    stream.last_valid_tick_received_at_by_market[
        "NIFTY"
    ] = (
        NOW + timedelta(seconds=29)
    )

    stream.latest_provider_timestamp_by_market[
        "NIFTY"
    ] = (
        NOW + timedelta(seconds=29)
    )

    # SENSEX has received no valid market tick since open.
    observed = (
        NOW + timedelta(seconds=31)
    )

    health = stream.health(
        now=observed
    )

    assert (
        health["markets"]["NIFTY"]["state"]
        == "OPEN"
    )

    assert (
        health["markets"]["SENSEX"]["state"]
        == "STALE"
    )

    assert (
        stream._stale_markets(
            observed
        )
        == ("SENSEX",)
    )


def test_both_markets_are_independently_fresh(
    tmp_path,
):
    stream = Task9LiveTickStream(
        journal=Task9LiveTickJournal(
            tmp_path,
            session_state_resolver=_resolver(),
        ),
        websocket_factory=lambda **_: None,
        credentials={},
    )

    stream._session_open = True
    stream._session_opened_at = NOW

    observed = (
        NOW + timedelta(seconds=20)
    )

    for market in (
        "NIFTY",
        "SENSEX",
    ):
        stream.last_valid_tick_received_at_by_market[
            market
        ] = NOW

        stream.latest_provider_timestamp_by_market[
            market
        ] = NOW

    health = stream.health(
        now=observed
    )

    assert (
        health["markets"]["NIFTY"]["state"]
        == "OPEN"
    )

    assert (
        health["markets"]["SENSEX"]["state"]
        == "OPEN"
    )

    assert (
        stream._stale_markets(
            observed
        )
        == ()
    )
