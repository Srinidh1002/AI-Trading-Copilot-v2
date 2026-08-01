"""Task 7A Slice 6 complete replay certification tests."""
from datetime import datetime, timezone

from services.certification.complete_replay_certification_runner import (
    run_complete_replay_certification,
)
from services.certification.replacement_replay_scenarios import (
    build_replacement_trade_scenarios,
)


NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


def test_replacement_catalogue_contains_24_trade_scenarios():
    scenarios = build_replacement_trade_scenarios()

    assert len(scenarios) == 24
    assert all(
        scenario.expected_outcome == "CLOSED_TRADE"
        for scenario in scenarios
    )
    assert len(
        {scenario.scenario_id for scenario in scenarios}
    ) == 24


def test_replacements_are_exactly_12_per_market():
    scenarios = build_replacement_trade_scenarios()

    assert sum(
        scenario.market == ("NIFTY", "NSE")
        for scenario in scenarios
    ) == 12
    assert sum(
        scenario.market == ("SENSEX", "BSE")
        for scenario in scenarios
    ) == 12


def test_complete_runner_reaches_exact_required_counts(tmp_path):
    ledger = run_complete_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-complete",
        generated_at=NOW,
    )

    assert ledger.nifty_closed_trade_count == 60
    assert ledger.sensex_closed_trade_count == 60
    assert ledger.is_complete is True


def test_safety_outcomes_remain_separate_in_complete_ledger(tmp_path):
    ledger = run_complete_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-safety-preserved",
        generated_at=NOW,
    )

    assert len(ledger.results) == 144
    assert ledger.no_trade_count == 12
    assert ledger.blocked_count == 12
    assert ledger.failed_count == 0


def test_all_120_counted_trades_really_opened_and_closed(tmp_path):
    ledger = run_complete_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-trade-coherence",
        generated_at=NOW,
    )

    closed = tuple(
        result
        for result in ledger.results
        if result.status == "CLOSED_TRADE"
    )

    assert len(closed) == 120
    assert all(result.opened for result in closed)
    assert all(result.closed for result in closed)
    assert all(result.closure_reason for result in closed)
    assert all(result.action_history for result in closed)


def test_complete_runner_is_deterministic(tmp_path):
    first = run_complete_replay_certification(
        work_root=tmp_path / "first",
        ledger_id="task-7a-deterministic",
        generated_at=NOW,
    )
    second = run_complete_replay_certification(
        work_root=tmp_path / "second",
        ledger_id="task-7a-deterministic",
        generated_at=NOW,
    )

    assert first == second


def test_complete_ledger_remains_offline_paper_only(tmp_path):
    ledger = run_complete_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-offline-paper",
        generated_at=NOW,
    )

    assert ledger.execution_mode == "PAPER"
    assert ledger.network_access_used is False
    assert ledger.broker_submission_enabled is False
    assert ledger.live_execution_eligible is False
    assert all(
        result.execution_mode == "PAPER"
        and result.network_access_used is False
        and result.broker_submission_enabled is False
        and result.live_execution_eligible is False
        for result in ledger.results
    )
