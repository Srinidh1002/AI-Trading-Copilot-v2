"""Focused, provider-free coverage for the Task 9 production launcher."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import services.certification.task9_live_paper_certification_launcher as launcher_module
from services.certification.task9_market_session_evaluator import (
    evaluate_task9_market_session,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    build_task9_market_session_policy,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9ParentEvidenceSessionClosedError,
    Task9LivePaperCertificationLauncher,
    Task9SingleProcessLock,
    load_or_create_task9_run_manifest,
)
from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerStore,
)
from services.certification.task9_startup_preflight_store import (
    Task9StartupPreflightStore,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
    Task9StartupPreflightResultV1,
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


_TEST_SESSION_POLICY = build_task9_market_session_policy(
    policy_id="task9-launcher-test-policy",
    policy_version="1",
    calendar_authority_ref="task9-launcher-test-calendar",
    nfo_new_entry_cutoff=__import__("datetime").time(15, 30),
    bfo_new_entry_cutoff=__import__("datetime").time(15, 30),
)


def _test_session_state_resolver(
    *,
    market,
    evaluated_at,
    market_date,
):
    non_trading = (
        market_date.weekday() >= 5
        or (market_date.month, market_date.day) == (1, 26)
    )

    aggregate = evaluate_task9_market_session(
        policy=_TEST_SESSION_POLICY,
        evaluated_at=evaluated_at,
        market_date=market_date,
        calendar_state=(
            "NON_TRADING_DAY"
            if non_trading
            else "TRADING_DAY"
        ),
    )

    expected = {
        "NIFTY": Task9MarketSegment.NFO_OPTIONS,
        "SENSEX": Task9MarketSegment.BFO_OPTIONS,
    }[market]

    return next(
        state
        for state in aggregate.states
        if state.segment is expected
    )


def _launcher(tmp_path, *, task9_evidence_factory, runtime_factory, now):
    root = tmp_path / "task9"

    preflight_id = "task916-launcher-preflight"
    snapshot_sha256 = "a" * 64
    snapshot_id = (
        "task9-runtime-config-"
        + snapshot_sha256
    )
    campaign_id = "task916-launcher-campaign"
    market_date = now.date()

    phase_results = tuple(
        Task9StartupPreflightPhaseResultV1(
            phase,
            Task9StartupPreflightPhaseStatus.PASS,
            False,
            "TASK916_TEST_PREFLIGHT_PASS",
            None,
            now,
        )
        for phase in Task9StartupPreflightPhase
    )

    receipt = Task9StartupPreflightResultV1(
        preflight_id=preflight_id,
        runtime_config_snapshot_id=snapshot_id,
        runtime_config_sha256=snapshot_sha256,
        campaign_id=campaign_id,
        market_date=market_date,
        official_run_id="task9-live-operator-run",
        run_classification="OFFICIAL_CERTIFICATION",
        started_at=now,
        completed_at=now,
        phase_results=phase_results,
    )

    preflight_store = Task9StartupPreflightStore(
        root
    )

    if preflight_store.get(
        preflight_id
    ) is None:
        preflight_store.save(
            receipt
        )

    value = Task9LivePaperCertificationLauncher(
        persistence_root=root,
        official_run_id="task9-live-operator-run",
        startup_preflight_id=preflight_id,
        runtime_config_snapshot_id=snapshot_id,
        runtime_config_sha256=snapshot_sha256,
        campaign_id=campaign_id,
        market_date=market_date,
        task9_evidence_dependencies_factory=task9_evidence_factory,
        runtime_factory=runtime_factory,
        session_state_resolver=_test_session_state_resolver,
        clock=lambda: now,
        sleep=lambda _: None,
    )

    value._startup_safety = lambda: None
    return value


def _ist(hour, minute=0):
    return datetime(2026, 8, 12, hour, minute, tzinfo=timezone(timedelta(hours=5, minutes=30)))


def test_launcher_forwards_runtime_authorities_only_to_compatible_factory(tmp_path):
    captured = {}

    def compatible_factory(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    value = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path,
        official_run_id="runtime-authority-run",
        startup_preflight_id="runtime-authority-preflight",
        runtime_config_snapshot_id="task9-runtime-config-" + "a" * 64,
        runtime_config_sha256="a" * 64,
        campaign_id="runtime-authority-campaign",
        market_date=_ist(10).date(),
        available_capital=12_345.0,
        risk_fraction=0.005,
        maximum_quantity=75,
        maximum_daily_loss_fraction=0.05,
        task9_evidence_dependencies_factory=compatible_factory,
    )

    assert value._build_task9_evidence_dependencies(lambda _: None) is not None
    assert captured["available_capital"] == 12_345.0
    assert captured["risk_fraction"] == 0.005
    assert captured["maximum_quantity"] == 75
    assert captured["maximum_daily_loss_fraction"] == 0.05

    def legacy_factory(*, task9_cycle_evidence_sink):
        assert callable(task9_cycle_evidence_sink)
        return SimpleNamespace()

    value.task9_evidence_dependencies_factory = legacy_factory
    assert value._build_task9_evidence_dependencies(lambda _: None) is not None


@pytest.mark.parametrize(
    "now",
    (
        datetime(2026, 8, 10, 8, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 15, 40, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 15, 45, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 21, 44, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 15, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 1, 26, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    ),
)
def test_parent_evidence_session_rejects_before_task8_or_provider_access(tmp_path, now):
    calls = []
    value = _launcher(
        tmp_path,
        task9_evidence_factory=lambda **_: calls.append("task8"),
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
    value = _launcher(tmp_path, task9_evidence_factory=lambda **_: pytest.fail("task8 must not run"), runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=_ist(15, 40))
    stats = value.run(cycle_interval_seconds=0)
    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_open_session_stale_parent_evidence_is_audited_skipped_and_next_attempt_succeeds(tmp_path):
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    runtime = _FakeTask9Runtime(calls=[])
    attempts = []
    sleeps = []

    def factory(*, task9_cycle_evidence_sink):
        def parent_cycle():
            attempts.append("parent")
            if len(attempts) == 1:
                raise ValueError("market observation is stale")
            for evidence in seed["handoffs"].values():
                task9_cycle_evidence_sink(evidence)
            return SimpleNamespace(
                selected_market=None,
                completed_at=seed["boundary"],
                parent_cycle_id="healthy-parent-cycle",
            )

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=parent_cycle,
            selected_planner=lambda _: pytest.fail("planner must not run"),
        )

    value = _launcher(
        tmp_path,
        task9_evidence_factory=factory,
        runtime_factory=lambda **_: runtime,
        now=_ist(10, 0),
    )
    value.sleep = sleeps.append
    stats = value.run(max_cycles=2, cycle_interval_seconds=17)

    root = tmp_path / "task9"
    skipped = list(root.glob("task9-skipped-parent-evidence-cycles/*.json"))
    assert stats.completed_cycles == 1
    assert stats.graceful_shutdown is True
    assert attempts == ["parent", "parent"]
    assert sleeps == [17.0]
    assert len(runtime.calls) == 1
    assert len(skipped) == 1
    assert not list(root.glob("prediction-ledger.json"))
    assert not list(root.glob("task9-cycle-results/*"))
    assert not (root / "task9-live-paper.lock").exists()


def test_bounded_stale_parent_attempt_returns_without_busy_loop_or_counting(tmp_path):
    calls = []

    def factory(**_):
        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=lambda: (_ for _ in ()).throw(
                ValueError("market observation is stale")
            ),
            selected_planner=lambda _: None,
        )

    value = _launcher(
        tmp_path,
        task9_evidence_factory=factory,
        runtime_factory=lambda **_: pytest.fail("runtime must not run"),
        now=_ist(10, 0),
    )
    value.sleep = calls.append
    stats = value.run(max_cycles=1, cycle_interval_seconds=17)

    root = tmp_path / "task9"
    assert stats.completed_cycles == 0
    assert calls == []
    assert len(list(root.glob("task9-skipped-parent-evidence-cycles/*.json"))) == 1
    assert not list(root.glob("task9-cycle-results/*"))
    assert not list(root.glob("prediction-ledger.json"))


def test_after_session_close_stale_parent_evidence_remains_graceful_without_audit(tmp_path):
    def closing_factory(**_):
        def parent_cycle():
            raise ValueError("market observation is stale")
        return SimpleNamespace(execution_mode="PAPER", broker_order_submission=False, live_execution_eligible=False, parent_cycle=parent_cycle, selected_planner=lambda _: None)

    value = _launcher(tmp_path / "closing", task9_evidence_factory=closing_factory, runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=_ist(15, 40))
    stats = value.run(cycle_interval_seconds=0)
    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True
    assert not (tmp_path / "closing" / "task9" / "task9-live-paper.lock").exists()
    assert not list((tmp_path / "closing" / "task9").glob("task9-skipped-parent-evidence-cycles/*"))


def test_stale_skip_preserves_already_retained_typed_provider_incident(tmp_path):
    value = _launcher(
        tmp_path,
        task9_evidence_factory=lambda **_: pytest.fail("task8 must not run"),
        runtime_factory=lambda **_: pytest.fail("runtime must not run"),
        now=_ist(10, 0),
    )
    incident_id = (
        "task9-provider-incident:observation:NSE:historical-data:5m:"
        "HISTORICAL-DATA_RATE_LIMITED"
    )
    value._record_skipped_stale_parent_evidence_cycle(
        handoffs={
            ("NIFTY", "NSE"): SimpleNamespace(
                provider_incidents=(SimpleNamespace(incident_id=incident_id),)
            )
        },
        observed_at=_ist(10, 0),
    )

    stored = Task9ExternalProviderBlockerStore(
        tmp_path / "task9"
    ).load("task9-live-operator-run")
    audit = next(
        (tmp_path / "task9" / "task9-skipped-parent-evidence-cycles").glob("*.json")
    ).read_text(encoding="utf-8")

    assert stored["occurrence_count"] == 1
    assert incident_id in audit
    assert "prediction_id" not in audit


def test_unrelated_value_error_after_session_remains_loud_and_releases_lock(tmp_path):
    now = [_ist(10, 0)]

    def factory(**_):
        def parent_cycle():
            now[0] = _ist(15, 30)
            raise ValueError("unrelated failure")
        return SimpleNamespace(execution_mode="PAPER", broker_order_submission=False, live_execution_eligible=False, parent_cycle=parent_cycle, selected_planner=lambda _: None)

    value = _launcher(tmp_path, task9_evidence_factory=factory, runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=now[0])
    value.clock = lambda: now[0]
    with pytest.raises(ValueError, match="unrelated failure"):
        value.run()
    assert not (tmp_path / "task9" / "task9-live-paper.lock").exists()


def test_continuous_session_close_preserves_already_completed_cycles(tmp_path):
    value = _launcher(tmp_path, task9_evidence_factory=lambda **_: pytest.fail("task8 must not run"), runtime_factory=lambda **_: pytest.fail("runtime must not run"), now=_ist(10, 0))
    calls = []

    def one_cycle(*_, **__):
        calls.append("cycle")
        if len(calls) == 2:
            raise Task9ParentEvidenceSessionClosedError(
                "TASK9_PARENT_EVIDENCE_SESSION_CLOSED"
            )
        return object()

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
        datetime(2026, 8, 10, 15, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        datetime(2026, 8, 10, 15, 39, tzinfo=timezone(timedelta(hours=5, minutes=30))),
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
        task9_evidence_factory=factory,
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
        task9_evidence_factory=_task8_factory(
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
        task9_evidence_factory=_task8_factory(handoffs=only_nifty, boundary=seed["boundary"]),
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
        task9_evidence_factory=_task8_factory(handoffs=seed["handoffs"], boundary=seed["boundary"]),
        runtime_factory=runtime_factory,
        now=seed["boundary"] - timedelta(minutes=2),
    )
    second = _launcher(
        tmp_path,
        task9_evidence_factory=_task8_factory(handoffs=seed["handoffs"], boundary=seed["boundary"]),
        runtime_factory=runtime_factory,
        now=seed["boundary"] - timedelta(minutes=1),
    )

    first.run(max_cycles=1)
    second.run(max_cycles=1)
    snapshot_sha256 = "a" * 64
    snapshot_id = (
        "task9-runtime-config-"
        + snapshot_sha256
    )

    manifest = load_or_create_task9_run_manifest(
        persistence_root=tmp_path / "task9",
        official_run_id="task9-live-operator-run",
        started_at=seed["boundary"],
        runtime_config_snapshot_id=snapshot_id,
        runtime_config_sha256=snapshot_sha256,
        campaign_id="task916-launcher-campaign",
        market_date=(
            seed["boundary"]
            - timedelta(minutes=2)
        ).date(),
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
        task9_evidence_factory=unsafe_factory,
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
        task9_evidence_factory=_task8_factory(
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
        task9_evidence_factory=_task8_factory(
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


def _launcher_diagnostics(value):
    path = value.persistence_root / "launcher-runtime-diagnostics.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_launcher_persists_continuous_attempt_completion_and_interrupt(tmp_path):
    now = _ist(10)
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    runtime = _FakeTask9Runtime(calls=[])
    value = _launcher(tmp_path, task9_evidence_factory=_task8_factory(handoffs=seed["handoffs"], boundary=now), runtime_factory=lambda **_: runtime, now=now)
    value.sleep = lambda _: (_ for _ in ()).throw(KeyboardInterrupt())

    stats = value.run(cycle_interval_seconds=0)

    assert stats.completed_cycles == 1
    assert [item["category"] for item in _launcher_diagnostics(value)] == ["ATTEMPT_STARTED", "CYCLE_COMPLETED", "INTERRUPTED"]


def test_launcher_persists_session_close_and_unexpected_failure_safely(tmp_path):
    closed = _launcher(tmp_path / "closed", task9_evidence_factory=lambda **_: pytest.fail("cycle"), runtime_factory=lambda **_: pytest.fail("runtime"), now=_ist(15, 40))
    with pytest.raises(Task9ParentEvidenceSessionClosedError):
        closed.run(max_cycles=1)
    assert [item["category"] for item in _launcher_diagnostics(closed)] == ["ATTEMPT_STARTED", "SESSION_CLOSED"]

    failed = _launcher(tmp_path / "failed", task9_evidence_factory=lambda **_: pytest.fail("cycle"), runtime_factory=lambda **_: pytest.fail("runtime"), now=_ist(10))
    failed._run_one_cycle = lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("Authorization: Bearer secret"))
    with pytest.raises(ValueError, match="Authorization"):
        failed.run(max_cycles=1)
    diagnostic = _launcher_diagnostics(failed)[-1]
    assert diagnostic["category"] == "UNEXPECTED_FAILURE"
    assert diagnostic["exception_class"] == "ValueError"
    assert "secret" not in json.dumps(diagnostic)


def test_launcher_persists_bounded_completion_and_preserves_prior_diagnostics(tmp_path):
    now = _ist(10)
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT", sensex_action="NO_TRADE")
    runtime = _FakeTask9Runtime(calls=[])
    value = _launcher(tmp_path, task9_evidence_factory=_task8_factory(handoffs=seed["handoffs"], boundary=now), runtime_factory=lambda **_: runtime, now=now)
    assert value.run(max_cycles=1).completed_cycles == 1
    first = _launcher_diagnostics(value)
    assert [item["category"] for item in first] == ["ATTEMPT_STARTED", "CYCLE_COMPLETED", "RUN_COMPLETED"]
    restarted = _launcher(tmp_path, task9_evidence_factory=_task8_factory(handoffs=seed["handoffs"], boundary=now), runtime_factory=lambda **_: runtime, now=now)
    assert _launcher_diagnostics(restarted) == first


def test_runbook_has_the_dedicated_task9_command_and_rejects_legacy_credit():
    runbook = Path("docs/PAPER_RUNTIME_RUNBOOK.md").read_text(encoding="utf-8")

    task9_section = runbook.split(
        "## Legacy certified runtime launcher",
        1,
    )[0]

    assert (
        "services.certification."
        "task9_production_startup_entrypoint"
        in task9_section
    )

    assert (
        "services.certification."
        "task9_live_paper_certification_launcher"
        not in task9_section
    )
    assert "--automated-paper" in runbook
    assert "--official-run-id task9-live-20260810-a" in runbook
    assert "Legacy certified runtime launcher — not Task 9 /100 authority" in runbook
    assert "WAIT and NO_TRADE remain separately persisted" in runbook
    assert "never increment `/100`" in runbook


def _stale_full_quote_runtime_error():
    cause = ValueError(
        "provider quote timestamp is stale."
    )

    error = RuntimeError(
        "SENSEX FULL quote contains invalid "
        "provider timestamp evidence."
    )

    error.__cause__ = cause

    return error


def test_open_session_stale_full_quote_runtime_error_is_audited_skip(
    tmp_path,
):
    attempts = []

    def factory(**_):
        def parent_cycle():
            attempts.append("parent")
            raise _stale_full_quote_runtime_error()

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=parent_cycle,
            selected_planner=lambda _: None,
        )

    value = _launcher(
        tmp_path,
        task9_evidence_factory=factory,
        runtime_factory=lambda **_: pytest.fail(
            "runtime must not run"
        ),
        now=_ist(10, 0),
    )

    stats = value.run(
        max_cycles=1,
        cycle_interval_seconds=0,
    )

    root = tmp_path / "task9"

    assert attempts == ["parent"]
    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True

    skipped = list(
        root.glob(
            "task9-skipped-parent-evidence-cycles/*.json"
        )
    )

    assert len(skipped) == 1
    assert not list(
        root.glob("task9-cycle-results/*")
    )


def test_stale_full_quote_race_to_session_close_becomes_graceful(
    tmp_path,
):
    now = [_ist(15, 39)]

    def factory(**_):
        def parent_cycle():
            now[0] = _ist(15, 40)
            raise _stale_full_quote_runtime_error()

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=parent_cycle,
            selected_planner=lambda _: None,
        )

    value = _launcher(
        tmp_path,
        task9_evidence_factory=factory,
        runtime_factory=lambda **_: pytest.fail(
            "runtime must not run"
        ),
        now=now[0],
    )

    value.clock = lambda: now[0]

    drained = []

    value._drain_expired_abstentions = (
        lambda manifest, *, evaluated_at:
        drained.append(
            (
                manifest.official_run_id,
                evaluated_at,
            )
        )
    )

    stats = value.run(
        cycle_interval_seconds=0,
    )

    root = tmp_path / "task9"

    assert stats.completed_cycles == 0
    assert stats.graceful_shutdown is True
    assert len(drained) == 1

    assert not list(
        root.glob(
            "task9-skipped-parent-evidence-cycles/*"
        )
    )


def test_unrelated_runtime_error_after_session_remains_loud(
    tmp_path,
):
    now = [_ist(10, 0)]

    def factory(**_):
        def parent_cycle():
            now[0] = _ist(15, 40)

            raise RuntimeError(
                "unrelated runtime failure"
            )

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
            parent_cycle=parent_cycle,
            selected_planner=lambda _: None,
        )

    value = _launcher(
        tmp_path,
        task9_evidence_factory=factory,
        runtime_factory=lambda **_: pytest.fail(
            "runtime must not run"
        ),
        now=now[0],
    )

    value.clock = lambda: now[0]

    with pytest.raises(
        RuntimeError,
        match="unrelated runtime failure",
    ):
        value.run()

    assert not (
        tmp_path
        / "task9"
        / "task9-live-paper.lock"
    ).exists()


def test_bounded_session_close_after_completed_work_drains_gracefully(
    tmp_path,
):
    value = _launcher(
        tmp_path,
        task9_evidence_factory=lambda **_:
        pytest.fail("task8 must not run"),
        runtime_factory=lambda **_:
        pytest.fail("runtime must not run"),
        now=_ist(10, 0),
    )

    calls = []

    def one_cycle(*_, **__):
        calls.append("cycle")

        if len(calls) == 2:
            raise Task9ParentEvidenceSessionClosedError(
                "TASK9_PARENT_EVIDENCE_SESSION_CLOSED"
            )

        return object()

    value._run_one_cycle = one_cycle

    drained = []

    value._drain_expired_abstentions = (
        lambda manifest, *, evaluated_at:
        drained.append(
            manifest.official_run_id
        )
    )

    stats = value.run(
        max_cycles=150,
        cycle_interval_seconds=0,
    )

    assert calls == [
        "cycle",
        "cycle",
    ]

    assert stats.completed_cycles == 1
    assert stats.graceful_shutdown is True
    assert len(drained) == 1

    assert not (
        tmp_path
        / "task9"
        / "task9-live-paper.lock"
    ).exists()

def test_task9104_close_drain_refresh_publishes_final_persisted_progress():
    import inspect

    from services.certification.task9_live_paper_certification_launcher import (
        Task9LivePaperCertificationLauncher,
    )

    source = inspect.getsource(
        Task9LivePaperCertificationLauncher._drain_expired_abstentions
    )

    authority_index = source.index(
        "Task9CertificationPublicationAuthority("
    )

    refresh_index = source.index(
        ").refresh(",
        authority_index,
    )

    publish_index = source.index(
        "self._publish_after_close_drain_progress(",
        refresh_index,
    )

    return_index = source.index(
        "return drain_state",
        publish_index,
    )

    assert (
        authority_index
        < refresh_index
        < publish_index
        < return_index
    )


def test_task9104_close_drain_dashboard_publish_does_not_fake_cycle_result():
    import inspect

    from services.certification.task9_live_paper_certification_launcher import (
        Task9LivePaperCertificationLauncher,
    )

    source = inspect.getsource(
        Task9LivePaperCertificationLauncher._publish_after_close_drain_progress
    )

    assert (
        ".publish_persisted_progress("
        in source
    )

    assert (
        "Task9LivePaperCycleResultV1("
        not in source
    )

    assert "parent_cycle(" not in source
    assert "selected_planner(" not in source


def test_task9104_persisted_progress_publish_boundary_validates_before_io(
    tmp_path,
):
    from datetime import datetime, timezone

    import pytest

    from services.dashboard_publication.dashboard_publication_store import (
        DashboardPublicationStore,
    )
    from services.dashboard_publication.task9_dashboard_publication_publisher import (
        Task9DashboardPublicationPublisher,
    )

    publisher = Task9DashboardPublicationPublisher(
        store=DashboardPublicationStore(),
        persistence_root=tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="source_id",
    ):
        publisher.publish_persisted_progress(
            source_id="",
            published_at=datetime.now(
                timezone.utc
            ),
        )

    with pytest.raises(
        ValueError,
        match="published_at",
    ):
        publisher.publish_persisted_progress(
            source_id="close-drain",
            published_at=datetime(
                2026,
                8,
                20,
                15,
                40,
            ),
        )


def test_task9104_cycle_dashboard_publish_still_uses_shared_progress_boundary():
    import inspect

    from services.dashboard_publication.task9_dashboard_publication_publisher import (
        Task9DashboardPublicationPublisher,
    )

    source = inspect.getsource(
        Task9DashboardPublicationPublisher.publish
    )

    assert "self._publish_progress(" in source
    assert "result.cycle_id" in source
    assert "result.completed_at" in source

def test_task9104_cli_defaults_to_canonical_task9_persistence_root(
    monkeypatch,
):
    from types import SimpleNamespace

    import services.certification.task9_live_paper_certification_launcher as module

    captured = {}

    class FakeLauncher:
        def __init__(
            self,
            **kwargs,
        ):
            captured.update(kwargs)

        def run(
            self,
            *,
            max_cycles=None,
            cycle_interval_seconds=60.0,
        ):
            captured["max_cycles"] = max_cycles
            captured[
                "cycle_interval_seconds"
            ] = cycle_interval_seconds

            return SimpleNamespace(
                completed_cycles=0,
                graceful_shutdown=True,
                official_run_id=(
                    "task9-live-20260821-test"
                ),
            )

    monkeypatch.setattr(
        module,
        "Task9LivePaperCertificationLauncher",
        FakeLauncher,
    )

    exit_code = module.main(
        [
            "--official-run-id",
            "task9-live-20260821-test",
            "--startup-preflight-id",
            "preflight-test",
            "--runtime-config-snapshot-id",
            "snapshot-test",
            "--runtime-config-sha256",
            "a" * 64,
            "--campaign-id",
            "campaign-test",
            "--market-date",
            "2026-08-21",
            "--automated-paper",
            "--max-cycles",
            "1",
            "--cycle-interval-seconds",
            "0",
        ]
    )

    assert exit_code == 0

    assert (
        captured["persistence_root"]
        == "data/task9"
    )

    assert (
        captured["official_run_id"]
        == "task9-live-20260821-test"
    )
