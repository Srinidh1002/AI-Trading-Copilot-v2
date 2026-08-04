"""APT-1 control-plane tests.  Runtime/persistence fixtures remain PAPER-only."""

from datetime import datetime, timezone

import pytest

from services.paper_orchestration.certified_new_entry_input_factory import (
    CertifiedNewEntryInputFactory,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputFactory,
)
from services.paper_orchestration.certified_runtime_composition import (
    AutomatedPaperAuthorityBundleV1,
    CertifiedRuntimeCompositionSettingsV1,
    CertifiedRuntimeProviderBundleV1,
    build_certified_launcher,
)
from services.paper_orchestration.certified_runtime_launcher import main
from services.paper_orchestration.certified_runtime_launcher import (
    CertifiedPaperRuntimeLauncher,
)
from services.paper_orchestration.certified_runtime_safety import (
    validate_no_broker_submission_guard,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


class Analysis:
    def analyse(self, **kwargs):
        return {"decision": "NEUTRAL", "timeframes": {}}


class NoActionOptions:
    def analyse(self, **kwargs):
        return {"decision": "NO_TRADE", "reasons": ["fixture"]}


def _providers():
    return CertifiedRuntimeProviderBundleV1(
        quote_reader=lambda *_: {
            "ltp": 25000.0,
            "market_timestamp": NOW,
            "received_at": NOW,
            "timestamp_source": "TEST",
        },
        analysis_pipeline=Analysis(),
        option_decision_pipeline=NoActionOptions(),
        clock=lambda: NOW,
    )


def _authorities():
    # These exact existing factories are intentionally not invoked by the
    # NO_ACTION fixture; dedicated P6/P7 fixture tests exercise them in full.
    return AutomatedPaperAuthorityBundleV1(
        p6_input_factory=object.__new__(CertifiedP6InputFactory),
        new_entry_input_factory=object.__new__(CertifiedNewEntryInputFactory),
    )


def _paper_config(monkeypatch):
    monkeypatch.setattr("config.BROKER", "PAPER")
    monkeypatch.setattr("config.ENABLE_PAPER_TRADING", True)
    monkeypatch.setattr("config.ENABLE_LIVE_TRADING", False)


def test_cli_modes_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        main([
            "--factory",
            "services.paper_orchestration.certified_runtime_composition:build_certified_launcher",
            "--observe-only",
            "--automated-paper",
        ])


def test_cli_automated_paper_passes_automated_composition_flag(
    tmp_path,
    monkeypatch,
):
    _paper_config(monkeypatch)
    captured = {}

    def factory(*, automated_paper=False):
        captured["automated_paper"] = automated_paper
        return build_certified_launcher(
            settings=CertifiedRuntimeCompositionSettingsV1(
                data_root=tmp_path / "runtime",
                log_path=tmp_path / "runtime" / "runtime.jsonl",
                observe_only=False,
                automated_paper=True,
                automated_authorities=_authorities(),
            ),
            providers=_providers(),
            automated_paper=automated_paper,
        )

    class Launcher:
        def __init__(self, *, composition, clock):
            assert composition.automated_paper is True
            assert composition.controls.snapshot().observe_only is False

        def run(self, *, max_cycles=None):
            return {}

    monkeypatch.setattr(
        "services.paper_orchestration.certified_runtime_launcher._load_factory",
        lambda _: factory,
    )
    monkeypatch.setattr(
        "services.paper_orchestration.certified_runtime_launcher.CertifiedPaperRuntimeLauncher",
        Launcher,
    )

    assert main([
        "--factory", "test:factory", "--automated-paper",
    ]) == 0
    assert captured["automated_paper"] is True


@pytest.mark.parametrize("emergency_halt", (False, True))
def test_standard_cli_default_factory_builds_automated_paper_composition(
    monkeypatch,
    emergency_halt,
):
    _paper_config(monkeypatch)
    captured = {}

    class Launcher:
        def __init__(self, *, composition, clock):
            captured["composition"] = composition

        def run(self, *, max_cycles=None):
            return {}

    monkeypatch.setattr(
        "services.paper_orchestration.certified_runtime_composition."
        "build_default_runtime_providers",
        _providers,
    )
    monkeypatch.setattr(
        "services.paper_orchestration.certified_runtime_launcher."
        "CertifiedPaperRuntimeLauncher",
        Launcher,
    )

    args = [
        "--factory",
        "services.paper_orchestration.certified_runtime_composition:"
        "build_certified_launcher",
        "--automated-paper",
    ]
    if emergency_halt:
        args.append("--emergency-halt")

    assert main(args) == 0
    snapshot = captured["composition"].controls.snapshot()
    assert captured["composition"].automated_paper is True
    assert snapshot.observe_only is False
    assert snapshot.emergency_halt is emergency_halt
    assert snapshot.new_entries_allowed is not emergency_halt


def test_explicit_automated_settings_without_authorities_fail_closed():
    with pytest.raises(TypeError, match="automated_authorities"):
        CertifiedRuntimeCompositionSettingsV1(
            observe_only=False,
            automated_paper=True,
        )


def test_default_observe_only_is_unchanged(tmp_path, monkeypatch):
    _paper_config(monkeypatch)
    composition = build_certified_launcher(
        settings=CertifiedRuntimeCompositionSettingsV1(
            data_root=tmp_path / "runtime",
            log_path=tmp_path / "runtime" / "runtime.jsonl",
        ),
        providers=_providers(),
    )
    snapshot = composition.controls.snapshot()
    assert composition.automated_paper is False
    assert snapshot.observe_only is True
    assert snapshot.new_entries_allowed is False
    assert composition.broker_order_submission is False


def test_automated_paper_control_snapshot_allows_entries(tmp_path, monkeypatch):
    _paper_config(monkeypatch)
    composition = build_certified_launcher(
        settings=CertifiedRuntimeCompositionSettingsV1(
            data_root=tmp_path / "runtime",
            log_path=tmp_path / "runtime" / "runtime.jsonl",
            observe_only=False,
            automated_paper=True,
            automated_authorities=_authorities(),
        ),
        providers=_providers(),
        automated_paper=True,
    )
    snapshot = composition.controls.snapshot()
    assert composition.automated_paper is True
    assert snapshot.observe_only is False
    assert snapshot.new_entries_allowed is True
    assert snapshot.position_monitoring_allowed is True
    assert composition.execution_mode == "PAPER"
    assert composition.live_execution_eligible is False


def test_emergency_halt_overrides_automated_entry_permission(tmp_path, monkeypatch):
    _paper_config(monkeypatch)
    composition = build_certified_launcher(
        settings=CertifiedRuntimeCompositionSettingsV1(
            data_root=tmp_path / "runtime",
            log_path=tmp_path / "runtime" / "runtime.jsonl",
            observe_only=False,
            emergency_halt=True,
            automated_paper=True,
            automated_authorities=_authorities(),
        ),
        providers=_providers(),
        automated_paper=True,
    )
    snapshot = composition.controls.snapshot()
    assert snapshot.emergency_halt is True
    assert snapshot.new_entries_allowed is False
    assert snapshot.position_monitoring_allowed is True


def test_broker_submission_guard_rejects_enabled_submission():
    with pytest.raises(RuntimeError, match="broker order submission"):
        validate_no_broker_submission_guard(broker_order_submission=True)


def test_automated_mode_can_safely_return_no_action(tmp_path, monkeypatch):
    _paper_config(monkeypatch)
    composition = build_certified_launcher(
        settings=CertifiedRuntimeCompositionSettingsV1(
            data_root=tmp_path / "runtime",
            log_path=tmp_path / "runtime" / "runtime.jsonl",
            observe_only=False,
            automated_paper=True,
            automated_authorities=_authorities(),
            interval_seconds=0.001,
        ),
        providers=_providers(),
        automated_paper=True,
    )
    result = CertifiedPaperRuntimeLauncher(
        composition=composition,
        clock=lambda: NOW,
    ).run(max_cycles=1)
    assert result["cycles_completed"] == 1
    assert composition.controls.snapshot().new_entries_allowed is True
