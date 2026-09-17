from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_india_vix_projection import (
    project_task9_angel_india_vix_to_report,
)
from services.certification.task9_angel_india_vix_readiness import (
    Task9AngelIndiaVixReadinessStatus,
    evaluate_task9_angel_india_vix,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_india_vix_proof_v1 import (
    Task9AngelIndiaVixProbeStatus,
    Task9AngelIndiaVixProofV1,
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
    30,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _runtime():
    return build_task9_runtime_config(
        runtime_config_id="task9857-runtime",
        runtime_config_version="1",
        campaign_registry_location="task9857/campaign.json",
        campaign_id="task9857-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9857-run",
        official_root="task9857/official",
        certification_registry_root="task9857/registry",
        authoritative_persistence_root="task9857/persistence",
        dashboard_publication_location="task9857/dashboard.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9857-canonical.v1",
            "session": "task9857-session.v1",
            "risk": "task9857-risk.v1",
            "contract_selection": "task9857-contract.v1",
            "lifecycle": "task9857-lifecycle.v1",
            "counting": "task9857-counting.v1",
            "failure_disposition": "task9857-failure.v1",
            "contract_spread": "task9857-spread.v1",
            "liquidity": "task9857-liquidity.v1",
            "minimum_risk_reward": "task9857-rr.v1",
            "stop_target": "task9857-stop-target.v1",
            "portfolio_concurrency": "task9857-concurrency.v1",
        },
    )


def _authority():
    return build_task9_angel_capability_session()


def _proof(
    *,
    status=Task9AngelIndiaVixProbeStatus.AVAILABLE,
    age=1.0,
    identity=True,
    reason=None,
):
    return Task9AngelIndiaVixProofV1(
        proof_id="task9857-vix",
        observed_at=NOW,
        market="INDIA_VIX",
        exchange="NSE",
        instrument_type="AMXIDX",
        status=status,
        provider_timestamp=(
            NOW - timedelta(seconds=age)
            if status
            is Task9AngelIndiaVixProbeStatus.AVAILABLE
            else None
        ),
        ltp=(
            14.5
            if status
            is Task9AngelIndiaVixProbeStatus.AVAILABLE
            else None
        ),
        previous_close=(
            14.1
            if status
            is Task9AngelIndiaVixProbeStatus.AVAILABLE
            else None
        ),
        identity_verified=identity,
        source_ref=(
            "angel-india-vix-full"
            if status
            is Task9AngelIndiaVixProbeStatus.AVAILABLE
            else None
        ),
        incident_ref=(
            None
            if status
            is Task9AngelIndiaVixProbeStatus.AVAILABLE
            else "incident-task9857-vix"
        ),
        sanitized_reason=reason,
    )


def _report():
    return build_task9_provider_capability_report(
        _runtime()
    )


def _row(report):
    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.INDIA_VIX
            and state.capability
            is Task9ProviderCapability.INDIA_VIX
        )
    )

    assert len(matches) == 1
    return matches[0]


def test_fresh_verified_vix_is_ready():
    result = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(),
    )

    assert (
        result.status
        is Task9AngelIndiaVixReadinessStatus.READY
    )
    assert (
        result.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )


def test_vix_unavailable_is_optional():
    result = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            status=(
                Task9AngelIndiaVixProbeStatus.UNAVAILABLE
            ),
            reason="SANITIZED_VIX_UNAVAILABLE",
        ),
    )

    assert (
        result.status
        is Task9AngelIndiaVixReadinessStatus.UNAVAILABLE_OPTIONAL
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
    )


def test_vix_identity_failure_is_optional_not_fatal():
    result = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            identity=False,
        ),
    )

    assert (
        result.status
        is Task9AngelIndiaVixReadinessStatus.UNAVAILABLE_OPTIONAL
    )


def test_stale_vix_is_optional_unavailable():
    runtime = _runtime()

    result = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            age=(
                runtime.market_quote_max_age_seconds
                + 0.001
            ),
        ),
    )

    assert (
        result.status
        is Task9AngelIndiaVixReadinessStatus.UNAVAILABLE_OPTIONAL
    )


def test_ready_projection():
    readiness = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(),
    )

    projected = (
        project_task9_angel_india_vix_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _row(projected)

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert row.startup_semantic is None


def test_unavailable_projection_is_nonblocking():
    readiness = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            status=(
                Task9AngelIndiaVixProbeStatus.UNAVAILABLE
            ),
            reason="SANITIZED_VIX_UNAVAILABLE",
        ),
    )

    projected = (
        project_task9_angel_india_vix_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _row(projected)

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
    )

    assert (
        row.startup_semantic
        is Task9StartupSemantic.OPTIONAL_UNAVAILABLE
    )


def test_projection_is_idempotent():
    readiness = evaluate_task9_angel_india_vix(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(),
    )

    first = (
        project_task9_angel_india_vix_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    second = (
        project_task9_angel_india_vix_to_report(
            report=first,
            readiness=readiness,
        )
    )

    assert first.to_dict() == second.to_dict()


def test_wrong_vix_identity_contract_rejected():
    with pytest.raises(ValueError):
        Task9AngelIndiaVixProofV1(
            proof_id="wrong-vix",
            observed_at=NOW,
            market="INDIA_VIX",
            exchange="BSE",
            instrument_type="AMXIDX",
            status=(
                Task9AngelIndiaVixProbeStatus.AVAILABLE
            ),
            provider_timestamp=NOW,
            ltp=14.5,
            previous_close=14.1,
            identity_verified=True,
        )


def test_secret_like_reason_rejected():
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        _proof(
            status=(
                Task9AngelIndiaVixProbeStatus.UNAVAILABLE
            ),
            reason="raw_payload=secret",
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelIndiaVixProofV1(
            proof_id="unsafe-vix",
            observed_at=NOW,
            market="INDIA_VIX",
            exchange="NSE",
            instrument_type="AMXIDX",
            status=(
                Task9AngelIndiaVixProbeStatus.AVAILABLE
            ),
            provider_timestamp=NOW,
            ltp=14.5,
            previous_close=14.1,
            identity_verified=True,
            broker_order_submission=True,
        )
