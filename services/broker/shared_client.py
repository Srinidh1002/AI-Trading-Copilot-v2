"""
Shared Angel One read-only market-data clients.

Normal runtime and certification retain separate lazy client singletons so
their retry policies remain independent, but both clients share one
process-wide request controller because Angel One applies REST rate limits
by client code rather than by Python client instance.

No broker order submission.
"""

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.broker.market_data_control import (
    MarketDataRequestController,
)
from services.broker.angel_endpoint_policies import (
    CONSERVATIVE_HISTORICAL_POLICY,
    CONSERVATIVE_MARKET_QUOTE_POLICY,
)


_market_client = None
_certification_market_client = None
_request_controller = None


def get_shared_request_controller():
    """Return the account-wide Angel read-only request controller."""

    global _request_controller

    if _request_controller is None:
        _request_controller = MarketDataRequestController(
            historical_request_interval_seconds=1.0,
            market_quote_request_interval_seconds=(
                1.0
                / CONSERVATIVE_MARKET_QUOTE_POLICY.requests_per_second
            ),
            historical_requests_per_second=(
                CONSERVATIVE_HISTORICAL_POLICY.requests_per_second
            ),
            historical_requests_per_minute=(
                CONSERVATIVE_HISTORICAL_POLICY.requests_per_minute
            ),
            historical_requests_per_hour=(
                CONSERVATIVE_HISTORICAL_POLICY.requests_per_hour
            ),
        )

    return _request_controller


def get_market_client():
    """Return the normal shared read-only market-data client."""

    global _market_client

    if _market_client is None:
        _market_client = AngelMarketDataClient(
            request_controller=(
                get_shared_request_controller()
            )
        )

    return _market_client


def get_certification_market_client():
    """Return the deterministic certification read-only client.

    Certification policy:
    - one total attempt for ordinary provider/network failures;
    - no rate-limit retry;
    - the same account-wide request pacing/budget authority used by normal
      runtime;
    - persistent request history within the process.

    The retry policy is client-specific. The provider request budget is not.
    """

    global _certification_market_client

    if _certification_market_client is None:
        _certification_market_client = (
            AngelMarketDataClient(
                max_retries=1,
                max_rate_limit_retries=0,
                request_controller=(
                    get_shared_request_controller()
                ),
            )
        )

    return _certification_market_client


def reset_shared_market_clients_for_testing():
    """Reset lazy shared state for deterministic unit tests only."""

    global _market_client
    global _certification_market_client
    global _request_controller

    _market_client = None
    _certification_market_client = None
    _request_controller = None
