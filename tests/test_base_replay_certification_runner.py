"""Task 7A Slice 5 full base replay runner certification."""
from datetime import datetime, timezone

from services.certification.base_replay_certification_runner import (
    run_base_replay_certification,
)


NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


def test_base_runner_executes_all_120_scenarios(tmp_path):
    ledger = run_base_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-base-ledger",
        generated_at=NOW,
    )

    assert len(ledger.results) == 120
    assert len(
        {result.result_id for result in ledger.results}
    ) == 120
    assert len(
        {result.scenario_id for result in ledger.results}
    ) == 120


def test_base_runner_records_real_closed_trade_counts(tmp_path):
    ledger = run_base_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-count-ledger",
        generated_at=NOW,
    )

    assert ledger.nifty_closed_trade_count == 48
    assert ledger.sensex_closed_trade_count == 48
    assert ledger.is_complete is False


def test_base_runner_keeps_safety_outcomes_separate(tmp_path):
    ledger = run_base_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-safety-ledger",
        generated_at=NOW,
    )

    assert ledger.no_trade_count == 12
    assert ledger.blocked_count == 12
    assert ledger.failed_count == 0

    assert (
        ledger.nifty_closed_trade_count
        + ledger.sensex_closed_trade_count
        + ledger.no_trade_count
        + ledger.blocked_count
        + ledger.failed_count
        == 120
    )


def test_every_counted_trade_actually_opened_and_closed(tmp_path):
    ledger = run_base_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-coherence-ledger",
        generated_at=NOW,
    )

    closed = tuple(
        result
        for result in ledger.results
        if result.status == "CLOSED_TRADE"
    )

    assert len(closed) == 96
    assert all(result.opened for result in closed)
    assert all(result.closed for result in closed)
    assert all(
        result.opened_at is not None
        and result.closed_at is not None
        and result.closure_reason is not None
        and result.action_history
        for result in closed
    )


def test_no_trade_and_blocked_never_claim_position_activity(tmp_path):
    ledger = run_base_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-nontrade-ledger",
        generated_at=NOW,
    )

    non_trades = tuple(
        result
        for result in ledger.results
        if result.status in {"NO_TRADE", "BLOCKED"}
    )

    assert len(non_trades) == 24
    assert all(result.opened is False for result in non_trades)
    assert all(result.closed is False for result in non_trades)
    assert all(result.opened_at is None for result in non_trades)
    assert all(result.closed_at is None for result in non_trades)
    assert all(result.realized_pnl == 0.0 for result in non_trades)


def test_runner_is_deterministic_across_clean_roots(tmp_path):
    first = run_base_replay_certification(
        work_root=tmp_path / "first",
        ledger_id="task-7a-deterministic",
        generated_at=NOW,
    )
    second = run_base_replay_certification(
        work_root=tmp_path / "second",
        ledger_id="task-7a-deterministic",
        generated_at=NOW,
    )

    assert first == second


def test_full_ledger_remains_offline_paper_only(tmp_path):
    ledger = run_base_replay_certification(
        work_root=tmp_path,
        ledger_id="task-7a-safety",
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
