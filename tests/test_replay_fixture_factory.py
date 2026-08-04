"""Task 7A Slice 3 deterministic typed fixture certification."""
from services.certification.replay_fixture_factory import (
    ReplayLifecycleFixtureV1,
    build_replay_fixture_catalogue,
    build_replay_lifecycle_fixture,
)
from services.certification.replay_scenario_catalogue import (
    build_replay_scenario_catalogue,
)


def _scenario(scenario_type, market=("NIFTY", "NSE")):
    return next(
        scenario
        for scenario in build_replay_scenario_catalogue()
        if scenario.scenario_type == scenario_type
        and scenario.market == market
    )


def test_fixture_catalogue_matches_all_120_scenarios():
    fixtures = build_replay_fixture_catalogue()

    assert len(fixtures) == 120
    assert all(
        type(item) is ReplayLifecycleFixtureV1
        for item in fixtures
    )
    assert len(
        {item.fixture_id for item in fixtures}
    ) == 120


def test_trade_fixture_uses_exact_market_identity():
    nifty = build_replay_lifecycle_fixture(
        _scenario("ALL_TARGETS")
    )
    sensex = build_replay_lifecycle_fixture(
        _scenario(
            "ALL_TARGETS",
            ("SENSEX", "BSE"),
        )
    )

    assert (
        nifty.initial_position.underlying_symbol,
        nifty.initial_position.exchange,
    ) == ("NIFTY", "NSE")
    assert (
        sensex.initial_position.underlying_symbol,
        sensex.initial_position.exchange,
    ) == ("SENSEX", "BSE")


def test_all_targets_fixture_has_hold_and_three_target_prices():
    fixture = build_replay_lifecycle_fixture(
        _scenario("ALL_TARGETS")
    )

    assert fixture.initial_position is not None
    assert tuple(
        item.current_bid
        for item in fixture.monitoring_evidence
    ) == (105.0, 110.0, 120.0, 130.0)


def test_stop_fixture_reaches_below_stop_price():
    fixture = build_replay_lifecycle_fixture(
        _scenario("STOP_HIT")
    )

    assert fixture.initial_position is not None
    assert (
        fixture.monitoring_evidence[-1].current_bid
        < fixture.initial_position.stop_loss
    )


def test_early_exit_fixture_invalidates_setup():
    fixture = build_replay_lifecycle_fixture(
        _scenario("EARLY_SAFETY_EXIT")
    )

    assert (
        fixture.monitoring_evidence[-1].setup_valid
        is False
    )
    assert (
        fixture.monitoring_evidence[-1].confidence
        < fixture.monitoring_evidence[0].confidence
    )


def test_reversal_fixture_partially_exits_then_stops():
    fixture = build_replay_lifecycle_fixture(
        _scenario("REVERSAL")
    )

    assert tuple(
        item.current_bid
        for item in fixture.monitoring_evidence
    ) == (110.0, 120.0, 89.0)


def test_non_trade_safety_fixture_has_no_position_or_monitoring():
    for scenario_type in (
        "STALE_DATA",
        "MISSING_OPTION_CHAIN",
        "ONE_MARKET_UNAVAILABLE",
        "BOTH_BLOCKED",
    ):
        fixture = build_replay_lifecycle_fixture(
            _scenario(scenario_type)
        )
        assert fixture.initial_position is None
        assert fixture.monitoring_evidence == ()


def test_every_trade_evidence_matches_position_identity():
    fixtures = build_replay_fixture_catalogue()

    for fixture in fixtures:
        if fixture.initial_position is None:
            continue
        assert all(
            item.position_id
            == fixture.initial_position.position_id
            for item in fixture.monitoring_evidence
        )


def test_fixture_generation_is_deterministic():
    first = build_replay_fixture_catalogue()
    second = build_replay_fixture_catalogue()

    assert first == second


def test_every_fixture_remains_offline_paper_only():
    fixtures = build_replay_fixture_catalogue()

    assert all(
        item.execution_mode == "PAPER"
        and item.network_access_used is False
        and item.broker_submission_enabled is False
        and item.live_execution_eligible is False
        for item in fixtures
    )
