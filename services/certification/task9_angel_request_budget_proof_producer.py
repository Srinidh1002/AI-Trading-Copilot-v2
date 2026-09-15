"""Task 9 Angel request-budget proof from concrete runtime structure.

No provider request, authentication request, historical request, or order
submission occurs here.

The producer verifies the existing controller/client/launcher ownership
boundaries and projects those facts into the Task 9 request-budget proof.
"""
from __future__ import annotations

import inspect
import threading
from datetime import datetime

from services.broker import shared_client
from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.broker.market_data_control import (
    MarketDataRequestController,
)
from services.certification import (
    task9_live_paper_certification_launcher as launcher_module,
)
from services.contracts.task9_angel_request_budget_proof_v1 import (
    Task9AngelRequestBudgetProbeStatus,
    Task9AngelRequestBudgetProofV1,
)


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def _source(
    value: object,
) -> str:
    try:
        return inspect.getsource(value)
    except (OSError, TypeError):
        return ""


def _contains_all(
    text: str,
    *items: str,
) -> bool:
    return bool(text) and all(
        item in text
        for item in items
    )


def produce_task9_angel_request_budget_proof(
    *,
    controller: MarketDataRequestController,
    client: AngelMarketDataClient,
    observed_at: datetime,
) -> Task9AngelRequestBudgetProofV1:
    """Verify existing request ownership without issuing a request."""

    if type(controller) is not MarketDataRequestController:
        raise TypeError("controller")

    if type(client) is not AngelMarketDataClient:
        raise TypeError("client")

    observed_at = _aware(
        observed_at,
        "observed_at",
    )

    required_wait_source = _source(
        MarketDataRequestController._required_wait
    )
    wait_for_slot_source = _source(
        MarketDataRequestController.wait_for_slot
    )
    record_rate_limit_source = _source(
        MarketDataRequestController.record_rate_limit
    )
    cache_read_source = _source(
        MarketDataRequestController.get_cached
    )
    cache_write_source = _source(
        MarketDataRequestController.cache
    )

    execute_source = _source(
        AngelMarketDataClient._execute_request
    )

    normal_factory_source = _source(
        shared_client.get_market_client
    )
    certification_factory_source = _source(
        shared_client.get_certification_market_client
    )

    launcher_source = _source(
        launcher_module
    )

    lock_type = type(
        threading.Lock()
    )

    controller_thread_safe = (
        type(getattr(controller, "_lock", None))
        is lock_type
        and _contains_all(
            wait_for_slot_source,
            "with self._lock",
            "_required_wait",
        )
        and _contains_all(
            cache_read_source,
            "with self._lock",
            "self._cache",
        )
        and _contains_all(
            cache_write_source,
            "with self._lock",
            "self._cache",
        )
    )

    account_wide_budget_owner = (
        getattr(
            client,
            "request_controller",
            None,
        )
        is controller
        and _contains_all(
            normal_factory_source,
            "get_shared_request_controller()",
            "AngelMarketDataClient",
        )
        and _contains_all(
            certification_factory_source,
            "get_shared_request_controller()",
            "AngelMarketDataClient",
        )
    )

    endpoint_scoped_cooldowns = (
        isinstance(
            getattr(
                controller,
                "_cooldown_until",
                None,
            ),
            dict,
        )
        and isinstance(
            getattr(
                controller,
                "_last_request_by_type",
                None,
            ),
            dict,
        )
        and _contains_all(
            required_wait_source,
            "_cooldown_until.get(request_type",
            "_last_request_by_type.get(",
            "request_type",
        )
        and _contains_all(
            record_rate_limit_source,
            "_cooldown_until",
            "request_type",
        )
    )

    historical_branch_isolated = (
        (
            controller.HISTORICAL_REQUEST_TYPE
            != controller.MARKET_QUOTE_REQUEST_TYPE
        )
        and hasattr(
            controller,
            "_historical_request_times",
        )
        and _contains_all(
            required_wait_source,
            "self.HISTORICAL_REQUEST_TYPE",
            "self._historical_budget_wait",
        )
        and (
            required_wait_source.count(
                "self._historical_budget_wait"
            )
            == 1
        )
    )

    historical_isolated_from_market_data = (
        historical_branch_isolated
        and controller.MARKET_QUOTE_REQUEST_TYPE
        != controller.HISTORICAL_REQUEST_TYPE
    )

    historical_isolated_from_greeks = (
        historical_branch_isolated
        and "Option Greeks"
        != controller.HISTORICAL_REQUEST_TYPE
    )

    angel_client_transport_retry_owner = (
        _contains_all(
            execute_source,
            "for attempt in range",
            "self.max_retries",
            "self.max_rate_limit_retries",
            "self._ensure_authenticated()",
            "self.request_controller.wait_for_slot",
            "continue",
        )
    )

    launcher_next_cycle_retry_only = (
        _contains_all(
            launcher_source,
            "while max_cycles is None or attempted < max_cycles",
            "self._run_one_cycle(",
            "self.sleep(float(cycle_interval_seconds))",
            "return None",
        )
    )

    transport_markers = (
        ".get_market_data(",
        ".getMarketData(",
        ".getCandleData(",
        ".optionGreek(",
        "SmartConnect(",
        ".generateSession(",
    )

    launcher_request_burst_owner = any(
        marker in launcher_source
        for marker in transport_markers
    )

    cache_owned_by_controller = (
        isinstance(
            getattr(
                controller,
                "_cache",
                None,
            ),
            dict,
        )
        and callable(
            getattr(
                controller,
                "get_cached",
                None,
            )
        )
        and callable(
            getattr(
                controller,
                "cache",
                None,
            )
        )
        and _contains_all(
            execute_source,
            "self.request_controller.get_cached",
            "self.request_controller.cache",
        )
    )

    ready = all((
        controller_thread_safe,
        account_wide_budget_owner,
        endpoint_scoped_cooldowns,
        historical_isolated_from_market_data,
        historical_isolated_from_greeks,
        angel_client_transport_retry_owner,
        launcher_next_cycle_retry_only,
        cache_owned_by_controller,
        not launcher_request_burst_owner,
    ))

    status = (
        Task9AngelRequestBudgetProbeStatus.READY
        if ready
        else Task9AngelRequestBudgetProbeStatus.INVALID
    )

    return Task9AngelRequestBudgetProofV1(
        proof_id=(
            "task9-angel-request-budget:"
            f"{observed_at.isoformat()}"
        ),
        observed_at=observed_at,
        status=status,
        controller_thread_safe=(
            controller_thread_safe
        ),
        account_wide_budget_owner=(
            account_wide_budget_owner
        ),
        endpoint_scoped_cooldowns=(
            endpoint_scoped_cooldowns
        ),
        historical_isolated_from_market_data=(
            historical_isolated_from_market_data
        ),
        historical_isolated_from_greeks=(
            historical_isolated_from_greeks
        ),
        angel_client_transport_retry_owner=(
            angel_client_transport_retry_owner
        ),
        launcher_next_cycle_retry_only=(
            launcher_next_cycle_retry_only
        ),
        launcher_request_burst_owner=(
            launcher_request_burst_owner
        ),
        cache_owned_by_controller=(
            cache_owned_by_controller
        ),
        source_ref=(
            "task9-request-budget-structural-verifier"
            if ready
            else None
        ),
        incident_ref=None,
        sanitized_reason=(
            None
            if ready
            else "TASK9_REQUEST_BUDGET_STRUCTURE_INVALID"
        ),
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "produce_task9_angel_request_budget_proof",
)
