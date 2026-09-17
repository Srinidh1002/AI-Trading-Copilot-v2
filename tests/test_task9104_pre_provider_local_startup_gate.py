from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services.certification import (
    task9_production_startup_entrypoint as module,
)


NOW = datetime(
    2026,
    8,
    22,
    4,
    0,
    tzinfo=timezone.utc,
)


def _runtime():
    return SimpleNamespace(
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
        available_capital=10000.0,
    )


def test_local_gate_runs_before_default_provider_creation(
    monkeypatch,
):
    runtime = _runtime()
    snapshot = object()
    providers = object()
    calls = []

    monkeypatch.setattr(
        module,
        "Task9RuntimeConfigV1",
        type(runtime),
    )

    monkeypatch.setattr(
        module,
        "CertifiedRuntimeProviderBundleV1",
        type(providers),
    )

    monkeypatch.setattr(
        module,
        "build_task9_runtime_config_snapshot",
        lambda value: (
            calls.append(("snapshot", value))
            or snapshot
        ),
    )

    monkeypatch.setattr(
        module,
        "prepare_task9_startup_campaign_authority",
        lambda **kwargs: calls.append(
            (
                "campaign",
                kwargs["runtime_config"],
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "_run_task9_pre_provider_local_startup_gate",
        lambda **kwargs: calls.append(
            (
                "local_gate",
                kwargs["runtime_config"],
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "build_default_runtime_providers",
        lambda: (
            calls.append(("providers", None))
            or providers
        ),
    )

    monkeypatch.setattr(
        module,
        "capture_task9_production_startup_angel_facts",
        lambda **kwargs: (
            calls.append(("capture", kwargs["providers"]))
            or object()
        ),
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_live_proof_bundle_from_retained_captures",
        lambda **_: object(),
    )

    class Blocked:
        launch_approved = False

        def launcher_kwargs(self):
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_NOT_APPROVED"
            )

    monkeypatch.setattr(
        module,
        "default_provider_capability_registry",
        lambda: object(),
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_capability_session",
        lambda: object(),
    )

    monkeypatch.setattr(
        module,
        "run_task9_production_startup_bootstrap",
        lambda **_: Blocked(),
    )

    monkeypatch.setattr(
        module,
        "Task9LivePaperCertificationLauncher",
        lambda **_: pytest.fail(
            "blocked bootstrap must not launch"
        ),
    )

    result = (
        module.run_task9_production_startup_entrypoint(
            runtime_config=runtime,
            preflight_id="preflight",
            startup_capture_id="capture",
            providers=None,
            clock=lambda: NOW,
        )
    )

    assert result.launcher_stats is None

    assert tuple(
        item[0]
        for item in calls
    ) == (
        "snapshot",
        "campaign",
        "local_gate",
        "providers",
        "capture",
    )


def test_blocked_local_gate_prevents_default_provider_creation(
    monkeypatch,
):
    runtime = _runtime()
    snapshot = object()
    calls = []

    monkeypatch.setattr(
        module,
        "Task9RuntimeConfigV1",
        type(runtime),
    )

    monkeypatch.setattr(
        module,
        "build_task9_runtime_config_snapshot",
        lambda _: snapshot,
    )

    monkeypatch.setattr(
        module,
        "prepare_task9_startup_campaign_authority",
        lambda **_: calls.append(
            ("campaign", None)
        ),
    )

    def blocked_gate(**_):
        calls.append(
            ("local_gate", None)
        )

        raise ValueError(
            "TASK9_PRE_PROVIDER_LOCAL_PERSISTENCE_BLOCKED:"
            "PERSISTENCE_INTEGRITY_NOT_WRITABLE"
        )

    monkeypatch.setattr(
        module,
        "_run_task9_pre_provider_local_startup_gate",
        blocked_gate,
    )

    monkeypatch.setattr(
        module,
        "build_default_runtime_providers",
        lambda: pytest.fail(
            "provider construction must not occur"
        ),
    )

    with pytest.raises(
        ValueError,
        match="TASK9_PRE_PROVIDER_LOCAL_PERSISTENCE_BLOCKED",
    ):
        module.run_task9_production_startup_entrypoint(
            runtime_config=runtime,
            preflight_id="preflight",
            startup_capture_id="capture",
            providers=None,
            clock=lambda: NOW,
        )

    assert tuple(
        item[0]
        for item in calls
    ) == (
        "campaign",
        "local_gate",
    )


def test_injected_providers_still_pass_through_same_local_gate(
    monkeypatch,
):
    runtime = _runtime()
    snapshot = object()
    providers = object()
    calls = []

    monkeypatch.setattr(
        module,
        "Task9RuntimeConfigV1",
        type(runtime),
    )

    monkeypatch.setattr(
        module,
        "CertifiedRuntimeProviderBundleV1",
        type(providers),
    )

    monkeypatch.setattr(
        module,
        "build_task9_runtime_config_snapshot",
        lambda _: snapshot,
    )

    monkeypatch.setattr(
        module,
        "prepare_task9_startup_campaign_authority",
        lambda **_: calls.append(
            ("campaign", None)
        ),
    )

    monkeypatch.setattr(
        module,
        "_run_task9_pre_provider_local_startup_gate",
        lambda **_: calls.append(
            ("local_gate", None)
        ),
    )

    monkeypatch.setattr(
        module,
        "build_default_runtime_providers",
        lambda: pytest.fail(
            "injected providers must be preserved"
        ),
    )

    monkeypatch.setattr(
        module,
        "capture_task9_production_startup_angel_facts",
        lambda **kwargs: (
            calls.append(
                ("capture", kwargs["providers"])
            )
            or object()
        ),
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_live_proof_bundle_from_retained_captures",
        lambda **_: object(),
    )

    class Blocked:
        launch_approved = False

        def launcher_kwargs(self):
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_NOT_APPROVED"
            )

    monkeypatch.setattr(
        module,
        "default_provider_capability_registry",
        lambda: object(),
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_capability_session",
        lambda: object(),
    )

    monkeypatch.setattr(
        module,
        "run_task9_production_startup_bootstrap",
        lambda **_: Blocked(),
    )

    monkeypatch.setattr(
        module,
        "Task9LivePaperCertificationLauncher",
        lambda **_: pytest.fail(
            "blocked bootstrap must not launch"
        ),
    )

    result = (
        module.run_task9_production_startup_entrypoint(
            runtime_config=runtime,
            preflight_id="preflight",
            startup_capture_id="capture",
            providers=providers,
            clock=lambda: NOW,
        )
    )

    assert result.launcher_stats is None

    assert tuple(
        item[0]
        for item in calls
    ) == (
        "campaign",
        "local_gate",
        "capture",
    )

    assert calls[-1][1] is providers
