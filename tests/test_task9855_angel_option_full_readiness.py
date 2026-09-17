from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_option_full_projection import (
    project_task9_angel_option_full_to_report,
)
from services.certification.task9_angel_option_full_readiness import (
    Task9AngelOptionFullReadinessStatus,
    evaluate_task9_angel_option_full,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_option_full_proof_v1 import (
    Task9AngelOptionFullProbeStatus,
    Task9AngelOptionFullProofV1,
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
    20,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _runtime():
    return build_task9_runtime_config(
        runtime_config_id="task9855-runtime",
        runtime_config_version="1",
        campaign_registry_location="task9855/campaign.json",
        campaign_id="task9855-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9855-run",
        official_root="task9855/official",
        certification_registry_root="task9855/registry",
        authoritative_persistence_root="task9855/persistence",
        dashboard_publication_location="task9855/dashboard.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9855-canonical.v1",
            "session": "task9855-session.v1",
            "risk": "task9855-risk.v1",
            "contract_selection": "task9855-contract.v1",
            "lifecycle": "task9855-lifecycle.v1",
            "counting": "task9855-counting.v1",
            "failure_disposition": "task9855-failure.v1",
            "contract_spread": "task9855-spread.v1",
            "liquidity": "task9855-liquidity.v1",
            "minimum_risk_reward": "task9855-rr.v1",
            "stop_target": "task9855-stop-target.v1",
            "portfolio_concurrency": "task9855-concurrency.v1",
        },
    )


def _authority():
    return build_task9_angel_capability_session()


def _exchange(market):
    return "NFO" if market == "NIFTY" else "BFO"


def _proof(
    market,
    *,
    status=Task9AngelOptionFullProbeStatus.AVAILABLE,
    requested=10,
    fetched=10,
    unfetched=0,
    malformed=0,
    age=1.0,
    identity=True,
    reason=None,
):
    has_fetched = fetched > 0

    return Task9AngelOptionFullProofV1(
        proof_id=f"task9855-{market.lower()}",
        observed_at=NOW,
        market=market,
        exchange=_exchange(market),
        status=status,
        requested_contract_count=requested,
        fetched_contract_count=fetched,
        unfetched_contract_count=unfetched,
        malformed_contract_count=malformed,
        oldest_provider_timestamp=(
            NOW - timedelta(seconds=age)
            if has_fetched
            else None
        ),
        newest_provider_timestamp=(
            NOW
            if has_fetched
            else None
        ),
        exchange_identity_verified=identity,
        source_ref=(
            "angel-option-full"
            if has_fetched
            else None
        ),
        incident_ref=(
            None
            if status
            is Task9AngelOptionFullProbeStatus.AVAILABLE
            else f"incident-task9855-{market.lower()}"
        ),
        sanitized_reason=reason,
    )


def _report():
    return build_task9_provider_capability_report(
        _runtime()
    )


def _row(report, market):
    exchange = _exchange(market)

    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_OPTION_FULL
            and state.capability
            is Task9ProviderCapability.OPTION_FULL_QUOTES
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
def test_complete_fresh_full_capability_is_ready(market):
    result = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(market),
    )

    assert (
        result.status
        is Task9AngelOptionFullReadinessStatus.READY
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert result.partial_response is False


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_partial_fetched_unfetched_response_still_proves_capability(
    market,
):
    proof = _proof(
        market,
        status=(
            Task9AngelOptionFullProbeStatus.PARTIAL
        ),
        requested=10,
        fetched=8,
        unfetched=2,
        malformed=0,
        reason="SANITIZED_PARTIAL_RESPONSE",
    )

    result = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=proof,
    )

    assert (
        result.status
        is Task9AngelOptionFullReadinessStatus.READY
    )
    assert result.partial_response is True
    assert result.fetched_contract_count == 8
    assert result.unfetched_contract_count == 2


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_partial_malformed_contract_does_not_fail_provider_capability(
    market,
):
    proof = _proof(
        market,
        status=(
            Task9AngelOptionFullProbeStatus.PARTIAL
        ),
        requested=10,
        fetched=9,
        unfetched=0,
        malformed=1,
        reason="SANITIZED_ONE_CONTRACT_REJECTED",
    )

    result = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=proof,
    )

    assert (
        result.status
        is Task9AngelOptionFullReadinessStatus.READY
    )
    assert result.malformed_contract_count == 1


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_unavailable_batch_is_retryable(market):
    result = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            market,
            status=(
                Task9AngelOptionFullProbeStatus.UNAVAILABLE
            ),
            requested=10,
            fetched=0,
            unfetched=10,
            malformed=0,
            reason="SANITIZED_OPTION_FULL_UNAVAILABLE",
        ),
    )

    assert (
        result.status
        is Task9AngelOptionFullReadinessStatus.BLOCKED_RETRYABLE
    )


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_stale_fetched_batch_is_retryable(market):
    runtime = _runtime()

    result = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=runtime,
        proof=_proof(
            market,
            age=(
                runtime.option_quote_max_age_seconds
                + 0.001
            ),
        ),
    )

    assert (
        result.status
        is Task9AngelOptionFullReadinessStatus.BLOCKED_RETRYABLE
    )


@pytest.mark.parametrize(
    "market",
    ("NIFTY", "SENSEX"),
)
def test_wrong_exchange_identity_is_fatal(market):
    result = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            market,
            identity=False,
        ),
    )

    assert (
        result.status
        is Task9AngelOptionFullReadinessStatus.FAILED_FATAL
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.WRONG_OPTION_EXCHANGE
    )


def test_nfo_and_bfo_projection_are_independent():
    report = _report()

    nifty = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof("NIFTY"),
    )

    report = project_task9_angel_option_full_to_report(
        report=report,
        readiness=nifty,
    )

    assert (
        _row(
            report,
            "NIFTY",
        ).readiness_status
        is Task9ProviderReadinessStatus.READY
    )

    assert (
        _row(
            report,
            "SENSEX",
        ).readiness_status
        is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
    )

    sensex = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            "SENSEX",
            status=(
                Task9AngelOptionFullProbeStatus.UNAVAILABLE
            ),
            requested=10,
            fetched=0,
            unfetched=10,
            reason="SANITIZED_BFO_UNAVAILABLE",
        ),
    )

    report = project_task9_angel_option_full_to_report(
        report=report,
        readiness=sensex,
    )

    assert (
        _row(
            report,
            "NIFTY",
        ).readiness_status
        is Task9ProviderReadinessStatus.READY
    )

    assert (
        _row(
            report,
            "SENSEX",
        ).readiness_status
        is Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
    )


def test_partial_projection_is_ready_but_preserves_counts():
    readiness = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof(
            "NIFTY",
            status=(
                Task9AngelOptionFullProbeStatus.PARTIAL
            ),
            requested=10,
            fetched=8,
            unfetched=2,
            reason="SANITIZED_PARTIAL_RESPONSE",
        ),
    )

    report = project_task9_angel_option_full_to_report(
        report=_report(),
        readiness=readiness,
    )

    row = _row(report, "NIFTY")

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert row.startup_semantic is None
    assert row.metadata[
        "fetched_contract_count"
    ] == 8
    assert row.metadata[
        "unfetched_contract_count"
    ] == 2
    assert row.metadata[
        "partial_response"
    ] is True


def test_projection_is_idempotent():
    readiness = evaluate_task9_angel_option_full(
        authority=_authority(),
        runtime_config=_runtime(),
        proof=_proof("NIFTY"),
    )

    first = project_task9_angel_option_full_to_report(
        report=_report(),
        readiness=readiness,
    )

    second = project_task9_angel_option_full_to_report(
        report=first,
        readiness=readiness,
    )

    assert first.to_dict() == second.to_dict()


def test_contract_accounting_must_balance():
    with pytest.raises(
        ValueError,
        match="contract accounting",
    ):
        _proof(
            "NIFTY",
            requested=10,
            fetched=8,
            unfetched=1,
            malformed=0,
        )


def test_zero_fetched_partial_is_invalid():
    with pytest.raises(
        ValueError,
        match="PARTIAL requires fetched",
    ):
        _proof(
            "NIFTY",
            status=(
                Task9AngelOptionFullProbeStatus.PARTIAL
            ),
            requested=10,
            fetched=0,
            unfetched=10,
            reason="SANITIZED_PARTIAL",
        )


def test_secret_like_reason_rejected():
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        _proof(
            "NIFTY",
            status=(
                Task9AngelOptionFullProbeStatus.UNAVAILABLE
            ),
            requested=10,
            fetched=0,
            unfetched=10,
            reason="raw_payload=secret",
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelOptionFullProofV1(
            proof_id="unsafe",
            observed_at=NOW,
            market="NIFTY",
            exchange="NFO",
            status=(
                Task9AngelOptionFullProbeStatus.AVAILABLE
            ),
            requested_contract_count=1,
            fetched_contract_count=1,
            unfetched_contract_count=0,
            malformed_contract_count=0,
            oldest_provider_timestamp=NOW,
            newest_provider_timestamp=NOW,
            exchange_identity_verified=True,
            broker_order_submission=True,
        )
