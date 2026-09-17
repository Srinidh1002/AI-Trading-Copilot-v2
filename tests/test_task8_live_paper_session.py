"""Deterministic tests for the bounded Task 8 PAPER session."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import services.certification.task8_live_paper_session as session_module
from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1,
    Task8CanaryReportV1,
)
from services.certification.task8_live_paper_session import (
    run_task8_live_paper_session,
)


NOW = datetime(2026, 8, 6, 9, 30, tzinfo=timezone.utc)


def _dependencies(index: int) -> Task8CanaryDependenciesV1:
    return Task8CanaryDependenciesV1(
        branch="p10-two-market-weekend-readiness",
        commit="92368dc",
        preflight=lambda: {},
        parent_cycle=lambda: None,
        selected_planner=lambda _: None,
        monitoring=lambda: None,
        clock=lambda: NOW,
        id_factory=lambda: f"dependency-{index}",
        network_live_read_usage=False,
    )


def _report(
    index: int,
    *,
    passed: bool = True,
) -> Task8CanaryReportV1:
    blockers = () if passed else ("TEST_FAILURE",)
    return Task8CanaryReportV1(
        run_id=f"run-{index}",
        generated_at=NOW + timedelta(seconds=index),
        branch="p10-two-market-weekend-readiness",
        commit="92368dc",
        outer_status="PASSED" if passed else "FAILED",
        nifty_evaluation_count=1,
        nifty_terminal_status="COMPLETED",
        sensex_evaluation_count=1,
        sensex_terminal_status="COMPLETED",
        freshness_status="PASSED",
        timestamp_skew_status="PASSED",
        selected_market="NONE",
        rejected_market=None,
        rejection_reasons=(),
        final_action="NO_TRADE",
        planning_status="NOT_RUN",
        lifecycle_status="NOT_RUN",
        monitoring_status="NOT_RUN",
        persistence_status="NOT_RUN",
        journal_status="NOT_WRITTEN",
        paper_mode=True,
        network_live_read_usage=False,
        broker_submission_disabled=True,
        live_execution_ineligible=True,
        pass_blockers=blockers,
    )


def test_two_cycle_session_writes_each_cycle_and_summary(
    tmp_path,
    monkeypatch,
):
    reports = iter((_report(1), _report(2)))
    monkeypatch.setattr(
        session_module,
        "run_task8_live_paper_canary",
        lambda _: next(reports),
    )

    dependency_calls = []
    sleep_calls = []

    def factory():
        dependency_calls.append(len(dependency_calls) + 1)
        return _dependencies(len(dependency_calls))

    clock_values = iter(
        (
            NOW,
            NOW + timedelta(minutes=2),
        )
    )

    report, path = run_task8_live_paper_session(
        dependency_factory=factory,
        cycle_count=2,
        interval_seconds=12.0,
        output_directory=tmp_path,
        clock=lambda: next(clock_values),
        session_id_factory=lambda: "session-fixed",
        sleep_function=sleep_calls.append,
    )

    assert report.passed is True
    assert report.session_status == "PASSED"
    assert report.completed_cycle_count == 2
    assert report.total_nifty_evaluation_count == 2
    assert report.total_sensex_evaluation_count == 2
    assert dependency_calls == [1, 2]
    assert sleep_calls == [12.0]
    assert path.exists()

    cycle_files = sorted(
        tmp_path.glob("session-fixed-cycle-*.json")
    )
    assert len(cycle_files) == 2

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["session_status"] == "PASSED"
    assert payload["completed_cycle_count"] == 2


def test_failed_cycle_stops_session_immediately(
    tmp_path,
    monkeypatch,
):
    reports = iter(
        (
            _report(1),
            _report(2, passed=False),
            _report(3),
        )
    )
    monkeypatch.setattr(
        session_module,
        "run_task8_live_paper_canary",
        lambda _: next(reports),
    )

    dependency_calls = []
    sleep_calls = []

    def factory():
        dependency_calls.append(len(dependency_calls) + 1)
        return _dependencies(len(dependency_calls))

    report, _ = run_task8_live_paper_session(
        dependency_factory=factory,
        cycle_count=3,
        interval_seconds=5.0,
        output_directory=tmp_path,
        clock=lambda: NOW,
        session_id_factory=lambda: "session-failed",
        sleep_function=sleep_calls.append,
    )

    assert report.session_status == "FAILED"
    assert report.completed_cycle_count == 2
    assert report.passed_cycle_count == 1
    assert report.failed_cycle_count == 1
    assert dependency_calls == [1, 2]
    assert sleep_calls == [5.0]
    assert "CYCLE_002_FAILED" in report.blockers
    assert "TEST_FAILURE" in report.blockers


def test_keyboard_interrupt_writes_interrupted_summary(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        session_module,
        "run_task8_live_paper_canary",
        lambda _: _report(1),
    )

    def interrupt(_):
        raise KeyboardInterrupt

    report, path = run_task8_live_paper_session(
        dependency_factory=lambda: _dependencies(1),
        cycle_count=2,
        interval_seconds=5.0,
        output_directory=tmp_path,
        clock=lambda: NOW,
        session_id_factory=lambda: "session-interrupted",
        sleep_function=interrupt,
    )

    assert report.session_status == "INTERRUPTED"
    assert report.completed_cycle_count == 1
    assert report.failed_cycle_count == 0
    assert report.blockers == ("SESSION_INTERRUPTED",)
    assert path.exists()


def test_provider_exception_writes_failed_session_summary(
    tmp_path,
    monkeypatch,
):
    def fail(_):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        session_module,
        "run_task8_live_paper_canary",
        fail,
    )

    report, path = run_task8_live_paper_session(
        dependency_factory=lambda: _dependencies(1),
        cycle_count=2,
        interval_seconds=0,
        output_directory=tmp_path,
        clock=lambda: NOW,
        session_id_factory=lambda: "session-exception",
        sleep_function=lambda _: None,
    )

    assert report.session_status == "FAILED"
    assert report.completed_cycle_count == 0
    assert report.failed_cycle_count == 0
    assert "SESSION_EXECUTION_EXCEPTION" in report.blockers
    assert "SESSION_EXCEPTION_RUNTIMEERROR" in report.blockers
    assert path.exists()


def test_session_rejects_invalid_cycle_count(tmp_path):
    with pytest.raises(ValueError, match="cycle_count"):
        run_task8_live_paper_session(
            dependency_factory=lambda: _dependencies(1),
            cycle_count=0,
            interval_seconds=0,
            output_directory=tmp_path,
            clock=lambda: NOW,
            session_id_factory=lambda: "invalid",
            sleep_function=lambda _: None,
        )
def test_rate_limit_exception_is_classified_in_session_summary(
    tmp_path,
    monkeypatch,
):
    from services.broker.market_data_control import (
        BrokerMarketDataRequestError,
    )

    error = BrokerMarketDataRequestError(
        "historical-data",
        1,
        "rate_limited",
        "sanitized provider failure",
    )

    def fail(_):
        raise error

    monkeypatch.setattr(
        session_module,
        "run_task8_live_paper_canary",
        fail,
    )

    report, path = run_task8_live_paper_session(
        dependency_factory=lambda: _dependencies(1),
        cycle_count=2,
        interval_seconds=0,
        output_directory=tmp_path,
        clock=lambda: NOW,
        session_id_factory=lambda: "session-rate-limit",
        sleep_function=lambda _: None,
    )

    assert report.session_status == "FAILED"
    assert "SESSION_EXECUTION_EXCEPTION" in report.blockers
    assert "HISTORICAL-DATA_RATE_LIMITED" in report.blockers
    assert "PROVIDER_THROTTLED" in report.blockers
    assert path.exists()
