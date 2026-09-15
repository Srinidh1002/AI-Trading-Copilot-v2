from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_greeks_projection import (
    project_task9_angel_greeks_to_report,
)
from services.certification.task9_angel_greeks_readiness import (
    Task9AngelGreeksReadinessStatus,
    evaluate_task9_angel_greeks,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_greeks_proof_v1 import (
    Task9AngelGreeksProbeStatus,
    Task9AngelGreeksProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapability,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupSemantic,
)


NOW = datetime(
    2026,
    8,
    17,
    9,
    25,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _authority():
    return build_task9_angel_capability_session()


def _runtime():
    return build_task9_runtime_config(
        runtime_config_id="task9856-runtime",
        runtime_config_version="1",
        campaign_registry_location="task9856/campaign.json",
        campaign_id="task9856-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9856-run",
        official_root="task9856/official",
        certification_registry_root="task9856/registry",
        authoritative_persistence_root="task9856/persistence",
        dashboard_publication_location="task9856/dashboard.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9856-canonical.v1",
            "session": "task9856-session.v1",
            "risk": "task9856-risk.v1",
            "contract_selection": "task9856-contract.v1",
            "lifecycle": "task9856-lifecycle.v1",
            "counting": "task9856-counting.v1",
            "failure_disposition": "task9856-failure.v1",
            "contract_spread": "task9856-spread.v1",
            "liquidity": "task9856-liquidity.v1",
            "minimum_risk_reward": "task9856-rr.v1",
            "stop_target": "task9856-stop-target.v1",
            "portfolio_concurrency": "task9856-concurrency.v1",
        },
    )


def _report():
    return build_task9_provider_capability_report(
        _runtime()
    )


def _nfo(
    *,
    status=Task9AngelGreeksProbeStatus.AVAILABLE,
    requested=5,
    enriched=5,
    unavailable=0,
    reason=None,
):
    return Task9AngelGreeksProofV1(
        proof_id="task9856-nfo",
        observed_at=NOW,
        market="NIFTY",
        exchange="NFO",
        status=status,
        requested_contract_count=requested,
        enriched_contract_count=enriched,
        unavailable_contract_count=unavailable,
        delta_present=(enriched > 0),
        gamma_present=(enriched > 0),
        theta_present=(enriched > 0),
        vega_present=(enriched > 0),
        implied_volatility_present=(
            enriched > 0
        ),
        source_ref=(
            "angel-option-greeks"
            if enriched > 0
            else None
        ),
        incident_ref=(
            None
            if status
            is Task9AngelGreeksProbeStatus.AVAILABLE
            else "incident-task9856-nfo"
        ),
        sanitized_reason=reason,
    )


def _bfo():
    return Task9AngelGreeksProofV1(
        proof_id="task9856-bfo",
        observed_at=NOW,
        market="SENSEX",
        exchange="BFO",
        status=(
            Task9AngelGreeksProbeStatus.UNSUPPORTED
        ),
        requested_contract_count=0,
        enriched_contract_count=0,
        unavailable_contract_count=0,
        delta_present=False,
        gamma_present=False,
        theta_present=False,
        vega_present=False,
        implied_volatility_present=False,
        sanitized_reason=(
            "BFO_GREEKS_PROVIDER_UNSUPPORTED"
        ),
    )


def _row(report, market, exchange):
    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_OPTION_GREEKS
            and state.capability
            is Task9ProviderCapability.OPTION_GREEKS
            and state.market == market
            and state.exchange == exchange
        )
    )

    assert len(matches) == 1
    return matches[0]


def test_nfo_complete_greeks_proves_optional_capability():
    result = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(),
    )

    assert (
        result.status
        is Task9AngelGreeksReadinessStatus.READY
    )
    assert (
        result.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )


def test_nfo_partial_greeks_still_proves_capability():
    result = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(
            status=(
                Task9AngelGreeksProbeStatus.PARTIAL
            ),
            requested=5,
            enriched=3,
            unavailable=2,
            reason="SANITIZED_PARTIAL_GREEKS",
        ),
    )

    assert (
        result.status
        is Task9AngelGreeksReadinessStatus.READY
    )
    assert result.partial_response is True


def test_nfo_unavailable_is_optional_nonblocking():
    result = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(
            status=(
                Task9AngelGreeksProbeStatus.UNAVAILABLE
            ),
            requested=5,
            enriched=0,
            unavailable=5,
            reason="SANITIZED_GREEKS_UNAVAILABLE",
        ),
    )

    assert (
        result.status
        is Task9AngelGreeksReadinessStatus.UNAVAILABLE_OPTIONAL
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
    )


def test_bfo_is_explicitly_unsupported():
    result = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_bfo(),
    )

    assert (
        result.status
        is Task9AngelGreeksReadinessStatus.UNSUPPORTED
    )
    assert (
        result.live_proof_status
        is Task9LiveProofStatus.NOT_APPLICABLE
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )


def test_bfo_probe_attempt_is_rejected():
    with pytest.raises(
        ValueError,
        match="BFO Greeks",
    ):
        Task9AngelGreeksProofV1(
            proof_id="illegal-bfo-probe",
            observed_at=NOW,
            market="SENSEX",
            exchange="BFO",
            status=(
                Task9AngelGreeksProbeStatus.AVAILABLE
            ),
            requested_contract_count=1,
            enriched_contract_count=1,
            unavailable_contract_count=0,
            delta_present=True,
            gamma_present=True,
            theta_present=True,
            vega_present=True,
            implied_volatility_present=True,
        )


def test_bfo_fabricated_fields_are_rejected():
    with pytest.raises(
        ValueError,
        match="fabricated",
    ):
        Task9AngelGreeksProofV1(
            proof_id="fabricated-bfo",
            observed_at=NOW,
            market="SENSEX",
            exchange="BFO",
            status=(
                Task9AngelGreeksProbeStatus.UNSUPPORTED
            ),
            requested_contract_count=0,
            enriched_contract_count=0,
            unavailable_contract_count=0,
            delta_present=True,
            gamma_present=False,
            theta_present=False,
            vega_present=False,
            implied_volatility_present=False,
            sanitized_reason=(
                "BFO_GREEKS_PROVIDER_UNSUPPORTED"
            ),
        )


def test_nfo_projection_ready():
    readiness = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(),
    )

    projected = (
        project_task9_angel_greeks_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _row(
        projected,
        "NIFTY",
        "NFO",
    )

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert row.startup_semantic is None


def test_nfo_unavailable_projection_remains_optional():
    readiness = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(
            status=(
                Task9AngelGreeksProbeStatus.UNAVAILABLE
            ),
            requested=5,
            enriched=0,
            unavailable=5,
            reason="SANITIZED_GREEKS_UNAVAILABLE",
        ),
    )

    projected = (
        project_task9_angel_greeks_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _row(
        projected,
        "NIFTY",
        "NFO",
    )

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
    )
    assert (
        row.startup_semantic
        is Task9StartupSemantic.OPTIONAL_UNAVAILABLE
    )


def test_bfo_projection_preserves_unsupported():
    readiness = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_bfo(),
    )

    projected = (
        project_task9_angel_greeks_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _row(
        projected,
        "SENSEX",
        "BFO",
    )

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )
    assert (
        row.live_proof_status
        is Task9LiveProofStatus.NOT_APPLICABLE
    )
    assert (
        row.startup_semantic
        is Task9StartupSemantic.OPTIONAL_UNAVAILABLE
    )


def test_nfo_projection_does_not_mutate_bfo():
    report = _report()
    original_bfo = _row(
        report,
        "SENSEX",
        "BFO",
    )

    readiness = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(),
    )

    projected = (
        project_task9_angel_greeks_to_report(
            report=report,
            readiness=readiness,
        )
    )

    assert (
        _row(
            projected,
            "SENSEX",
            "BFO",
        )
        == original_bfo
    )


def test_projection_is_idempotent():
    readiness = evaluate_task9_angel_greeks(
        authority=_authority(),
        proof=_nfo(),
    )

    first = project_task9_angel_greeks_to_report(
        report=_report(),
        readiness=readiness,
    )

    second = project_task9_angel_greeks_to_report(
        report=first,
        readiness=readiness,
    )

    assert first.to_dict() == second.to_dict()


def test_secret_like_reason_rejected():
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        _nfo(
            status=(
                Task9AngelGreeksProbeStatus.UNAVAILABLE
            ),
            requested=5,
            enriched=0,
            unavailable=5,
            reason="raw_payload=secret",
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelGreeksProofV1(
            proof_id="unsafe",
            observed_at=NOW,
            market="NIFTY",
            exchange="NFO",
            status=(
                Task9AngelGreeksProbeStatus.AVAILABLE
            ),
            requested_contract_count=1,
            enriched_contract_count=1,
            unavailable_contract_count=0,
            delta_present=True,
            gamma_present=True,
            theta_present=True,
            vega_present=True,
            implied_volatility_present=True,
            broker_order_submission=True,
        )
