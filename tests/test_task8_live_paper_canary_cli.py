"""Tests for Task 8 canary CLI failure evidence."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from services.broker.market_data_control import (
    BrokerMarketDataRequestError,
)
from services.certification import (
    task8_live_paper_canary_cli as cli,
)
from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1,
)


NOW = datetime(
    2026,
    8,
    6,
    10,
    0,
    tzinfo=timezone.utc,
)


def _dependencies(exception):
    def parent_cycle():
        raise exception

    return Task8CanaryDependenciesV1(
        branch="p10-two-market-weekend-readiness",
        commit="e69bef7",
        preflight=lambda: {
            "branch_worktree": True,
            "paper_mode": True,
            "live_execution_ineligible": True,
            "broker_submission_disabled": True,
            "nifty_provider": True,
            "sensex_provider": True,
            "routing": True,
            "persistence_writable": True,
            "journal_writable": True,
            "emergency_halt": True,
            "market_session_checked": True,
            "credentials_present": True,
            "journal_status": "WRITABLE",
        },
        parent_cycle=parent_cycle,
        selected_planner=lambda _: None,
        monitoring=lambda: None,
        clock=lambda: NOW,
        id_factory=lambda: "unused",
    )


def test_rate_limit_writes_non_countable_failure_evidence(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "rate-limit.json"

    error = BrokerMarketDataRequestError(
        "historical-data",
        1,
        "rate_limited",
        "sanitized provider failure",
    )

    monkeypatch.setattr(
        cli,
        "_load",
        lambda _: lambda: _dependencies(error),
    )
    monkeypatch.setattr(
        cli,
        "_utc_now",
        lambda: NOW,
    )
    monkeypatch.setattr(
        cli,
        "_failure_run_id",
        lambda: "task8-failure-fixed",
    )

    exit_code = cli.main(
        ["--output", str(output)]
    )

    payload = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert exit_code == 2
    assert payload["status"] == "FAILED"
    assert payload["countable"] is False
    assert payload["completed_market_count"] == 0
    assert payload["provider_throttled"] is True
    assert (
        payload["failure_reason"]
        == "HISTORICAL-DATA_RATE_LIMITED"
    )
    assert payload["paper_mode"] is True
    assert (
        payload["broker_submission_enabled"]
        is False
    )
    assert (
        payload["live_execution_eligible"]
        is False
    )


def test_generic_exception_is_sanitized(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "generic.json"

    monkeypatch.setattr(
        cli,
        "_load",
        lambda _: lambda: _dependencies(
            RuntimeError(
                "secret header and credential text"
            )
        ),
    )
    monkeypatch.setattr(
        cli,
        "_utc_now",
        lambda: NOW,
    )
    monkeypatch.setattr(
        cli,
        "_failure_run_id",
        lambda: "task8-failure-fixed",
    )

    exit_code = cli.main(
        ["--output", str(output)]
    )

    raw = output.read_text(encoding="utf-8")
    payload = json.loads(raw)

    assert exit_code == 2
    assert payload["provider_throttled"] is False
    assert (
        payload["failure_reason"]
        == "EXECUTION_EXCEPTION"
    )
    assert "secret" not in raw.lower()
    assert "credential" not in raw.lower()


def test_failure_evidence_path_is_immutable(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "existing.json"
    output.write_text(
        "{}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "_load",
        lambda _: lambda: _dependencies(
            RuntimeError("failure")
        ),
    )
    monkeypatch.setattr(
        cli,
        "_utc_now",
        lambda: NOW,
    )
    monkeypatch.setattr(
        cli,
        "_failure_run_id",
        lambda: "task8-failure-fixed",
    )

    assert (
        cli.main(["--output", str(output)])
        == 2
    )
    assert (
        output.read_text(encoding="utf-8")
        == "{}\n"
    )
