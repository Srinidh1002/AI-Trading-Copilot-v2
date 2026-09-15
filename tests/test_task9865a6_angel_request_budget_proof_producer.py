from datetime import datetime, timezone
import inspect

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.broker.market_data_control import (
    MarketDataRequestController,
)
from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_request_budget_proof_producer import (
    produce_task9_angel_request_budget_proof,
)
from services.certification.task9_angel_request_budget_readiness import (
    Task9AngelRequestBudgetReadinessStatus,
    evaluate_task9_angel_request_budget,
)
from services.contracts.task9_angel_request_budget_proof_v1 import (
    Task9AngelRequestBudgetProbeStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    12,
    0,
    tzinfo=timezone.utc,
)


def _runtime():
    controller = (
        MarketDataRequestController(
            monotonic_function=lambda: 0.0,
            sleep_function=lambda _seconds: None,
        )
    )

    client = object.__new__(
        AngelMarketDataClient
    )

    client.request_controller = controller

    return controller, client


def test_real_structure_produces_ready_budget_proof():
    controller, client = _runtime()

    proof = (
        produce_task9_angel_request_budget_proof(
            controller=controller,
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelRequestBudgetProbeStatus.READY
    )

    assert proof.controller_thread_safe is True
    assert (
        proof.account_wide_budget_owner
        is True
    )
    assert (
        proof.endpoint_scoped_cooldowns
        is True
    )
    assert (
        proof.historical_isolated_from_market_data
        is True
    )
    assert (
        proof.historical_isolated_from_greeks
        is True
    )
    assert (
        proof.angel_client_transport_retry_owner
        is True
    )
    assert (
        proof.launcher_next_cycle_retry_only
        is True
    )
    assert (
        proof.launcher_request_burst_owner
        is False
    )
    assert (
        proof.cache_owned_by_controller
        is True
    )


def test_real_structure_passes_existing_readiness():
    controller, client = _runtime()

    proof = (
        produce_task9_angel_request_budget_proof(
            controller=controller,
            client=client,
            observed_at=NOW,
        )
    )

    result = (
        evaluate_task9_angel_request_budget(
            authority=(
                build_task9_angel_capability_session()
            ),
            proof=proof,
        )
    )

    assert (
        result.status
        is Task9AngelRequestBudgetReadinessStatus.READY
    )


def test_client_must_use_supplied_controller():
    controller, client = _runtime()

    other = MarketDataRequestController(
        monotonic_function=lambda: 0.0,
        sleep_function=lambda _seconds: None,
    )

    client.request_controller = other

    proof = (
        produce_task9_angel_request_budget_proof(
            controller=controller,
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelRequestBudgetProbeStatus.INVALID
    )
    assert (
        proof.account_wide_budget_owner
        is False
    )


def test_producer_performs_no_provider_request():
    controller, client = _runtime()

    # No SmartConnect/api/session fields are provided.
    # Any provider request attempt would fail this test.
    proof = (
        produce_task9_angel_request_budget_proof(
            controller=controller,
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelRequestBudgetProbeStatus.READY
    )


def test_proof_remains_paper_only():
    controller, client = _runtime()

    proof = (
        produce_task9_angel_request_budget_proof(
            controller=controller,
            client=client,
            observed_at=NOW,
        )
    )

    assert proof.execution_mode == "PAPER"
    assert (
        proof.broker_order_submission
        is False
    )
    assert (
        proof.live_execution_eligible
        is False
    )


def test_producer_signature_requires_existing_objects_only():
    parameters = inspect.signature(
        produce_task9_angel_request_budget_proof
    ).parameters

    assert tuple(parameters) == (
        "controller",
        "client",
        "observed_at",
    )
