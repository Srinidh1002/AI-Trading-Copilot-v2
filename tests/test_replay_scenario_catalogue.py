"""Task 7A Slice 2 deterministic scenario catalogue certification."""
from collections import Counter

import pytest

from services.certification.replay_scenario_catalogue import (
    REQUIRED_SCENARIO_TYPES,
    build_replay_scenario_catalogue,
    scenario_coverage,
    scenarios_for_market,
)


def test_catalogue_contains_exactly_120_base_scenarios():
    catalogue = build_replay_scenario_catalogue()

    assert len(catalogue) == 120
    assert len(
        {
            scenario.scenario_id
            for scenario in catalogue
        }
    ) == 120
    assert len(
        {
            scenario.fixture_id
            for scenario in catalogue
        }
    ) == 120


def test_catalogue_contains_exactly_60_cases_per_market():
    catalogue = build_replay_scenario_catalogue()

    nifty = scenarios_for_market(
        catalogue,
        ("NIFTY", "NSE"),
    )
    sensex = scenarios_for_market(
        catalogue,
        ("SENSEX", "BSE"),
    )

    assert len(nifty) == 60
    assert len(sensex) == 60
    assert tuple(
        scenario.sequence for scenario in nifty
    ) == tuple(range(1, 61))
    assert tuple(
        scenario.sequence for scenario in sensex
    ) == tuple(range(1, 61))


def test_every_required_scenario_type_is_covered():
    catalogue = build_replay_scenario_catalogue()
    coverage = scenario_coverage(catalogue)

    assert tuple(coverage) == REQUIRED_SCENARIO_TYPES
    assert all(
        coverage[scenario_type] >= 2
        for scenario_type in REQUIRED_SCENARIO_TYPES
    )


def test_each_market_independently_covers_all_scenarios():
    catalogue = build_replay_scenario_catalogue()

    for market in (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ):
        values = scenarios_for_market(
            catalogue,
            market,
        )
        covered = {
            scenario.scenario_type
            for scenario in values
        }
        assert covered == set(REQUIRED_SCENARIO_TYPES)


def test_safety_scenarios_are_not_falsely_counted_as_trades():
    catalogue = build_replay_scenario_catalogue()

    expected = {
        "STALE_DATA": "NO_TRADE",
        "MISSING_OPTION_CHAIN": "NO_TRADE",
        "ONE_MARKET_UNAVAILABLE": "BLOCKED",
        "BOTH_BLOCKED": "BLOCKED",
    }

    for scenario in catalogue:
        if scenario.scenario_type in expected:
            assert (
                scenario.expected_outcome
                == expected[scenario.scenario_type]
            )


def test_lifecycle_scenarios_require_terminal_actions():
    catalogue = build_replay_scenario_catalogue()
    lifecycle_types = {
        "DUPLICATE_ENTRY",
        "PARTIAL_EXITS",
        "ALL_TARGETS",
        "STOP_HIT",
        "EARLY_SAFETY_EXIT",
        "RESTART_RECOVERY",
    }

    for scenario in catalogue:
        if scenario.scenario_type not in lifecycle_types:
            continue

        assert scenario.expected_outcome == "CLOSED_TRADE"
        assert scenario.expected_actions

        if scenario.scenario_type == "ALL_TARGETS":
            assert scenario.expected_actions == (
                "TARGET_1_HIT",
                "TARGET_2_HIT",
                "TARGET_3_HIT",
            )
        if scenario.scenario_type == "STOP_HIT":
            assert scenario.expected_actions == (
                "STOP_HIT",
            )
        if (
            scenario.scenario_type
            == "EARLY_SAFETY_EXIT"
        ):
            assert scenario.expected_actions == (
                "EXIT_NOW",
            )


def test_catalogue_is_deterministic():
    first = build_replay_scenario_catalogue()
    second = build_replay_scenario_catalogue()

    assert first == second


def test_scenario_distribution_is_balanced_between_markets():
    catalogue = build_replay_scenario_catalogue()

    nifty = Counter(
        scenario.scenario_type
        for scenario in scenarios_for_market(
            catalogue,
            ("NIFTY", "NSE"),
        )
    )
    sensex = Counter(
        scenario.scenario_type
        for scenario in scenarios_for_market(
            catalogue,
            ("SENSEX", "BSE"),
        )
    )

    assert nifty == sensex


def test_non_default_target_fails_closed():
    with pytest.raises(
        ValueError,
        match="exactly 60",
    ):
        build_replay_scenario_catalogue(
            closed_trade_target_per_market=59,
        )


def test_every_scenario_remains_offline_paper_only():
    catalogue = build_replay_scenario_catalogue()

    assert all(
        scenario.execution_mode == "PAPER"
        for scenario in catalogue
    )
    assert all(
        scenario.network_access_allowed is False
        for scenario in catalogue
    )
    assert all(
        scenario.broker_submission_enabled is False
        for scenario in catalogue
    )
    assert all(
        scenario.live_execution_eligible is False
        for scenario in catalogue
    )
