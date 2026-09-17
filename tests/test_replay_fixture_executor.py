"""Task 7A Slice 4 certified replay execution tests."""
from services.certification.replay_fixture_executor import (
    execute_replay_fixture,
)
from services.certification.replay_fixture_factory import (
    build_replay_lifecycle_fixture,
)
from services.certification.replay_scenario_catalogue import (
    build_replay_scenario_catalogue,
)


def _fixture(scenario_type, market=("NIFTY", "NSE")):
    scenario = next(
        item
        for item in build_replay_scenario_catalogue()
        if item.scenario_type == scenario_type
        and item.market == market
    )
    return build_replay_lifecycle_fixture(scenario)


def test_all_targets_runs_through_runtime_and_closes(tmp_path):
    result = execute_replay_fixture(
        _fixture("ALL_TARGETS"),
        work_root=tmp_path,
    )

    assert result.status == "CLOSED_TRADE"
    assert result.opened is True
    assert result.closed is True
    assert result.closure_reason == "TARGET_3"
    assert result.action_history == (
        "HOLD",
        "TARGET_1_HIT",
        "TARGET_2_HIT",
        "TARGET_3_HIT",
    )
    assert result.realized_pnl == 1500.0


def test_stop_scenario_closes_via_certified_stop(tmp_path):
    result = execute_replay_fixture(
        _fixture("STOP_HIT"),
        work_root=tmp_path,
    )

    assert result.status == "CLOSED_TRADE"
    assert result.closure_reason == "STOP"
    assert result.action_history[-1] == "STOP_HIT"


def test_early_exit_closes_via_safety_exit(tmp_path):
    result = execute_replay_fixture(
        _fixture("EARLY_SAFETY_EXIT"),
        work_root=tmp_path,
    )

    assert result.status == "CLOSED_TRADE"
    assert result.closure_reason == "EARLY_SAFETY_EXIT"
    assert result.action_history[-1] == "EXIT_NOW"


def test_reversal_records_partial_targets_before_stop(tmp_path):
    result = execute_replay_fixture(
        _fixture("REVERSAL"),
        work_root=tmp_path,
    )

    assert result.status == "CLOSED_TRADE"
    assert result.closure_reason == "STOP"
    assert result.action_history == (
        "TARGET_1_HIT",
        "TARGET_2_HIT",
        "STOP_HIT",
    )


def test_restart_recovery_reopens_repository_and_finishes(tmp_path):
    result = execute_replay_fixture(
        _fixture("RESTART_RECOVERY"),
        work_root=tmp_path,
    )

    assert result.status == "CLOSED_TRADE"
    assert result.closure_reason == "TARGET_3"
    assert result.action_history[-1] == "TARGET_3_HIT"


def test_sensex_uses_same_runtime_contract(tmp_path):
    result = execute_replay_fixture(
        _fixture(
            "ALL_TARGETS",
            ("SENSEX", "BSE"),
        ),
        work_root=tmp_path,
    )

    assert result.status == "CLOSED_TRADE"
    assert result.market == ("SENSEX", "BSE")
    assert result.closure_reason == "TARGET_3"


def test_no_trade_is_recorded_without_fake_position(tmp_path):
    result = execute_replay_fixture(
        _fixture("STALE_DATA"),
        work_root=tmp_path,
    )

    assert result.status == "NO_TRADE"
    assert result.opened is False
    assert result.closed is False
    assert result.blockers == ("STALE_DATA",)


def test_blocked_market_is_recorded_separately(tmp_path):
    result = execute_replay_fixture(
        _fixture("ONE_MARKET_UNAVAILABLE"),
        work_root=tmp_path,
    )

    assert result.status == "BLOCKED"
    assert result.blockers == ("MARKET_UNAVAILABLE",)


def test_execution_is_deterministic_across_clean_roots(tmp_path):
    fixture = _fixture("ALL_TARGETS")

    first = execute_replay_fixture(
        fixture,
        work_root=tmp_path / "first",
    )
    second = execute_replay_fixture(
        fixture,
        work_root=tmp_path / "second",
    )

    assert first == second


def test_results_remain_offline_paper_only(tmp_path):
    result = execute_replay_fixture(
        _fixture("ALL_TARGETS"),
        work_root=tmp_path,
    )

    assert result.execution_mode == "PAPER"
    assert result.network_access_used is False
    assert result.broker_submission_enabled is False
    assert result.live_execution_eligible is False

