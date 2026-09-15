from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_spot_full_projection import (
    project_task9_angel_spot_full_to_report,
)
from services.certification.task9_angel_spot_full_readiness import (
    Task9AngelSpotFullReadinessStatus,
    evaluate_task9_angel_spot_full,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_spot_full_proof_v1 import (
    Task9AngelSpotFullProbeStatus,
    Task9AngelSpotFullProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
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
    16,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _runtime():
    return build_task9_runtime_config(
        runtime_config_id="task9854-runtime",
        runtime_config_version="1",
        campaign_registry_location="task9854/campaign.json",
        campaign_id="task9854-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9854-run",
        official_root="task9854/official",
        certification_registry_root="task9854/registry",
        authoritative_persistence_root="task9854/persistence",
        dashboard_publication_location="task9854/dashboard.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9854-canonical.v1",
            "session": "task9854-session.v1",
            "risk": "task9854-risk.v1",
            "contract_selection": "task9854-contract.v1",
            "lifecycle": "task9854-lifecycle.v1",
            "counting": "task9854-counting.v1",
            "failure_disposition": "task9854-failure.v1",
            "contract_spread": "task9854-spread.v1",
            "liquidity": "task9854-liquidity.v1",
            "minimum_risk_reward": "task9854-rr.v1",
            "stop_target": "task9854-stop-target.v1",
            "portfolio_concurrency": "task9854-concurrency.v1",
        },
    )


def _authority():
    return build_task9_angel_capability_session()


def _identity(market):
    if market == "NIFTY":
        return "NSE", "99926000"
    return "BSE", "99919000"


def _proof(
    market,
    *,
    status=Task9AngelSpotFullProbeStatus.AVAILABLE,
    age=1.0,
    identity_verified=True,
    reason=None,
):
    exchange, token = _identity(market)

    return Task9AngelSpotFullProofV1(
        proof_id=f"task9854-{market.lower()}",
        observed_at=NOW,
        market=market,
        exchange=exchange,
        token=token,
        status=status,
        provider_timestamp=(
            NOW - timedelta(seconds=age)
            if status
            is Task9AngelSpotFullProbeStatus.AVAILABLE
            else None
        ),
        ltp=(
            25000.0
            if market == "NIFTY"
            else 80000.0
        )
        if status
        is Task9AngelSpotFullProbeStatus.AVAILABLE
        else None,
        identity_verified=identity_verified,
        source_ref=(
            "angel-full-quote"
            if status
            is Task9AngelSpotFullProbeStatus.AVAILABLE
            else None
        ),
        incident_ref=(
            None
            if status
            is Task9AngelSpotFullProbeStatus.AVAILABLE
            else f"incident-task9854-{market.lower()}"
        ),
        sanitized_reason=reason,
    )


def _report():
    return build_task9_provider_capability_report(
        _runtime()
    )


def _spot_row(report, market):
    exchange, _ = _identity(market)

    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_SPOT
            and state.capability
            is Task9ProviderCapability.SPOT_QUOTES
            and state.market == market
            and state.exchange == exchange
        )
    )

    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_fresh_verified_quote_is_ready(market):
    runtime = _runtime()

    result = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            market,
            age=min(
                1.0,
                runtime.market_quote_max_age_seconds,
            ),
        ),
    )

    assert (
        result.status
        is Task9AngelSpotFullReadinessStatus.READY
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert result.reason_code is None


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_exact_quote_age_limit_is_ready(market):
    runtime = _runtime()

    result = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            market,
            age=(
                runtime.market_quote_max_age_seconds
            ),
        ),
    )

    assert (
        result.status
        is Task9AngelSpotFullReadinessStatus.READY
    )


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_stale_quote_is_retryable(market):
    runtime = _runtime()

    result = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            market,
            age=(
                runtime.market_quote_max_age_seconds
                + 0.001
            ),
        ),
    )

    assert (
        result.status
        is Task9AngelSpotFullReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
    )


@pytest.mark.parametrize(
    "market,reason_code",
    (
        (
            "NIFTY",
            Task9StartupReasonCode.WRONG_NIFTY_IDENTITY,
        ),
        (
            "SENSEX",
            Task9StartupReasonCode.WRONG_SENSEX_IDENTITY,
        ),
    ),
)
def test_identity_mismatch_is_fatal(
    market,
    reason_code,
):
    result = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            market,
            identity_verified=False,
        ),
    )

    assert (
        result.status
        is Task9AngelSpotFullReadinessStatus.FAILED_FATAL
    )
    assert result.reason_code is reason_code


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_unavailable_quote_is_retryable(market):
    result = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            market,
            status=(
                Task9AngelSpotFullProbeStatus.UNAVAILABLE
            ),
            reason="SANITIZED_FULL_QUOTE_UNAVAILABLE",
        ),
    )

    assert (
        result.status
        is Task9AngelSpotFullReadinessStatus.BLOCKED_RETRYABLE
    )


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_malformed_quote_is_fatal(market):
    result = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            market,
            status=(
                Task9AngelSpotFullProbeStatus.MALFORMED
            ),
            reason="SANITIZED_FULL_QUOTE_MALFORMED",
        ),
    )

    assert (
        result.status
        is Task9AngelSpotFullReadinessStatus.FAILED_FATAL
    )


def test_projection_keeps_markets_independent():
    report = _report()

    nifty = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof("NIFTY"),
    )

    after_nifty = (
        project_task9_angel_spot_full_to_report(
            report=report,
            readiness=nifty,
        )
    )

    assert (
        _spot_row(
            after_nifty,
            "NIFTY",
        ).readiness_status
        is Task9ProviderReadinessStatus.READY
    )

    assert (
        _spot_row(
            after_nifty,
            "SENSEX",
        ).readiness_status
        is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
    )

    sensex_failed = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            "SENSEX",
            status=(
                Task9AngelSpotFullProbeStatus.UNAVAILABLE
            ),
            reason="SANITIZED_SENSEX_UNAVAILABLE",
        ),
    )

    final = (
        project_task9_angel_spot_full_to_report(
            report=after_nifty,
            readiness=sensex_failed,
        )
    )

    assert (
        _spot_row(
            final,
            "NIFTY",
        ).readiness_status
        is Task9ProviderReadinessStatus.READY
    )

    assert (
        _spot_row(
            final,
            "SENSEX",
        ).readiness_status
        is Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
    )


def test_ready_projection_changes_only_selected_row():
    report = _report()

    readiness = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof("NIFTY"),
    )

    projected = (
        project_task9_angel_spot_full_to_report(
            report=report,
            readiness=readiness,
        )
    )

    assert (
        _spot_row(
            projected,
            "NIFTY",
        ).startup_semantic
        is None
    )

    assert (
        _spot_row(
            projected,
            "SENSEX",
        )
        == _spot_row(
            report,
            "SENSEX",
        )
    )


def test_retryable_projection_has_retryable_semantic():
    readiness = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            "SENSEX",
            status=(
                Task9AngelSpotFullProbeStatus.UNAVAILABLE
            ),
            reason="SANITIZED_PROVIDER_FAILURE",
        ),
    )

    projected = (
        project_task9_angel_spot_full_to_report(
            report=_report(),
            readiness=readiness,
        )
    )

    assert (
        _spot_row(
            projected,
            "SENSEX",
        ).startup_semantic
        is Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
    )


def test_projection_is_idempotent():
    readiness = evaluate_task9_angel_spot_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof("NIFTY"),
    )

    first = project_task9_angel_spot_full_to_report(
        report=_report(),
        readiness=readiness,
    )

    second = project_task9_angel_spot_full_to_report(
        report=first,
        readiness=readiness,
    )

    assert first.to_dict() == second.to_dict()


def test_wrong_token_is_rejected_by_contract():
    with pytest.raises(
        ValueError,
        match="spot market identity",
    ):
        Task9AngelSpotFullProofV1(
            proof_id="wrong-token",
            observed_at=NOW,
            market="NIFTY",
            exchange="NSE",
            token="wrong",
            status=(
                Task9AngelSpotFullProbeStatus.AVAILABLE
            ),
            provider_timestamp=NOW,
            ltp=25000.0,
            identity_verified=True,
        )


def test_secret_like_failure_reason_rejected():
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        _proof(
            "NIFTY",
            status=(
                Task9AngelSpotFullProbeStatus.UNAVAILABLE
            ),
            reason="raw_payload=provider-secret",
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelSpotFullProofV1(
            proof_id="unsafe",
            observed_at=NOW,
            market="NIFTY",
            exchange="NSE",
            token="99926000",
            status=(
                Task9AngelSpotFullProbeStatus.AVAILABLE
            ),
            provider_timestamp=NOW,
            ltp=25000.0,
            identity_verified=True,
            broker_order_submission=True,
        )
