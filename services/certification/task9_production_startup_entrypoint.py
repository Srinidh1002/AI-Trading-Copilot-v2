"""Canonical Task 9 production startup entrypoint.

One production path:
runtime authorities
-> one shared provider bundle
-> one startup acquisition
-> A1-A7 proof bundle
-> canonical startup preflight
-> approved durable provenance
-> Task 9 PAPER launcher using the same provider bundle.

No alternate approval boolean, no manually supplied preflight receipt,
no second provider owner, and no broker/order authority exist here.
"""

from __future__ import annotations

import argparse
import uuid

from dataclasses import dataclass
from datetime import date, datetime, timezone, time
from pathlib import Path
from typing import Callable

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_live_collector_session_resolver import (
    build_task9_live_collector_session_resolver,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9LauncherStatsV1,
    Task9LivePaperCertificationLauncher,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.certification.task9_production_startup_acquisition import (
    capture_task9_production_startup_angel_facts,
)
from services.certification.task9_startup_campaign_transition import (
    prepare_task9_startup_campaign_authority,
)
from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_campaign_index_store import (
    Task9CampaignIndexStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_campaign_preflight_bridge import (
    build_task9_campaign_preflight_phase,
)
from services.certification.task9_dashboard_active_campaign_authority import (
    build_task9_dashboard_active_campaign_preflight_phase,
    synchronize_task9_dashboard_active_campaign_projection,
)
from services.certification.task9_persistence_writability_probe import (
    produce_task9_persistence_writability_proof,
)
from services.certification.task9_persistence_writability_readiness import (
    build_task9_persistence_writability_preflight_phase,
)
from services.certification.task9_runtime_safety_proof_producer import (
    produce_task9_runtime_safety_proof,
)
from services.certification.task9_runtime_safety_readiness import (
    build_task9_runtime_safety_preflight_phase,
)
from services.certification.task9_production_startup_bootstrap import (
    Task9ProductionStartupBootstrapResultV1,
    run_task9_production_startup_bootstrap,
)
from services.certification.task9_production_startup_proof_assembler import (
    build_task9_angel_live_proof_bundle_from_retained_captures,
)
from services.contracts.provider_capability_registry_v1 import (
    default_provider_capability_registry,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    build_task9_runtime_config_snapshot,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
    build_default_runtime_providers,
)


@dataclass(frozen=True, slots=True)
class Task9ProductionStartupEntrypointResultV1:
    bootstrap: Task9ProductionStartupBootstrapResultV1
    launcher_stats: Task9LauncherStatsV1 | None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_production_startup_entrypoint_result.v1"
    )

    def __post_init__(self) -> None:
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 production entrypoint must remain PAPER-only"
            )

        if (
            self.schema_version
            != "task9_production_startup_entrypoint_result.v1"
        ):
            raise ValueError(
                "schema_version"
            )


def _run_task9_pre_provider_local_startup_gate(
    *,
    runtime_config,
    snapshot,
    observed_at,
    live_stream_root=None,
    repository_broker="PAPER",
    repository_enable_paper_trading=True,
    repository_enable_live_trading=False,
):
    """Fail closed on local startup authority before provider construction."""

    persistence_root = Path(
        runtime_config.authoritative_persistence_root
    )

    stream_root = (
        Path(live_stream_root)
        if live_stream_root is not None
        else persistence_root / "live_stream"
    )

    runtime_safety_proof = (
        produce_task9_runtime_safety_proof(
            runtime_config=runtime_config,
            repository_broker=repository_broker,
            repository_enable_paper_trading=(
                repository_enable_paper_trading
            ),
            repository_enable_live_trading=(
                repository_enable_live_trading
            ),
            observed_at=observed_at,
        )
    )

    runtime_phase = (
        build_task9_runtime_safety_preflight_phase(
            proof=runtime_safety_proof
        )
    )

    if runtime_phase.blocking:
        raise ValueError(
            "TASK9_PRE_PROVIDER_LOCAL_RUNTIME_SAFETY_BLOCKED:"
            f"{runtime_phase.reason_code}"
        )

    persistence_proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=persistence_root,
            live_stream_root=stream_root,
            observed_at=observed_at,
        )
    )

    persistence_phase = (
        build_task9_persistence_writability_preflight_phase(
            proof=persistence_proof
        )
    )

    if persistence_phase.blocking:
        raise ValueError(
            "TASK9_PRE_PROVIDER_LOCAL_PERSISTENCE_BLOCKED:"
            f"{persistence_phase.reason_code}"
        )

    manifest_store = Task9CampaignManifestStore(
        persistence_root
    )

    pointer_store = Task9ActiveCampaignPointerStore(
        persistence_root
    )

    index_store = Task9CampaignIndexStore(
        persistence_root
    )

    campaign_index = index_store.get(
        runtime_config.campaign_id
    )

    campaign_phase = (
        build_task9_campaign_preflight_phase(
            runtime_config=runtime_config,
            manifest_store=manifest_store,
            pointer_store=pointer_store,
            observed_at=observed_at,
            runtime_config_snapshot_id=(
                snapshot.snapshot_id
            ),
            runtime_config_sha256=(
                snapshot.content_sha256
            ),
            campaign_index=campaign_index,
        )
    )

    if campaign_phase.blocking:
        raise ValueError(
            "TASK9_PRE_PROVIDER_LOCAL_CAMPAIGN_BLOCKED:"
            f"{campaign_phase.reason_code}"
        )

    dashboard_projection = (
        synchronize_task9_dashboard_active_campaign_projection(
            persistence_root=persistence_root,
            expected_campaign_id=(
                runtime_config.campaign_id
            ),
            expected_market_date=(
                runtime_config.market_date
            ),
            expected_official_run_id=(
                runtime_config.official_run_id
            ),
            expected_runtime_config_snapshot_id=(
                snapshot.snapshot_id
            ),
            expected_runtime_config_sha256=(
                snapshot.content_sha256
            ),
            observed_at=observed_at,
        )
    )

    dashboard_phase = (
        build_task9_dashboard_active_campaign_preflight_phase(
            projection=dashboard_projection,
            expected_campaign_id=(
                runtime_config.campaign_id
            ),
            expected_market_date=(
                runtime_config.market_date
            ),
            expected_official_run_id=(
                runtime_config.official_run_id
            ),
            expected_runtime_config_snapshot_id=(
                snapshot.snapshot_id
            ),
            expected_runtime_config_sha256=(
                snapshot.content_sha256
            ),
            observed_at=observed_at,
        )
    )

    if dashboard_phase.blocking:
        raise ValueError(
            "TASK9_PRE_PROVIDER_LOCAL_DASHBOARD_BLOCKED:"
            f"{dashboard_phase.reason_code}"
        )

    return {
        "runtime_safety": runtime_phase,
        "persistence": persistence_phase,
        "campaign": campaign_phase,
        "dashboard": dashboard_phase,
    }


def run_task9_production_startup_entrypoint(
    *,
    runtime_config: Task9RuntimeConfigV1,
    preflight_id: str,
    startup_capture_id: str,
    live_stream_root: str | Path | None = None,
    max_cycles: int | None = None,
    cycle_interval_seconds: float = 60.0,
    providers: CertifiedRuntimeProviderBundleV1 | None = None,
    clock: Callable[[], datetime] = (
        lambda: datetime.now(timezone.utc)
    ),
) -> Task9ProductionStartupEntrypointResultV1:
    """Run canonical Task 9 PAPER startup and launch only if approved."""

    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if (
        type(preflight_id) is not str
        or not preflight_id.strip()
    ):
        raise ValueError("preflight_id")

    if (
        type(startup_capture_id) is not str
        or not startup_capture_id.strip()
    ):
        raise ValueError("startup_capture_id")

    if not callable(clock):
        raise TypeError("clock")

    if (
        runtime_config.execution_mode != "PAPER"
        or runtime_config.broker_order_submission is not False
        or runtime_config.live_execution_eligible is not False
    ):
        raise ValueError(
            "Task 9 entrypoint requires PAPER-only runtime config"
        )

    snapshot = build_task9_runtime_config_snapshot(
        runtime_config
    )

    observed_at = clock()

    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("clock")

    # Establish or recover canonical campaign/run authority before any
    # provider-dependent startup acquisition.  A temporary provider outage
    # must not prevent the market-day rollover authority from existing.
    prepare_task9_startup_campaign_authority(
        runtime_config=runtime_config,
        snapshot=snapshot,
        observed_at=observed_at,
    )

    _run_task9_pre_provider_local_startup_gate(
        runtime_config=runtime_config,
        snapshot=snapshot,
        observed_at=observed_at,
        live_stream_root=live_stream_root,
    )

    provider_bundle = (
        providers
        if providers is not None
        else build_default_runtime_providers()
    )

    if (
        type(provider_bundle)
        is not CertifiedRuntimeProviderBundleV1
    ):
        raise TypeError("providers")

    try:
        retained = (
            capture_task9_production_startup_angel_facts(
                providers=provider_bundle,
                startup_capture_id=(
                    startup_capture_id.strip()
                ),
            )
        )

    except RuntimeError as exc:
        startup_acquisition_failure = str(
            exc
        )

        retryable_acquisition_failures = {
            (
                "TASK9_STARTUP_NIFTY_OPTION_CAPTURE_BLOCKED:"
                "OPTION_CAPTURE_RUNTIMEERROR"
            ),
            (
                "TASK9_STARTUP_SENSEX_OPTION_CAPTURE_BLOCKED:"
                "OPTION_CAPTURE_RUNTIMEERROR"
            ),
        }

        if (
            startup_acquisition_failure
            not in retryable_acquisition_failures
        ):
            raise

        bootstrap = (
            run_task9_production_startup_bootstrap(
                runtime_config=runtime_config,
                snapshot=snapshot,
                field_registry=(
                    default_provider_capability_registry()
                ),
                angel_capability_session=(
                    build_task9_angel_capability_session()
                ),
                live_proof_bundle=None,
                preflight_id=(
                    preflight_id.strip()
                ),
                observed_at=observed_at,
                live_stream_root=live_stream_root,
                startup_acquisition_failure=(
                    startup_acquisition_failure
                ),
            )
        )

        if bootstrap.launch_approved is not False:
            raise ValueError(
                "TASK9_RETRYABLE_ACQUISITION_FAILURE_"
                "UNEXPECTEDLY_APPROVED"
            )

        return (
            Task9ProductionStartupEntrypointResultV1(
                bootstrap=bootstrap,
                launcher_stats=None,
            )
        )

    live_proof_bundle = (
        build_task9_angel_live_proof_bundle_from_retained_captures(
            captures=retained
        )
    )

    bootstrap = (
        run_task9_production_startup_bootstrap(
            runtime_config=runtime_config,
            snapshot=snapshot,
            field_registry=(
                default_provider_capability_registry()
            ),
            angel_capability_session=(
                build_task9_angel_capability_session()
            ),
            live_proof_bundle=(
                live_proof_bundle
            ),
            preflight_id=(
                preflight_id.strip()
            ),
            observed_at=observed_at,
            live_stream_root=live_stream_root,
        )
    )

    # This is the only launch gate.  The method raises if canonical
    # preflight did not approve.  No boolean shortcut exists here.
    try:
        launcher_kwargs = (
            bootstrap.launcher_kwargs()
        )
    except ValueError as exc:
        if (
            str(exc)
            == "TASK9_STARTUP_PREFLIGHT_NOT_APPROVED"
        ):
            return (
                Task9ProductionStartupEntrypointResultV1(
                    bootstrap=bootstrap,
                    launcher_stats=None,
                )
            )
        raise

    launcher = (
        Task9LivePaperCertificationLauncher(
            **launcher_kwargs,
            providers=provider_bundle,
            available_capital=float(
                runtime_config.available_capital
            ),
            risk_fraction=float(
                runtime_config.trade_risk_fraction
            ),
            maximum_quantity=int(
                runtime_config.maximum_quantity
            ),
            maximum_daily_loss_fraction=float(
                runtime_config.maximum_daily_loss_fraction
            ),
            session_state_resolver=(
                build_task9_live_collector_session_resolver(
                    nfo_new_entry_cutoff=time(15, 30),
                    bfo_new_entry_cutoff=time(15, 30),
                )
            ),
            clock=clock,
        )
    )

    stats = launcher.run(
        max_cycles=max_cycles,
        cycle_interval_seconds=(
            cycle_interval_seconds
        ),
    )

    return (
        Task9ProductionStartupEntrypointResultV1(
            bootstrap=bootstrap,
            launcher_stats=stats,
        )
    )


def _parse_policy_references(
    values: list[str] | None,
) -> dict[str, str]:
    if not values:
        raise ValueError(
            "at least one --policy-reference is required"
        )

    result: dict[str, str] = {}

    for raw in values:
        if (
            type(raw) is not str
            or "=" not in raw
        ):
            raise ValueError(
                "policy references must use key=value"
            )

        key, value = raw.split(
            "=",
            1,
        )

        key = key.strip()
        value = value.strip()

        if not key or not value:
            raise ValueError(
                "policy references must use non-empty key=value"
            )

        existing = result.get(key)

        if (
            existing is not None
            and existing != value
        ):
            raise ValueError(
                "conflicting policy reference: "
                + key
            )

        result[key] = value

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Task 9 canonical bootstrap-first "
            "automated PAPER certification launcher"
        )
    )

    parser.add_argument(
        "--automated-paper",
        action="store_true",
        help=(
            "Required acknowledgement. "
            "No live-broker mode exists."
        ),
    )

    parser.add_argument(
        "--runtime-config-id",
        required=True,
    )

    parser.add_argument(
        "--runtime-config-version",
        default="1",
    )

    parser.add_argument(
        "--campaign-registry-location",
        required=True,
    )

    parser.add_argument(
        "--campaign-id",
        required=True,
    )

    parser.add_argument(
        "--market-date",
        required=True,
        help="Canonical market date in YYYY-MM-DD form.",
    )

    parser.add_argument(
        "--official-run-id",
        required=True,
    )

    parser.add_argument(
        "--official-root",
        required=True,
    )

    parser.add_argument(
        "--certification-registry-root",
        required=True,
    )

    parser.add_argument(
        "--persistence-root",
        required=True,
    )

    parser.add_argument(
        "--dashboard-publication-location",
        required=True,
    )

    parser.add_argument(
        "--available-capital",
        required=True,
        type=float,
    )

    parser.add_argument(
        "--risk-fraction",
        required=True,
        type=float,
    )

    parser.add_argument(
        "--maximum-quantity",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--policy-reference",
        action="append",
        help=(
            "Canonical policy reference as key=value. "
            "Repeat for every policy reference."
        ),
    )

    parser.add_argument(
        "--run-classification",
        default="OFFICIAL_CERTIFICATION",
    )

    parser.add_argument(
        "--live-stream-root",
    )

    parser.add_argument(
        "--max-cycles",
        type=int,
    )

    parser.add_argument(
        "--cycle-interval-seconds",
        type=float,
        default=60.0,
    )

    return parser


def _generated_startup_ids(
    *,
    official_run_id: str,
) -> tuple[str, str]:
    now = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    nonce = uuid.uuid4().hex[:12]

    base = (
        f"{official_run_id}-"
        f"{now}-{nonce}"
    )

    return (
        f"{base}-preflight",
        f"{base}-capture",
    )


def main(
    argv: list[str] | None = None,
) -> int:
    parser = _build_parser()

    args = parser.parse_args(
        argv
    )

    if args.automated_paper is not True:
        parser.error(
            "--automated-paper is required; "
            "no live mode exists"
        )

    try:
        market_date = date.fromisoformat(
            args.market_date
        )

        policy_references = (
            _parse_policy_references(
                args.policy_reference
            )
        )

        runtime_config = (
            build_task9_runtime_config(
                runtime_config_id=(
                    args.runtime_config_id
                ),
                runtime_config_version=(
                    args.runtime_config_version
                ),
                campaign_registry_location=(
                    args.campaign_registry_location
                ),
                campaign_id=(
                    args.campaign_id
                ),
                market_date=market_date,
                official_run_id=(
                    args.official_run_id
                ),
                official_root=(
                    args.official_root
                ),
                certification_registry_root=(
                    args.certification_registry_root
                ),
                authoritative_persistence_root=(
                    args.persistence_root
                ),
                dashboard_publication_location=(
                    args.dashboard_publication_location
                ),
                available_capital=(
                    args.available_capital
                ),
                risk_fraction=(
                    args.risk_fraction
                ),
                maximum_quantity=(
                    args.maximum_quantity
                ),
                policy_references=(
                    policy_references
                ),
                run_classification=(
                    args.run_classification
                ),

                # These are intentionally not CLI-selectable.
                execution_mode="PAPER",
                broker_order_submission=False,
                live_execution_eligible=False,
            )
        )

        (
            preflight_id,
            startup_capture_id,
        ) = _generated_startup_ids(
            official_run_id=(
                args.official_run_id
            )
        )

        result = (
            run_task9_production_startup_entrypoint(
                runtime_config=(
                    runtime_config
                ),
                preflight_id=(
                    preflight_id
                ),
                startup_capture_id=(
                    startup_capture_id
                ),
                live_stream_root=(
                    args.live_stream_root
                ),
                max_cycles=(
                    args.max_cycles
                ),
                cycle_interval_seconds=(
                    args.cycle_interval_seconds
                ),
            )
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        print(
            "TASK9_STARTUP_FAILED "
            f"error_type={type(exc).__name__} "
            f"reason={exc}"
        )
        return 2

    if result.launcher_stats is None:
        print(
            "TASK9_STARTUP_BLOCKED "
            "launch_approved=false "
            f"preflight_id={result.bootstrap.startup_preflight_id}"
        )
        return 2

    stats = result.launcher_stats

    print(
        "TASK9_LAUNCHER_STATS "
        f"completed_cycles={stats.completed_cycles} "
        f"graceful_shutdown={stats.graceful_shutdown} "
        "execution_mode=PAPER "
        "broker_order_submission=false "
        "live_execution_eligible=false"
    )

    return 0


__all__ = (
    "Task9ProductionStartupEntrypointResultV1",
    "run_task9_production_startup_entrypoint",
)


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

