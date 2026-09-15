from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_provider_aligned_startup_preflight import (
    run_task9_provider_aligned_startup_preflight,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.contracts.provider_capability_registry_v1 import (
    ProviderCapabilityRegistryV1,
    default_provider_capability_registry,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9ProviderCapabilityReportV1,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    build_task9_runtime_config_snapshot,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


NOW = datetime(
    2026,
    8,
    17,
    10,
    0,
    tzinfo=timezone.utc,
)


def _pass(phase):
    return lambda: Task9StartupPreflightPhaseResultV1(
        phase,
        Task9StartupPreflightPhaseStatus.PASS,
        False,
        "TASK9864_INJECTED_PASS",
        None,
        NOW,
    )


def _checks():
    return {
        phase: _pass(phase)
        for phase
        in tuple(Task9StartupPreflightPhase)[2:-1]
    }


def _authorities():
    config = _config()

    return (
        config,
        build_task9_runtime_config_snapshot(
            config
        ),
        default_provider_capability_registry(),
        build_task9_angel_capability_session(),
        build_task9_provider_capability_report(
            config
        ),
    )


def test_aligned_startup_runs_existing_preflight_after_alignment():
    (
        config,
        snapshot,
        registry,
        angel,
        generic,
    ) = _authorities()

    result = run_task9_provider_aligned_startup_preflight(
        runtime_config=config,
        snapshot=snapshot,
        field_registry=registry,
        angel_capability_session=angel,
        capability_report=generic,
        preflight_id="task9864-aligned",
        observed_at=NOW,
        mode="LIVE_CERTIFICATION_STARTUP",
        checks=_checks(),
    )

    assert result.launch_approved is True

    assert tuple(
        item.phase
        for item in result.phase_results
    ) == tuple(Task9StartupPreflightPhase)


def test_offline_mode_never_becomes_launch_approved():
    (
        config,
        snapshot,
        registry,
        angel,
        generic,
    ) = _authorities()

    result = run_task9_provider_aligned_startup_preflight(
        runtime_config=config,
        snapshot=snapshot,
        field_registry=registry,
        angel_capability_session=angel,
        capability_report=generic,
        preflight_id="task9864-offline",
        observed_at=NOW,
        mode="OFFLINE_BUILD_VALIDATION",
        checks=_checks(),
    )

    assert result.launch_approved is False


def test_static_runtime_contradiction_blocks_before_preflight():
    (
        config,
        snapshot,
        registry,
        angel,
        generic,
    ) = _authorities()

    raw = {
        identity: dict(fields)
        for identity, fields
        in registry.capabilities.items()
    }

    raw[
        ("SENSEX", "BSE", "BFO")
    ]["greeks"] = "SUPPORTED"

    bad_registry = ProviderCapabilityRegistryV1(
        raw
    )

    called = []

    checks = _checks()

    first_key = next(iter(checks))

    checks[first_key] = (
        lambda: called.append(True)
    )

    with pytest.raises(
        ValueError,
        match="TASK9_FIELD_BFO_GREEKS_ALIGNMENT_MISMATCH",
    ):
        run_task9_provider_aligned_startup_preflight(
            runtime_config=config,
            snapshot=snapshot,
            field_registry=bad_registry,
            angel_capability_session=angel,
            capability_report=generic,
            preflight_id="task9864-bad-static",
            observed_at=NOW,
            mode="LIVE_CERTIFICATION_STARTUP",
            checks=checks,
        )

    assert called == []


def test_generic_capability_contradiction_blocks_before_preflight():
    (
        config,
        snapshot,
        registry,
        angel,
        generic,
    ) = _authorities()

    rows = list(generic.capability_states)

    target = next(
        index
        for index, state in enumerate(rows)
        if (
            state.market == "SENSEX"
            and state.exchange == "BFO"
            and state.capability.value
            == "OPTION_GREEKS"
        )
    )

    rows[target] = replace(
        rows[target],
        readiness_status="READY",
        live_proof_status="PROVEN",
        startup_semantic=None,
    )

    bad_generic = Task9ProviderCapabilityReportV1(
        runtime_config_id=generic.runtime_config_id,
        runtime_config_version=(
            generic.runtime_config_version
        ),
        capability_states=tuple(rows),
    )

    with pytest.raises(ValueError):
        run_task9_provider_aligned_startup_preflight(
            runtime_config=config,
            snapshot=snapshot,
            field_registry=registry,
            angel_capability_session=angel,
            capability_report=bad_generic,
            preflight_id="task9864-bad-generic",
            observed_at=NOW,
            mode="LIVE_CERTIFICATION_STARTUP",
            checks=_checks(),
        )


@pytest.mark.parametrize(
    "replacement,error",
    (
        ("runtime_config", "runtime_config"),
        ("snapshot", "snapshot"),
        ("field_registry", "field_registry"),
        (
            "angel_capability_session",
            "angel_capability_session",
        ),
        (
            "capability_report",
            "capability_report",
        ),
    ),
)
def test_wrong_authority_types_fail_closed(
    replacement,
    error,
):
    (
        config,
        snapshot,
        registry,
        angel,
        generic,
    ) = _authorities()

    kwargs = {
        "runtime_config": config,
        "snapshot": snapshot,
        "field_registry": registry,
        "angel_capability_session": angel,
        "capability_report": generic,
        "preflight_id": "task9864-types",
        "observed_at": NOW,
        "mode": "LIVE_CERTIFICATION_STARTUP",
        "checks": _checks(),
    }

    kwargs[replacement] = object()

    with pytest.raises(
        TypeError,
        match=error,
    ):
        run_task9_provider_aligned_startup_preflight(
            **kwargs
        )


def test_naive_observed_at_fails_closed():
    (
        config,
        snapshot,
        registry,
        angel,
        generic,
    ) = _authorities()

    with pytest.raises(
        ValueError,
        match="observed_at",
    ):
        run_task9_provider_aligned_startup_preflight(
            runtime_config=config,
            snapshot=snapshot,
            field_registry=registry,
            angel_capability_session=angel,
            capability_report=generic,
            preflight_id="task9864-naive",
            observed_at=datetime(
                2026,
                8,
                17,
                10,
                0,
            ),
            mode="LIVE_CERTIFICATION_STARTUP",
            checks=_checks(),
        )
