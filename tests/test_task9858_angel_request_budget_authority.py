from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_request_budget_readiness import (
    Task9AngelRequestBudgetReadinessStatus,
    evaluate_task9_angel_request_budget,
)
from services.contracts.task9_angel_request_budget_proof_v1 import (
    Task9AngelRequestBudgetProbeStatus,
    Task9AngelRequestBudgetProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    9,
    30,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _authority():
    return build_task9_angel_capability_session()


def _proof(
    *,
    status=Task9AngelRequestBudgetProbeStatus.READY,
    thread_safe=True,
    account_owner=True,
    endpoint_cooldowns=True,
    historical_market_isolated=True,
    historical_greeks_isolated=True,
    transport_retry_owner=True,
    next_cycle_retry_only=True,
    launcher_burst_owner=False,
    cache_owner=True,
    reason=None,
):
    return Task9AngelRequestBudgetProofV1(
        proof_id="task9858-budget",
        observed_at=NOW,
        status=status,
        controller_thread_safe=thread_safe,
        account_wide_budget_owner=account_owner,
        endpoint_scoped_cooldowns=endpoint_cooldowns,
        historical_isolated_from_market_data=(
            historical_market_isolated
        ),
        historical_isolated_from_greeks=(
            historical_greeks_isolated
        ),
        angel_client_transport_retry_owner=(
            transport_retry_owner
        ),
        launcher_next_cycle_retry_only=(
            next_cycle_retry_only
        ),
        launcher_request_burst_owner=(
            launcher_burst_owner
        ),
        cache_owned_by_controller=cache_owner,
        source_ref=(
            "market-data-request-controller"
            if status
            is Task9AngelRequestBudgetProbeStatus.READY
            else None
        ),
        incident_ref=(
            None
            if status
            is Task9AngelRequestBudgetProbeStatus.READY
            else "incident-task9858-budget"
        ),
        sanitized_reason=reason,
    )


def test_canonical_request_budget_authority_is_ready():
    result = evaluate_task9_angel_request_budget(
        authority=_authority(),
        proof=_proof(),
    )

    assert (
        result.status
        is Task9AngelRequestBudgetReadinessStatus.READY
    )
    assert (
        result.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )


def test_controller_must_be_thread_safe():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            thread_safe=False,
        )


def test_account_wide_budget_has_single_owner():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            account_owner=False,
        )


def test_endpoint_cooldowns_are_required():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            endpoint_cooldowns=False,
        )


def test_historical_throttle_must_not_block_market_data():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            historical_market_isolated=False,
        )


def test_historical_throttle_must_not_block_greeks():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            historical_greeks_isolated=False,
        )


def test_angel_client_owns_bounded_transport_retry():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            transport_retry_owner=False,
        )


def test_launcher_may_only_retry_next_cycle():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            next_cycle_retry_only=False,
        )


def test_launcher_must_not_own_request_burst():
    with pytest.raises(
        ValueError,
        match="launcher must not own request bursts",
    ):
        _proof(
            launcher_burst_owner=True,
        )


def test_controller_owns_cache():
    with pytest.raises(
        ValueError,
        match="READY request budget proof incomplete",
    ):
        _proof(
            cache_owner=False,
        )


def test_retryable_controller_block_is_not_fatal():
    result = evaluate_task9_angel_request_budget(
        authority=_authority(),
        proof=_proof(
            status=(
                Task9AngelRequestBudgetProbeStatus.BLOCKED_RETRYABLE
            ),
            reason="SANITIZED_CONTROLLER_COOLDOWN",
        ),
    )

    assert (
        result.status
        is Task9AngelRequestBudgetReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
    )


def test_invalid_ownership_is_fatal():
    result = evaluate_task9_angel_request_budget(
        authority=_authority(),
        proof=_proof(
            status=(
                Task9AngelRequestBudgetProbeStatus.INVALID
            ),
            launcher_burst_owner=True,
            reason="SANITIZED_RETRY_OWNERSHIP_INVALID",
        ),
    )

    assert (
        result.status
        is Task9AngelRequestBudgetReadinessStatus.FAILED_FATAL
    )


def test_secret_like_reason_rejected():
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        _proof(
            status=(
                Task9AngelRequestBudgetProbeStatus.BLOCKED_RETRYABLE
            ),
            reason="raw_exception=secret",
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelRequestBudgetProofV1(
            proof_id="unsafe-budget",
            observed_at=NOW,
            status=(
                Task9AngelRequestBudgetProbeStatus.READY
            ),
            controller_thread_safe=True,
            account_wide_budget_owner=True,
            endpoint_scoped_cooldowns=True,
            historical_isolated_from_market_data=True,
            historical_isolated_from_greeks=True,
            angel_client_transport_retry_owner=True,
            launcher_next_cycle_retry_only=True,
            launcher_request_burst_owner=False,
            cache_owned_by_controller=True,
            broker_order_submission=True,
        )
