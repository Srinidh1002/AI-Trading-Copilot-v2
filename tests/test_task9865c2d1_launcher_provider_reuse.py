from types import SimpleNamespace

from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperCertificationLauncher,
)


def _bare_launcher(
    *,
    factory,
    providers,
):
    launcher = object.__new__(
        Task9LivePaperCertificationLauncher
    )

    launcher.task9_evidence_dependencies_factory = factory
    launcher.providers = providers

    # This fixture deliberately bypasses __init__ to isolate provider
    # forwarding behavior, so initialize the runtime-authority fields that
    # production __init__ now guarantees.
    launcher.available_capital = 10_000.0
    launcher.risk_fraction = 0.01
    launcher.maximum_quantity = None
    launcher.maximum_daily_loss_fraction = None

    launcher.option_oi_change_authority = (
        object()
    )

    return launcher


def test_launcher_passes_exact_precomposed_provider_bundle():
    providers = object()
    received = []

    def factory(
        *,
        task9_cycle_evidence_sink,
        providers=None,
        **kwargs,
    ):
        received.append(
            {
                "sink": (
                    task9_cycle_evidence_sink
                ),
                "providers": providers,
                "kwargs": kwargs,
            }
        )

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
        )

    launcher = _bare_launcher(
        factory=factory,
        providers=providers,
    )

    sink = object()

    result = launcher._build_task9_evidence_dependencies(
        sink
    )

    assert len(received) == 1

    assert (
        received[0]["providers"]
        is providers
    )

    assert (
        received[0]["sink"]
        is sink
    )

    assert result.execution_mode == "PAPER"
    assert result.broker_order_submission is False
    assert result.live_execution_eligible is False


def test_launcher_does_not_force_providers_into_legacy_factory():
    providers = object()
    calls = []

    def legacy_factory(
        *,
        task9_cycle_evidence_sink,
    ):
        calls.append(
            task9_cycle_evidence_sink
        )

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
        )

    launcher = _bare_launcher(
        factory=legacy_factory,
        providers=providers,
    )

    sink = object()

    result = launcher._build_task9_evidence_dependencies(
        sink
    )

    assert calls == [sink]

    assert result.execution_mode == "PAPER"


def test_launcher_omits_provider_argument_when_none():
    received = []

    def factory(
        *,
        task9_cycle_evidence_sink,
        providers="NOT_SET",
    ):
        received.append(
            providers
        )

        return SimpleNamespace(
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
        )

    launcher = _bare_launcher(
        factory=factory,
        providers=None,
    )

    launcher._build_task9_evidence_dependencies(
        object()
    )

    assert received == ["NOT_SET"]
