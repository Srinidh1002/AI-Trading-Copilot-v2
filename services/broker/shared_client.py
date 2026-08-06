"""
Shared Angel One read-only market-data clients.

Normal runtime and certification use separate lazy singletons so their
retry policies cannot be changed accidentally through environment state.

No broker order submission.
"""

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.broker.market_data_control import (
    MarketDataRequestController,
)


_market_client = None
_certification_market_client = None


def get_market_client():
    """Return the normal shared read-only market-data client."""

    global _market_client

    if _market_client is None:
        _market_client = AngelMarketDataClient()

    return _market_client


def get_certification_market_client():
    """Return the deterministic Task 8 certification client.

    Certification policy:
    - one total attempt for ordinary provider/network failures;
    - no rate-limit retry;
    - one-second historical pacing;
    - centralized rolling historical budgets;
    - persistent singleton request history within the process.
    """

    global _certification_market_client

    if _certification_market_client is None:
        request_controller = MarketDataRequestController(
            historical_request_interval_seconds=1.0,
            historical_requests_per_second=1,
            historical_requests_per_minute=120,
            historical_requests_per_hour=4000,
        )

        _certification_market_client = (
            AngelMarketDataClient(
                max_retries=1,
                max_rate_limit_retries=0,
                request_controller=request_controller,
            )
        )

    return _certification_market_client


def reset_shared_market_clients_for_testing():
    """Reset lazy singleton state for deterministic unit tests only."""

    global _market_client
    global _certification_market_client

    _market_client = None
    _certification_market_client = None
