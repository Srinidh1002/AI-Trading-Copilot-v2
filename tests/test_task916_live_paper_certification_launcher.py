"""Focused, provider-free coverage for the Task 9 production launcher."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import services.certification.task9_live_paper_certification_launcher as launcher_module
from services.certification.task9_live_paper_certification_launcher import (
    Task9ParentEvidenceSessionClosedError,
    Task9LivePaperCertificationLauncher,
    Task9SingleProcessLock,
    load_or_create_task9_run_manifest,
)
from tests.test_task916_production_child_evidence_authority import _runtime


@dataclass
class _FakeTask9Runtime:
    calls: list[tuple[str, datetime]]
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def run_cycle(self, *, cycle_id, evaluated_at):
        self.calls.append((cycle_id, evaluated_at))
        return SimpleNamespace(cycle_id=cycle_id)


def _task8_factory(*, handoffs, boundary, selected_market=None, interrupt=False):
    def factory(*, task9_cycle_evidence_sink):
        def parent_cycle():
            if interrupt:
                raise KeyboardInterrupt
            if selected_market is None:
                for evidence in handoffs.values():
                    task9_cycle_evidence_sink(evidence)
            return SimpleNamespace(
                selected_market=selected_market,
                completed_at=boundary,
                parent_cycle_id="authoritative-parent-cycle",
            )

        def selected_planner(identity):
            assert identity == selected_market
            for evidence in handoffs.values():
                task9_cycle_evidence_sink(evidence)
            return SimpleNamespace()

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=parent_cycle,
            selected_planner=selected_planner,
        )

    return factory


def _launcher(tmp_path, *, task8_factory, runtime_factory, now):
    value = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path / "task9",
        official_run_id="task9-live-operator-run",
        task8_dependencies_factory=task8_factory,
        runtime_factory=runtime_factory,
        clock=lambda: now,
        sleep=lambda _: None,
    )
    value._startup_safety = lambda: None
    return value


def _ist(hour, minute=0):
    return datetime(2026, 8, 12, hour, minute, tzinfo=timezone(timedelta(hours=5, minutes=30)))


@pytest.mark.parametrize(
    "now",
    (
        datetime(2026, 8, 10, 8, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 15, 35, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 21, 44, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 15, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 1, 26, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ),
)
def test_parent_evidence_session_rejects_before_task8_or_provider_access(tmp_path, now):
    calls = []
    value = _launcher(
        tmp_path,
        task8_factory=lambda **_: calls.append("task8"),
        runtime_factory=lambda **_: calls.append("runtime"),
        now=now,
    )

    with pytest.raises(Task9ParentEvidenceSessionClosedError, match="TASK9_PARENT_EVIDENCE_SESSION_CLOSED"):
        value.run(max_cycles=1)

    root = tmp_path / "task9"
    assert calls == []
    assert not (root / "task9-live-paper.lock").exists()
    assert not list(root.glob("task9-cycle-results/*"))
    assert not list(root.glob("task9-external-provider-*.json"))
    assert not list(root.glob("*progress*"))


def test_continuous_outside_session_returns_gracefully_and_releases_lock(tmp_path):
    value = _launcher(tmp_path, task8_factory=lambda **_: pytest.fail("task8 must not run"), runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=_ist(15, 30))
    stats = value.run(cycle_interval_seconds=0)
    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_exact_stale_parent_evidence_propagates_intraday_but_closes_continuously_after_session(tmp_path):
    now = [_ist(10, 0)]

    def factory(**_):
        return SimpleNamespace(execution_mode="PAPER", broker_order_submission=False, live_execution_eligible=False, parent_cycle=lambda: (_ for _ in ()).throw(ValueError("market observation is stale")), selected_planner=lambda _: None)

    value = _launcher(tmp_path, task8_factory=factory, runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=now[0])
    value.clock = lambda: now[0]
    with pytest.raises(ValueError, match="market observation is stale"):
        value.run(max_cycles=1)
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()

    def closing_factory(**_):
        def parent_cycle():
            now[0] = _ist(15, 30)
            raise ValueError("market observation is stale")
        return SimpleNamespace(execution_mode="PAPER", broker_order_submission=False, live_execution_eligible=False, parent_cycle=parent_cycle, selected_planner=lambda _: None)

    now[0] = _ist(10, 0)
    value = _launcher(tmp_path / "closing", task8_factory=closing_factory, runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=now[0])
    value.clock = lambda: now[0]
    stats = value.run(cycle_interval_seconds=0)
    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_unrelated_value_error_after_session_remains_loud_and_releases_lock(tmp_path):
    now = [_ist(10, 0)]

    def factory(**_):
        def parent_cycle():
            now[0] = _ist(15, 30)
            raise ValueError("unrelated failure")
        return SimpleNamespace(execution_mode="PAPER", broker_order_submission=False, live_execution_eligible=False, parent_cycle=parent_cycle, selected_planner=lambda _: None)

    value = _launcher(tmp_path, task8_factory=factory, runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=now[0])
    value.clock = lambda: now[0]
    with pytest.raises(ValueError, match="unrelated failure"):
        value.run()
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_continuous_session_close_preserves_already_completed_cycles(tmp_path):
    value = _launcher(tmp_path, task8_factory=lambda **_: pytest.fail("task8 must not run"), runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=_ist(10, 0))
    calls = []

    def one_cycle(*_, **__):
        calls.append("cycle")
        if len(calls) == 2:
            raise Task9ParentEvidenceSessionClosedError("TASK9_PARENT_EVIDENCE_SESSION_CLOSED")

    value._run_one_cycle = one_cycle
    stats = value.run(cycle_interval_seconds=0)
    assert stats.completed_cycles == 1
    assert stats.graceful_shutdown is True
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


@pytest.mark.parametrize(
    "now",
    (
        datetime(2026, 8, 10, 9, 15, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 15, 29, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ),
)
def test_parent_evidence_session_allows_open_and_pre_close_boundary(tmp_path, now):
    calls = []

    def parent_cycle():
        calls.append("parent")
        raise RuntimeError("parent reached")

    def factory(**_):
        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=parent_cycle,
            selected_planner=lambda _: pytest.fail("planner must not run"),
        )

    value = _launcher(
        tmp_path,
        task8_factory=factory,
        runtime_factory=lambda **_: pytest.fail("runtime must not be built"),
        now=now,
    )

    with pytest.raises(RuntimeError, match="parent reached"):
        value.run(max_cycles=1)

    assert calls == ["parent"]
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_launcher_collects_exact_two_market_handoffs_and_calls_task9_runtime_once(
    tmp_path,
):
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    runtime = _FakeTask9Runtime(calls=[])
    received = []

    def runtime_factory(**kwargs):
        received.append(kwargs)
        return runtime

    value = _launcher(
        tmp_path,
        task8_factory=_task8_factory(
            handoffs=seed["handoffs"], boundary=seed["boundary"]
        ),
        runtime_factory=runtime_factory,
        now=seed["boundary"] - timedelta(seconds=1),
    )

    stats = value.run(max_cycles=1, cycle_interval_seconds=0)

    assert stats.completed_cycles == 1
    assert len(received) == len(runtime.calls) == 1
    assert received[0]["cycle_evidence_by_market"][("NIFTY", "NSE")] is seed["handoffs"][("NIFTY", "NSE")]
    assert received[0]["cycle_evidence_by_market"][("SENSEX", "BSE")] is seed["handoffs"][("SENSEX", "BSE")]
    assert received[0]["persistence_root"] == tmp_path / "task9"
    assert runtime.calls[0][1] == seed["boundary"]


def test_launcher_requires_one_handoff_for_each_market_and_releases_lock(tmp_path):
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    only_nifty = {("NIFTY", "NSE"): seed["handoffs"][("NIFTY", "NSE")]}
    value = _launcher(
        tmp_path,
        task8_factory=_task8_factory(handoffs=only_nifty, boundary=seed["boundary"]),
        runtime_factory=lambda **_: pytest.fail("runtime must not be built"),
        now=seed["boundary"],
    )

    with pytest.raises(RuntimeError, match="exact NIFTY and SENSEX"):
        value.run(max_cycles=1)

    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_official_run_identity_and_start_time_remain_stable_across_restart(tmp_path):
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    calls = []

    def runtime_factory(**kwargs):
        calls.append(kwargs)
        return _FakeTask9Runtime(calls=[])

    first = _launcher(
        tmp_path,
        task8_factory=_task8_factory(handoffs=seed["handoffs"], boundary=seed["boundary"]),
        runtime_factory=runtime_factory,
        now=seed["boundary"] - timedelta(minutes=2),
    )
    second = _launcher(
        tmp_path,
        task8_factory=_task8_factory(handoffs=seed["handoffs"], boundary=seed["boundary"]),
        runtime_factory=runtime_factory,
        now=seed["boundary"] - timedelta(minutes=1),
    )

    first.run(max_cycles=1)
    second.run(max_cycles=1)
    manifest = load_or_create_task9_run_manifest(
        persistence_root=tmp_path / "task9",
        official_run_id="task9-live-operator-run",
        started_at=seed["boundary"],
    )

    assert manifest.official_start_at == seed["boundary"] - timedelta(minutes=2)
    assert {item["official_run_id"] for item in calls} == {"task9-live-operator-run"}
    assert {item["persistence_root"] for item in calls} == {tmp_path / "task9"}


def test_second_launcher_lock_fails_closed(tmp_path):
    root = tmp_path / "task9"
    first = Task9SingleProcessLock(
        persistence_root=root,
        official_run_id="task9-live-operator-run",
    )
    second = Task9SingleProcessLock(
        persistence_root=root,
        official_run_id="task9-live-operator-run",
    )

    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="lock already exists"):
            second.acquire()
    finally:
        first.release()


def test_launcher_rejects_a_nonpaper_task8_composition_before_acquisition(
    tmp_path,
):
    now = datetime(2026, 8, 10, 9, 15, tzinfo=timezone.utc)

    def unsafe_factory(*, task9_cycle_evidence_sink):
        return SimpleNamespace(
            execution_mode="LIVE",
            broker_order_submission=True,
            live_execution_eligible=True,
            parent_cycle=lambda: pytest.fail("parent acquisition must not run"),
            selected_planner=lambda _: pytest.fail("planner must not run"),
        )

    value = _launcher(
        tmp_path,
        task8_factory=unsafe_factory,
        runtime_factory=lambda **_: pytest.fail("runtime must not be built"),
        now=now,
    )
    manifest = load_or_create_task9_run_manifest(
        persistence_root=tmp_path / "task9",
        official_run_id="task9-live-operator-run",
        started_at=now,
    )

    with pytest.raises(ValueError, match="PAPER-only"):
        value._run_one_cycle(manifest)


def test_ctrl_c_stops_before_a_new_cycle_and_preserves_manifest(tmp_path):
    now = datetime(2026, 8, 10, 9, 15, tzinfo=timezone.utc)
    value = _launcher(
        tmp_path,
        task8_factory=_task8_factory(
            handoffs={}, boundary=now, interrupt=True
        ),
        runtime_factory=lambda **_: pytest.fail("runtime must not be built"),
        now=now,
    )

    stats = value.run(max_cycles=1)

    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True
    assert (tmp_path / "task9" / "task9-live-paper-run.json").exists()
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_launcher_leaves_cutoff_and_monitoring_decisions_to_task9_runner(tmp_path):
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    runtime = _FakeTask9Runtime(calls=[])
    after_cutoff = seed["boundary"].replace(hour=15, minute=21, second=0)
    value = _launcher(
        tmp_path,
        task8_factory=_task8_factory(
            handoffs=seed["handoffs"], boundary=after_cutoff
        ),
        runtime_factory=lambda **_: runtime,
        now=after_cutoff,
    )

    value.run(max_cycles=1)

    assert runtime.calls == [
        ("task9:task9-live-operator-run:authoritative-parent-cycle", after_cutoff)
    ]
    source = Path(launcher_module.__file__).read_text(encoding="utf-8")
    assert "validate_session_timestamp" not in source
    assert "entry_allowed" not in source


def test_launcher_has_no_legacy_launcher_broker_or_progress_mutation_dependency():
    source = Path(launcher_module.__file__).read_text(encoding="utf-8")

    assert "task9_live_paper_production_composition" in source
    assert "certified_runtime_launcher" not in source
    assert "broker_order" not in source.replace("broker_order_submission", "")
    assert "task9_live_paper_certification_progress_builder" not in source


def test_runbook_has_the_dedicated_task9_command_and_rejects_legacy_credit():
    runbook = Path("docs/PAPER_RUNTIME_RUNBOOK.md").read_text(encoding="utf-8")

    assert (
        "-m services.certification.task9_live_paper_certification_launcher"
        in runbook
    )
    assert "--automated-paper" in runbook
    assert "--official-run-id task9-live-20260810-a" in runbook
    assert "Legacy certified runtime launcher — not Task 9 /100 authority" in runbook
    assert "WAIT` and `NO_TRADE` remain separate analytics" in runbook
