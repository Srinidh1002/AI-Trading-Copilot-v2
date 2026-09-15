from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import services.certification.task9_production_startup_entrypoint as module


NOW = datetime(
    2026,
    8,
    17,
    6,
    30,
    tzinfo=timezone.utc,
)


def _runtime():
    return SimpleNamespace(
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
        available_capital=10000.0,
        trade_risk_fraction=0.005,
        maximum_quantity=75,
        maximum_daily_loss_fraction=0.05,
    )


def test_approved_bootstrap_constructs_launcher_after_canonical_gate(
    monkeypatch,
):
    runtime = _runtime()
    providers = object()
    snapshot = object()
    retained = object()
    bundle = object()
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
            snapshot
            if value is runtime
            else pytest.fail(
                "wrong runtime"
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "capture_task9_production_startup_angel_facts",
        lambda **kwargs: (
            calls.append(
                (
                    "capture",
                    kwargs["providers"],
                )
            )
            or retained
        ),
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_live_proof_bundle_from_retained_captures",
        lambda **kwargs: (
            calls.append(
                (
                    "proofs",
                    kwargs["captures"],
                )
            )
            or bundle
        ),
    )

    class Bootstrap:
        launch_approved = True

        def launcher_kwargs(self):
            calls.append(
                (
                    "launcher_kwargs",
                    None,
                )
            )

            return {
                "persistence_root": "root",
                "live_stream_root": "stream",
                "official_run_id": "run",
                "startup_preflight_id": "preflight",
                "runtime_config_snapshot_id": "snapshot",
                "runtime_config_sha256": "a" * 64,
                "campaign_id": "campaign",
                "market_date": NOW.date(),
                "run_classification": (
                    "OFFICIAL_CERTIFICATION"
                ),
            }

    bootstrap = Bootstrap()

    monkeypatch.setattr(
        module,
        "prepare_task9_startup_campaign_authority",
        lambda **kwargs: calls.append(
            (
                "campaign_init",
                kwargs["runtime_config"],
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "_run_task9_pre_provider_local_startup_gate",
        lambda **_: None,
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
        lambda **kwargs: (
            calls.append(
                (
                    "bootstrap",
                    kwargs[
                        "live_proof_bundle"
                    ],
                )
            )
            or bootstrap
        ),
    )

    class Launcher:
        def __init__(
            self,
            **kwargs,
        ):
            calls.append(
                (
                    "launcher",
                    kwargs["providers"],
                )
            )
            assert (
                kwargs["providers"]
                is providers
            )
            assert kwargs["available_capital"] == 10000.0
            assert kwargs["risk_fraction"] == 0.005
            assert kwargs["maximum_quantity"] == 75
            assert kwargs["maximum_daily_loss_fraction"] == 0.05

        def run(
            self,
            **kwargs,
        ):
            calls.append(
                (
                    "run",
                    kwargs,
                )
            )
            return "stats"

    monkeypatch.setattr(
        module,
        "Task9LivePaperCertificationLauncher",
        Launcher,
    )

    result = (
        module.run_task9_production_startup_entrypoint(
            runtime_config=runtime,
            preflight_id="preflight",
            startup_capture_id="capture",
            providers=providers,
            max_cycles=1,
            cycle_interval_seconds=0,
            clock=lambda: NOW,
        )
    )

    assert result.bootstrap is bootstrap
    assert result.launcher_stats == "stats"

    assert tuple(
        item[0]
        for item in calls
    ) == (
        "campaign_init",
        "capture",
        "proofs",
        "bootstrap",
        "launcher_kwargs",
        "launcher",
        "run",
    )


def test_blocked_bootstrap_never_constructs_launcher(
    monkeypatch,
):
    runtime = _runtime()
    providers = object()

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
        lambda _: object(),
    )

    monkeypatch.setattr(
        module,
        "capture_task9_production_startup_angel_facts",
        lambda **_: object(),
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_live_proof_bundle_from_retained_captures",
        lambda **_: object(),
    )

    monkeypatch.setattr(
        module,
        "prepare_task9_startup_campaign_authority",
        lambda **_: None,
    )

    monkeypatch.setattr(
        module,
        "_run_task9_pre_provider_local_startup_gate",
        lambda **_: None,
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

    class Blocked:
        launch_approved = False

        def launcher_kwargs(self):
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_NOT_APPROVED"
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
    assert result.bootstrap.launch_approved is False


def test_entrypoint_rejects_non_paper_runtime(
    monkeypatch,
):
    runtime = _runtime()
    runtime.execution_mode = "LIVE"

    monkeypatch.setattr(
        module,
        "Task9RuntimeConfigV1",
        type(runtime),
    )

    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        module.run_task9_production_startup_entrypoint(
            runtime_config=runtime,
            preflight_id="preflight",
            startup_capture_id="capture",
            providers=object(),
            clock=lambda: NOW,
        )



def test_retryable_option_acquisition_failure_routes_to_blocked_bootstrap(
    monkeypatch,
):
    runtime = _runtime()
    providers = object()
    snapshot = object()
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
            snapshot
            if value is runtime
            else pytest.fail(
                "wrong runtime"
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "prepare_task9_startup_campaign_authority",
        lambda **kwargs: calls.append(
            (
                "campaign_init",
                kwargs["runtime_config"],
            )
        ),
    )

    monkeypatch.setattr(
        module,
        "_run_task9_pre_provider_local_startup_gate",
        lambda **_: None,
    )

    def blocked_capture(**kwargs):
        calls.append(
            (
                "capture",
                kwargs["providers"],
            )
        )

        raise RuntimeError(
            "TASK9_STARTUP_NIFTY_OPTION_CAPTURE_BLOCKED:"
            "OPTION_CAPTURE_RUNTIMEERROR"
        )

    monkeypatch.setattr(
        module,
        "capture_task9_production_startup_angel_facts",
        blocked_capture,
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_live_proof_bundle_from_retained_captures",
        lambda **_: pytest.fail(
            "proof bundle must not be fabricated "
            "after acquisition failure"
        ),
    )

    registry = object()
    capability_session = object()

    monkeypatch.setattr(
        module,
        "default_provider_capability_registry",
        lambda: registry,
    )

    monkeypatch.setattr(
        module,
        "build_task9_angel_capability_session",
        lambda: capability_session,
    )

    class BlockedBootstrap:
        launch_approved = False

    blocked_bootstrap = (
        BlockedBootstrap()
    )

    def fake_bootstrap(**kwargs):
        calls.append(
            (
                "bootstrap",
                kwargs[
                    "live_proof_bundle"
                ],
                kwargs[
                    "startup_acquisition_failure"
                ],
            )
        )

        assert (
            kwargs["runtime_config"]
            is runtime
        )
        assert (
            kwargs["snapshot"]
            is snapshot
        )
        assert (
            kwargs["field_registry"]
            is registry
        )
        assert (
            kwargs[
                "angel_capability_session"
            ]
            is capability_session
        )
        assert (
            kwargs["live_proof_bundle"]
            is None
        )
        assert (
            kwargs[
                "startup_acquisition_failure"
            ]
            == (
                "TASK9_STARTUP_NIFTY_OPTION_CAPTURE_BLOCKED:"
                "OPTION_CAPTURE_RUNTIMEERROR"
            )
        )

        return blocked_bootstrap

    monkeypatch.setattr(
        module,
        "run_task9_production_startup_bootstrap",
        fake_bootstrap,
    )

    monkeypatch.setattr(
        module,
        "Task9LivePaperCertificationLauncher",
        lambda **_: pytest.fail(
            "retryable acquisition block "
            "must never construct launcher"
        ),
    )

    result = (
        module.run_task9_production_startup_entrypoint(
            runtime_config=runtime,
            preflight_id="preflight",
            startup_capture_id="capture",
            providers=providers,
            max_cycles=1,
            cycle_interval_seconds=0,
            clock=lambda: NOW,
        )
    )

    assert (
        result.bootstrap
        is blocked_bootstrap
    )
    assert (
        result.launcher_stats
        is None
    )

    assert tuple(
        item[0]
        for item in calls
    ) == (
        "campaign_init",
        "capture",
        "bootstrap",
    )
