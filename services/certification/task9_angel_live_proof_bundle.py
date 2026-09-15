"""Unified Task 9 Angel live-proof bundle and projection gate.

This module performs no provider acquisition.

A1-A6 proof contracts are evaluated by their existing readiness
authorities and projected through their existing generic-report
projectors.

Important boundaries:
- request-budget readiness remains Angel-specific and has no generic row;
- MARKET_DATA_WEBSOCKET remains pending for the collector/runtime
  readiness authority in 9.86.5B;
- therefore this module proves Angel live-proof readiness only and does
  not approve the complete startup preflight.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.certification.task9_angel_auth_capability_projection import (
    project_task9_angel_auth_readiness_to_report,
)
from services.certification.task9_angel_auth_session_readiness import (
    Task9AngelAuthReadinessResultV1,
    evaluate_task9_angel_auth_session,
)
from services.certification.task9_angel_greeks_projection import (
    project_task9_angel_greeks_to_report,
)
from services.certification.task9_angel_greeks_readiness import (
    Task9AngelGreeksReadinessV1,
    evaluate_task9_angel_greeks,
)
from services.certification.task9_angel_india_vix_projection import (
    project_task9_angel_india_vix_to_report,
)
from services.certification.task9_angel_india_vix_readiness import (
    Task9AngelIndiaVixReadinessV1,
    evaluate_task9_angel_india_vix,
)
from services.certification.task9_angel_instrument_master_projection import (
    project_task9_angel_instrument_master_to_report,
)
from services.certification.task9_angel_instrument_master_readiness import (
    Task9AngelInstrumentMasterReadinessV1,
    evaluate_task9_angel_instrument_master,
)
from services.certification.task9_angel_option_full_projection import (
    project_task9_angel_option_full_to_report,
)
from services.certification.task9_angel_option_full_readiness import (
    Task9AngelOptionFullReadinessV1,
    evaluate_task9_angel_option_full,
)
from services.certification.task9_angel_provider_capability_bridge import (
    validate_task9_angel_generic_capability_alignment,
)
from services.certification.task9_angel_request_budget_readiness import (
    Task9AngelRequestBudgetReadinessV1,
    evaluate_task9_angel_request_budget,
)
from services.certification.task9_angel_spot_full_projection import (
    project_task9_angel_spot_full_to_report,
)
from services.certification.task9_angel_spot_full_readiness import (
    Task9AngelSpotFullReadinessV1,
    evaluate_task9_angel_spot_full,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthSessionProofV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_greeks_proof_v1 import (
    Task9AngelGreeksProofV1,
)
from services.contracts.task9_angel_india_vix_proof_v1 import (
    Task9AngelIndiaVixProofV1,
)
from services.contracts.task9_angel_instrument_master_proof_v1 import (
    Task9AngelInstrumentMasterProofV1,
)
from services.contracts.task9_angel_option_full_proof_v1 import (
    Task9AngelOptionFullProofV1,
)
from services.contracts.task9_angel_request_budget_proof_v1 import (
    Task9AngelRequestBudgetProofV1,
)
from services.contracts.task9_angel_spot_full_proof_v1 import (
    Task9AngelSpotFullProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9ProviderCapability,
    Task9ProviderCapabilityReportV1,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)


@dataclass(frozen=True, slots=True)
class Task9AngelLiveProofBundleV1:
    auth: Task9AngelAuthSessionProofV1
    instrument_master: Task9AngelInstrumentMasterProofV1
    spots: tuple[
        Task9AngelSpotFullProofV1,
        ...,
    ]
    option_full: tuple[
        Task9AngelOptionFullProofV1,
        ...,
    ]
    greeks: tuple[
        Task9AngelGreeksProofV1,
        ...,
    ]
    india_vix: Task9AngelIndiaVixProofV1
    request_budget: Task9AngelRequestBudgetProofV1

    def __post_init__(self) -> None:
        if type(self.auth) is not Task9AngelAuthSessionProofV1:
            raise TypeError("auth")

        if (
            type(self.instrument_master)
            is not Task9AngelInstrumentMasterProofV1
        ):
            raise TypeError("instrument_master")

        if (
            type(self.india_vix)
            is not Task9AngelIndiaVixProofV1
        ):
            raise TypeError("india_vix")

        if (
            type(self.request_budget)
            is not Task9AngelRequestBudgetProofV1
        ):
            raise TypeError("request_budget")

        for name, value, expected in (
            (
                "spots",
                self.spots,
                Task9AngelSpotFullProofV1,
            ),
            (
                "option_full",
                self.option_full,
                Task9AngelOptionFullProofV1,
            ),
            (
                "greeks",
                self.greeks,
                Task9AngelGreeksProofV1,
            ),
        ):
            if type(value) is not tuple:
                raise TypeError(name)

            if (
                len(value) != 2
                or any(
                    type(item) is not expected
                    for item in value
                )
            ):
                raise ValueError(name)

        if {
            item.market
            for item in self.spots
        } != {"NIFTY", "SENSEX"}:
            raise ValueError(
                "TASK9_A7_SPOT_MARKETS_INVALID"
            )

        if {
            item.market
            for item in self.option_full
        } != {"NIFTY", "SENSEX"}:
            raise ValueError(
                "TASK9_A7_OPTION_FULL_MARKETS_INVALID"
            )

        if {
            item.market
            for item in self.greeks
        } != {"NIFTY", "SENSEX"}:
            raise ValueError(
                "TASK9_A7_GREEKS_MARKETS_INVALID"
            )


@dataclass(frozen=True, slots=True)
class Task9AngelLiveProofProjectionV1:
    report: Task9ProviderCapabilityReportV1

    auth_readiness: Task9AngelAuthReadinessResultV1
    instrument_master_readiness: (
        Task9AngelInstrumentMasterReadinessV1
    )
    spot_readiness: tuple[
        Task9AngelSpotFullReadinessV1,
        ...,
    ]
    option_full_readiness: tuple[
        Task9AngelOptionFullReadinessV1,
        ...,
    ]
    greeks_readiness: tuple[
        Task9AngelGreeksReadinessV1,
        ...,
    ]
    india_vix_readiness: Task9AngelIndiaVixReadinessV1
    request_budget_readiness: (
        Task9AngelRequestBudgetReadinessV1
    )

    required_angel_live_proofs_ready: bool
    websocket_live_proof_pending: bool

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 A7 projection must remain PAPER-only"
            )


def _ready(
    value: object,
) -> bool:
    return (
        getattr(
            value,
            "readiness_status",
            None,
        )
        is Task9ProviderReadinessStatus.READY
    )


def project_task9_angel_live_proof_bundle(
    *,
    runtime_config: Task9RuntimeConfigV1,
    authority: Task9AngelCapabilitySessionV1,
    bundle: Task9AngelLiveProofBundleV1,
) -> Task9AngelLiveProofProjectionV1:
    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if type(authority) is not Task9AngelCapabilitySessionV1:
        raise TypeError("authority")

    if type(bundle) is not Task9AngelLiveProofBundleV1:
        raise TypeError("bundle")

    report = build_task9_provider_capability_report(
        runtime_config
    )

    # Validate static 9.85 Angel authority against the untouched generic
    # report before any live proof projection changes generic states.
    validate_task9_angel_generic_capability_alignment(
        angel=authority,
        generic=report,
    )

    auth = evaluate_task9_angel_auth_session(
        authority=authority,
        proof=bundle.auth,
    )

    report = (
        project_task9_angel_auth_readiness_to_report(
            report=report,
            proof=bundle.auth,
            readiness=auth,
        )
    )

    master = evaluate_task9_angel_instrument_master(
        authority=authority,
        runtime_config=runtime_config,
        proof=bundle.instrument_master,
    )

    report = (
        project_task9_angel_instrument_master_to_report(
            report=report,
            readiness=master,
        )
    )

    spot_results = []

    for proof in sorted(
        bundle.spots,
        key=lambda item: item.market,
    ):
        readiness = evaluate_task9_angel_spot_full(
            authority=authority,
            runtime_config=runtime_config,
            proof=proof,
        )

        report = project_task9_angel_spot_full_to_report(
            report=report,
            readiness=readiness,
        )

        spot_results.append(readiness)

    option_results = []

    for proof in sorted(
        bundle.option_full,
        key=lambda item: item.market,
    ):
        readiness = evaluate_task9_angel_option_full(
            authority=authority,
            runtime_config=runtime_config,
            proof=proof,
        )

        report = project_task9_angel_option_full_to_report(
            report=report,
            readiness=readiness,
        )

        option_results.append(readiness)

    greek_results = []

    for proof in sorted(
        bundle.greeks,
        key=lambda item: item.market,
    ):
        readiness = evaluate_task9_angel_greeks(
            authority=authority,
            proof=proof,
        )

        report = project_task9_angel_greeks_to_report(
            report=report,
            readiness=readiness,
        )

        greek_results.append(readiness)

    vix = evaluate_task9_angel_india_vix(
        authority=authority,
        runtime_config=runtime_config,
        proof=bundle.india_vix,
    )

    report = project_task9_angel_india_vix_to_report(
        report=report,
        readiness=vix,
    )

    # Deliberately NOT projected into the generic report. The canonical
    # bridge explicitly defines request budget as Angel-specific
    # operational infrastructure with no separate generic row.
    budget = evaluate_task9_angel_request_budget(
        authority=authority,
        proof=bundle.request_budget,
    )

    required_results = (
        auth,
        master,
        *spot_results,
        *option_results,
        budget,
    )

    required_angel_ready = all(
        _ready(item)
        for item in required_results
    )

    websocket_rows = tuple(
        item
        for item in report.capability_states
        if (
            item.provider_family
            is Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET
            and item.capability
            is Task9ProviderCapability.MARKET_DATA_WEBSOCKET
        )
    )

    if len(websocket_rows) != 1:
        raise ValueError(
            "TASK9_A7_WEBSOCKET_GENERIC_ROW_INVALID"
        )

    websocket_pending = (
        websocket_rows[0].readiness_status
        is not Task9ProviderReadinessStatus.READY
    )

    # A7 must never silently satisfy the collector/WebSocket authority.
    if not websocket_pending:
        raise ValueError(
            "TASK9_A7_WEBSOCKET_WAS_PREMATURELY_PROVEN"
        )

    return Task9AngelLiveProofProjectionV1(
        report=report,
        auth_readiness=auth,
        instrument_master_readiness=master,
        spot_readiness=tuple(
            spot_results
        ),
        option_full_readiness=tuple(
            option_results
        ),
        greeks_readiness=tuple(
            greek_results
        ),
        india_vix_readiness=vix,
        request_budget_readiness=budget,
        required_angel_live_proofs_ready=(
            required_angel_ready
        ),
        websocket_live_proof_pending=True,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "Task9AngelLiveProofBundleV1",
    "Task9AngelLiveProofProjectionV1",
    "project_task9_angel_live_proof_bundle",
)
