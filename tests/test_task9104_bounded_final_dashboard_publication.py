from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import services.certification.task9_live_paper_certification_launcher as launcher_module


NOW = datetime(
    2026,
    8,
    21,
    9,
    0,
    tzinfo=timezone.utc,
)


class _FakeLock:
    def __init__(self, events):
        self.events = events

    def acquire(self):
        self.events.append("lock:acquire")

    def release(self):
        self.events.append("lock:release")


def _bare_launcher(tmp_path, events):
    launcher = object.__new__(
        launcher_module.Task9LivePaperCertificationLauncher
    )

    launcher.persistence_root = tmp_path
    launcher.official_run_id = "task9104-run"
    launcher.run_classification = "OFFICIAL_CERTIFICATION"

    launcher.runtime_config_snapshot_id = (
        "task9-runtime-config-"
        + ("a" * 64)
    )
    launcher.runtime_config_sha256 = "a" * 64

    launcher.campaign_id = "task9104-campaign"
    launcher.market_date = NOW.date()

    launcher.live_stream_root = (
        tmp_path / "live_stream"
    )

    launcher.session_state_resolver = (
        lambda **_: object()
    )

    launcher.available_capital = 10000.0
    launcher.sleep = lambda _: None

    launcher._now = lambda: NOW

    launcher._validate_startup_preflight_receipt = (
        lambda: events.append("preflight")
    )

    launcher._startup_safety = (
        lambda: events.append("safety")
    )

    return launcher


def test_bounded_normal_completion_publishes_persisted_progress_after_cycle(
    tmp_path,
    monkeypatch,
):
    events = []

    launcher = _bare_launcher(
        tmp_path,
        events,
    )

    manifest = SimpleNamespace(
        official_run_id="task9104-run",
        official_start_at=NOW,
        run_classification="OFFICIAL_CERTIFICATION",
    )

    monkeypatch.setattr(
        launcher_module,
        "Task9ExternalProviderBlockerStore",
        lambda *_: SimpleNamespace(
            load=lambda *_: None
        ),
    )

    monkeypatch.setattr(
        launcher_module,
        "build_task9_precomposed_timeframe_provider",
        lambda **_: object(),
    )

    monkeypatch.setattr(
        launcher_module,
        "Task9SingleProcessLock",
        lambda **_: _FakeLock(events),
    )

    monkeypatch.setattr(
        launcher_module,
        "load_or_create_task9_run_manifest",
        lambda **_: manifest,
    )

    monkeypatch.setattr(
        launcher_module,
        "run_task9_restart_recovery_startup",
        lambda **_: events.append("recovery"),
    )

    launcher._run_one_cycle = (
        lambda *_args, **_kwargs:
        events.append("cycle")
        or object()
    )

    launcher._publish_after_bounded_progress = (
        lambda *_args, **_kwargs:
        events.append("final-progress-publication")
    )

    stats = launcher.run(
        max_cycles=1,
        cycle_interval_seconds=0,
    )

    assert stats.completed_cycles == 1
    assert stats.graceful_shutdown is True

    assert events.index(
        "cycle"
    ) < events.index(
        "final-progress-publication"
    )

    assert events.index(
        "final-progress-publication"
    ) < events.index(
        "lock:release"
    )

    assert events.count(
        "final-progress-publication"
    ) == 1


def test_bounded_final_helper_uses_persisted_progress_publisher(
    tmp_path,
    monkeypatch,
):
    events = []

    launcher = _bare_launcher(
        tmp_path,
        events,
    )

    manifest = SimpleNamespace(
        official_run_id="task9104-run",
    )

    calls = {}

    persistent_store = object()
    dashboard_store = object()

    monkeypatch.setattr(
        launcher_module,
        "DashboardPublicationPersistentStore",
        lambda root: (
            calls.setdefault(
                "persistent_root",
                root,
            )
            or persistent_store
        ),
    )

    # Avoid truth-value behavior from the setdefault expression above.
    def persistent_factory(root):
        calls["persistent_root"] = root
        return persistent_store

    monkeypatch.setattr(
        launcher_module,
        "DashboardPublicationPersistentStore",
        persistent_factory,
    )

    def dashboard_factory(*, persistent_store):
        calls[
            "dashboard_persistent_store"
        ] = persistent_store
        return dashboard_store

    monkeypatch.setattr(
        launcher_module,
        "DashboardPublicationStore",
        dashboard_factory,
    )

    class _Publisher:
        def __init__(
            self,
            *,
            store,
            persistence_root,
        ):
            calls["publisher_store"] = store
            calls[
                "publisher_root"
            ] = persistence_root

        def publish_persisted_progress(
            self,
            *,
            source_id,
            published_at,
        ):
            calls["source_id"] = source_id
            calls[
                "published_at"
            ] = published_at

    monkeypatch.setattr(
        launcher_module,
        "Task9DashboardPublicationPublisher",
        _Publisher,
    )

    launcher._publish_after_bounded_progress(
        manifest,
        evaluated_at=NOW,
    )

    assert calls[
        "persistent_root"
    ] == tmp_path

    assert calls[
        "dashboard_persistent_store"
    ] is persistent_store

    assert calls[
        "publisher_store"
    ] is dashboard_store

    assert calls[
        "publisher_root"
    ] == tmp_path

    assert calls[
        "source_id"
    ].startswith(
        "task9-bounded-final:"
        "task9104-run:"
    )

    assert calls[
        "published_at"
    ] == NOW
