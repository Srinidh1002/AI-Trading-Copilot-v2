"""Canonical Task 9 provider-aligned startup composition.

This module owns no provider facts.

It binds the already-existing authorities in the only valid startup order:

    runtime config + reproducibility snapshot
        -> static provider field registry
        -> Angel capability session
        -> generic provider capability report
        -> cross-authority alignment validation
        -> 12-phase startup preflight

No provider acquisition occurs here.
No broker order authority exists here.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_provider_field_capability_alignment import (
    validate_task9_provider_field_runtime_alignment,
)
from services.certification.task9_startup_preflight_orchestrator import (
    Task9StartupPreflightMode,
    Task9StartupPreflightOrchestrator,
)
from services.contracts.provider_capability_registry_v1 import (
    ProviderCapabilityRegistryV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9ProviderCapabilityReportV1,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9RuntimeConfigSnapshotV1,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightResultV1,
)


def run_task9_provider_aligned_startup_preflight(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    field_registry: ProviderCapabilityRegistryV1,
    angel_capability_session: Task9AngelCapabilitySessionV1,
    capability_report: Task9ProviderCapabilityReportV1,
    preflight_id: str,
    observed_at: datetime,
    mode: Task9StartupPreflightMode | str,
    checks: Mapping[
        Task9StartupPreflightPhase,
        Callable[[], Task9StartupPreflightPhaseResultV1],
    ]
    | None = None,
) -> Task9StartupPreflightResultV1:
    """Validate provider authorities before executing startup preflight."""

    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if type(snapshot) is not Task9RuntimeConfigSnapshotV1:
        raise TypeError("snapshot")

    if type(field_registry) is not ProviderCapabilityRegistryV1:
        raise TypeError("field_registry")

    if (
        type(angel_capability_session)
        is not Task9AngelCapabilitySessionV1
    ):
        raise TypeError("angel_capability_session")

    if type(capability_report) is not Task9ProviderCapabilityReportV1:
        raise TypeError("capability_report")

    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at")

    if type(preflight_id) is not str or not preflight_id.strip():
        raise ValueError("preflight_id")

    # 9.86.1 + 9.86.2 + 9.86.3 are static runtime invariants.
    #
    # The Angel capability session is the static provider authority. Live
    # proof projection deliberately advances the generic report from
    # PENDING -> PROVEN/READY without mutating that static authority.
    # Therefore strict Angel/generic equality must be checked against the
    # untouched generic baseline, never against the post-proof report.
    static_report = build_task9_provider_capability_report(
        runtime_config
    )

    validate_task9_provider_field_runtime_alignment(
        registry=field_registry,
        angel=angel_capability_session,
        generic=static_report,
    )

    if (
        capability_report.runtime_config_id
        != static_report.runtime_config_id
        or capability_report.runtime_config_version
        != static_report.runtime_config_version
    ):
        raise ValueError(
            "TASK9_PROJECTED_PROVIDER_REPORT_RUNTIME_IDENTITY_MISMATCH"
        )

    static_rows = {
        (
            row.provider_family,
            row.capability,
            row.market,
            row.exchange,
        ): row
        for row in static_report.capability_states
    }

    projected_rows = {
        (
            row.provider_family,
            row.capability,
            row.market,
            row.exchange,
        ): row
        for row in capability_report.capability_states
    }

    if set(projected_rows) != set(static_rows):
        raise ValueError(
            "TASK9_PROJECTED_PROVIDER_REPORT_STATIC_SHAPE_MISMATCH"
        )

    for identity, baseline in static_rows.items():
        projected = projected_rows[identity]

        # Live projection may change only live/evidence state. It cannot
        # rewrite static provider documentation, implementation or feature
        # authority.
        if (
            projected.required
            != baseline.required
            or projected.feature_intent
            != baseline.feature_intent
            or projected.documentation_status
            != baseline.documentation_status
            or projected.implementation_status
            != baseline.implementation_status
            or projected.freshness_policy_ref
            != baseline.freshness_policy_ref
            or projected.rate_limit_policy_ref
            != baseline.rate_limit_policy_ref
        ):
            raise ValueError(
                "TASK9_PROJECTED_PROVIDER_REPORT_STATIC_AUTHORITY_MUTATED"
            )

        # Live proof may advance only capabilities whose static authority
        # permits runtime proof. A statically unsupported capability must
        # preserve its canonical baseline live/evidence semantics exactly.
        static_unsupported = (
            baseline.documentation_status.value
            == "UNSUPPORTED"
            or baseline.implementation_status.value
            == "UNSUPPORTED"
            or baseline.readiness_status.value
            == "UNSUPPORTED"
        )

        if static_unsupported and (
            projected.readiness_status
            != baseline.readiness_status
            or projected.live_proof_status
            != baseline.live_proof_status
            or projected.startup_semantic
            != baseline.startup_semantic
        ):
            raise ValueError(
                "TASK9_PROJECTED_UNSUPPORTED_CAPABILITY_PROMOTED:"
                f"{identity}"
            )

    orchestrator = Task9StartupPreflightOrchestrator(
        runtime_config=runtime_config,
        snapshot=snapshot,
        capability_report=capability_report,
        mode=mode,
        checks=checks,
    )

    return orchestrator.run(
        preflight_id=preflight_id.strip(),
        observed_at=observed_at,
    )


__all__ = (
    "run_task9_provider_aligned_startup_preflight",
)
