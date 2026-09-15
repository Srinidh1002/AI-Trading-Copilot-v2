from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_instrument_master_projection import (
    project_task9_angel_instrument_master_to_report,
)
from services.certification.task9_angel_instrument_master_readiness import (
    Task9AngelInstrumentMasterReadinessStatus,
    evaluate_task9_angel_instrument_master,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_instrument_master_proof_v1 import (
    Task9AngelInstrumentMasterProbeStatus,
    Task9AngelInstrumentMasterProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapability,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupReasonCode,
    Task9StartupSemantic,
)


NOW = datetime(
    2026,
    8,
    17,
    9,
    0,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _runtime():
    return build_task9_runtime_config(
        runtime_config_id="task9853-runtime",
        runtime_config_version="1",
        campaign_registry_location="task9853/campaign.json",
        campaign_id="task9853-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9853-run",
        official_root="task9853/official",
        certification_registry_root="task9853/registry",
        authoritative_persistence_root="task9853/persistence",
        dashboard_publication_location="task9853/dashboard.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9853-canonical.v1",
            "session": "task9853-session.v1",
            "risk": "task9853-risk.v1",
            "contract_selection": "task9853-contract.v1",
            "lifecycle": "task9853-lifecycle.v1",
            "counting": "task9853-counting.v1",
            "failure_disposition": "task9853-failure.v1",
            "contract_spread": "task9853-spread.v1",
            "liquidity": "task9853-liquidity.v1",
            "minimum_risk_reward": "task9853-rr.v1",
            "stop_target": "task9853-stop-target.v1",
            "portfolio_concurrency": "task9853-concurrency.v1",
        },
    )


def _authority():
    return build_task9_angel_capability_session()


def _proof(
    *,
    status=Task9AngelInstrumentMasterProbeStatus.AVAILABLE,
    age_seconds=10.0,
    nifty=True,
    sensex=True,
    record_count=1000,
    reason=None,
):
    fetched_at = (
        NOW - timedelta(seconds=age_seconds)
        if status
        is Task9AngelInstrumentMasterProbeStatus.AVAILABLE
        else None
    )

    return Task9AngelInstrumentMasterProofV1(
        proof_id="task9853-master-proof",
        observed_at=NOW,
        status=status,
        fetched_at=fetched_at,
        record_count=record_count,
        nifty_nfo_identity_present=nifty,
        sensex_bfo_identity_present=sensex,
        source_ref=(
            "angel-openapi-scrip-master"
            if status
            is Task9AngelInstrumentMasterProbeStatus.AVAILABLE
            else None
        ),
        incident_ref=(
            None
            if status
            is Task9AngelInstrumentMasterProbeStatus.AVAILABLE
            else "incident-task9853-master"
        ),
        sanitized_reason=reason,
    )


def _report():
    return build_task9_provider_capability_report(
        _runtime()
    )


def _master_row(report):
    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_INSTRUMENT_MASTER
            and state.capability
            is Task9ProviderCapability.INSTRUMENT_MASTER
        )
    )

    assert len(matches) == 1
    return matches[0]


def test_fresh_complete_master_is_ready():
    runtime = _runtime()

    proof = _proof(
        age_seconds=min(
            10.0,
            runtime.instrument_master_max_age_seconds,
        )
    )

    result = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=runtime,
        proof=proof,
    )

    assert (
        result.status
        is Task9AngelInstrumentMasterReadinessStatus.READY
    )
    assert (
        result.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert result.reason_code is None


def test_exact_maximum_age_is_still_fresh():
    runtime = _runtime()

    result = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            age_seconds=(
                runtime.instrument_master_max_age_seconds
            )
        ),
    )

    assert (
        result.status
        is Task9AngelInstrumentMasterReadinessStatus.READY
    )


def test_over_maximum_age_is_stale_retryable():
    runtime = _runtime()

    result = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            age_seconds=(
                runtime.instrument_master_max_age_seconds
                + 0.001
            )
        ),
    )

    assert (
        result.status
        is Task9AngelInstrumentMasterReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.INSTRUMENT_MASTER_STALE
    )


def test_unavailable_master_is_retryable():
    result = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            status=(
                Task9AngelInstrumentMasterProbeStatus.UNAVAILABLE
            ),
            record_count=None,
            reason="SANITIZED_MASTER_UNAVAILABLE",
        ),
    )

    assert (
        result.status
        is Task9AngelInstrumentMasterReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
    )


def test_corrupt_master_is_fatal():
    result = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            status=(
                Task9AngelInstrumentMasterProbeStatus.CORRUPT
            ),
            record_count=None,
            reason="SANITIZED_MASTER_CORRUPT",
        ),
    )

    assert (
        result.status
        is Task9AngelInstrumentMasterReadinessStatus.FAILED_FATAL
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.INSTRUMENT_MASTER_CORRUPT
    )


@pytest.mark.parametrize(
    "nifty,sensex",
    (
        (False, True),
        (True, False),
        (False, False),
    ),
)
def test_required_market_identity_missing_is_fatal(
    nifty,
    sensex,
):
    result = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            nifty=nifty,
            sensex=sensex,
        ),
    )

    assert (
        result.status
        is Task9AngelInstrumentMasterReadinessStatus.FAILED_FATAL
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.INSTRUMENT_MASTER_CORRUPT
    )


def test_ready_projection_changes_only_master_row():
    report = _report()

    readiness = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(),
    )

    projected = (
        project_task9_angel_instrument_master_to_report(
            report=report,
            readiness=readiness,
        )
    )

    row = _master_row(projected)

    assert (
        row.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert row.startup_semantic is None

    before_other = tuple(
        state
        for state in report.capability_states
        if state is not _master_row(report)
    )

    after_other = tuple(
        state
        for state in projected.capability_states
        if state is not row
    )

    assert after_other == before_other


def test_stale_projection_is_retryable():
    runtime = _runtime()

    readiness = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            age_seconds=(
                runtime.instrument_master_max_age_seconds
                + 1
            )
        ),
    )

    projected = (
        project_task9_angel_instrument_master_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _master_row(projected)

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        row.startup_semantic
        is Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
    )


def test_corrupt_projection_is_fatal():
    readiness = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            status=(
                Task9AngelInstrumentMasterProbeStatus.CORRUPT
            ),
            record_count=None,
            reason="SANITIZED_MASTER_CORRUPT",
        ),
    )

    projected = (
        project_task9_angel_instrument_master_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    row = _master_row(projected)

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.FAILED_FATAL
    )
    assert (
        row.startup_semantic
        is Task9StartupSemantic.STARTUP_FATAL
    )


def test_projection_is_idempotent():
    readiness = evaluate_task9_angel_instrument_master(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(),
    )

    first = (
        project_task9_angel_instrument_master_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    second = (
        project_task9_angel_instrument_master_to_report(
            report=first,
            readiness=readiness,
        )
    )

    assert first.to_dict() == second.to_dict()


def test_secret_like_failure_reason_rejected():
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        _proof(
            status=(
                Task9AngelInstrumentMasterProbeStatus.CORRUPT
            ),
            record_count=None,
            reason="raw_payload=secret-data",
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelInstrumentMasterProofV1(
            proof_id="unsafe-master",
            observed_at=NOW,
            status=(
                Task9AngelInstrumentMasterProbeStatus.AVAILABLE
            ),
            fetched_at=NOW,
            record_count=100,
            nifty_nfo_identity_present=True,
            sensex_bfo_identity_present=True,
            broker_order_submission=True,
        )


def test_wrong_types_fail_closed():
    proof = _proof()

    with pytest.raises(TypeError):
        evaluate_task9_angel_instrument_master(
            authority=object(),
            runtime_config=_runtime(),
            proof=proof,
        )

    with pytest.raises(TypeError):
        project_task9_angel_instrument_master_to_report(
            report=object(),
            readiness=object(),
        )
