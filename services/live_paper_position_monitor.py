"""
Live Paper Position Monitor.

Connects:

AngelMarketDataClient
    -> AngelPaperTradePriceProvider
    -> PaperPositionLifecycleRunner
    -> PaperTradingEngine
    -> PaperTradeRepository

Responsibilities:
- Recover persisted paper trades.
- Fetch live option LTPs for open paper positions.
- Update paper-trade P&L.
- Allow PaperTradingEngine to auto-close positions at SL/target.
- Return a structured monitoring report.

IMPORTANT:
- Paper trading only.
- Market-data access only.
- No broker order placement.
- No real trade execution.
"""

from copy import deepcopy

from services.angel_paper_trade_price_provider import (
    AngelPaperTradePriceProvider,
)

from services.paper_position_lifecycle_runner import (
    PaperPositionLifecycleRunner,
)

from services.paper_trade_repository import (
    PaperTradeRepository,
)

from services.paper_trading_engine import (
    PaperTradingEngine,
)


class LivePaperPositionMonitor:

    def __init__(
        self,
        market_data_client,
        *,
        repository=None,
        paper_trading_engine=None,
        price_provider=None,
        lifecycle_runner=None,
        default_option_exchange="NFO",
        recover_on_start=True,
    ):
        if market_data_client is None:
            raise ValueError(
                "market_data_client is required."
            )

        self.market_data_client = (
            market_data_client
        )

        # -----------------------------------------------------
        # REPOSITORY
        # -----------------------------------------------------

        if repository is None:
            repository = (
                PaperTradeRepository()
            )

        self.repository = (
            repository
        )

        # -----------------------------------------------------
        # PAPER TRADING ENGINE
        # -----------------------------------------------------

        if paper_trading_engine is None:
            paper_trading_engine = (
                PaperTradingEngine(
                    repository=(
                        self.repository
                    ),
                    persist_state=True,
                )
            )

        self.paper_trading_engine = (
            paper_trading_engine
        )

        # -----------------------------------------------------
        # PRICE PROVIDER
        # -----------------------------------------------------

        if price_provider is None:
            price_provider = (
                AngelPaperTradePriceProvider(
                    market_data_client=(
                        self.market_data_client
                    ),
                    default_option_exchange=(
                        default_option_exchange
                    ),
                )
            )

        self.price_provider = (
            price_provider
        )

        # -----------------------------------------------------
        # LIFECYCLE RUNNER
        # -----------------------------------------------------

        if lifecycle_runner is None:
            lifecycle_runner = (
                PaperPositionLifecycleRunner(
                    paper_trading_engine=(
                        self.paper_trading_engine
                    ),
                    price_provider=(
                        self.price_provider
                    ),
                )
            )

        self.lifecycle_runner = (
            lifecycle_runner
        )

        self.recover_on_start = bool(
            recover_on_start
        )

        self._recovered = False

        self._recovered_trade_count = 0

    # ---------------------------------------------------------
    # RECOVERY
    # ---------------------------------------------------------

    def recover(
        self,
    ):
        """
        Recover persisted paper trades into the engine.
        """

        recovered = (
            self.paper_trading_engine.recover_trades(
                include_closed=True
            )
        )

        if recovered is None:
            recovered = []

        if not isinstance(
            recovered,
            list,
        ):
            raise ValueError(
                "recover_trades() must return a list."
            )

        self._recovered = True

        self._recovered_trade_count = len(
            recovered
        )

        return deepcopy(
            recovered
        )

    # ---------------------------------------------------------
    # RUN ONE MONITORING CYCLE
    # ---------------------------------------------------------

    def run_once(
        self,
        *,
        updated_at=None,
    ):
        """
        Run one complete paper-position monitoring cycle.
        """

        recovery_performed = False

        if (
            self.recover_on_start
            and not self._recovered
        ):
            self.recover()

            recovery_performed = True

        lifecycle_report = (
            self.lifecycle_runner.run_once(
                updated_at=updated_at
            )
        )

        if not isinstance(
            lifecycle_report,
            dict,
        ):
            raise ValueError(
                "Lifecycle runner must return a dictionary."
            )

        return {
            "status": (
                lifecycle_report.get(
                    "status",
                    "UNKNOWN",
                )
            ),
            "recovery_performed": (
                recovery_performed
            ),
            "recovered_trade_count": (
                self._recovered_trade_count
            ),
            "open_trades_found": (
                lifecycle_report.get(
                    "open_trades_found",
                    0,
                )
            ),
            "processed": (
                lifecycle_report.get(
                    "processed",
                    0,
                )
            ),
            "failed": (
                lifecycle_report.get(
                    "failed",
                    0,
                )
            ),
            "open_trades_after": (
                lifecycle_report.get(
                    "open_trades_after",
                    0,
                )
            ),
            "closed_trades_after": (
                lifecycle_report.get(
                    "closed_trades_after",
                    0,
                )
            ),
            "updated_at": (
                lifecycle_report.get(
                    "updated_at"
                )
            ),
            "results": deepcopy(
                lifecycle_report.get(
                    "results",
                    [],
                )
            ),
        }

    # ---------------------------------------------------------
    # ALIAS
    # ---------------------------------------------------------

    def run(
        self,
        *,
        updated_at=None,
    ):
        return self.run_once(
            updated_at=updated_at
        )

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    def get_status(
        self,
    ):
        return {
            "recovered": (
                self._recovered
            ),
            "recovered_trade_count": (
                self._recovered_trade_count
            ),
            "open_trades": (
                self.paper_trading_engine
                .count_open_trades()
            ),
            "closed_trades": (
                self.paper_trading_engine
                .count_closed_trades()
            ),
            "total_trades": (
                self.paper_trading_engine
                .count_trades()
            ),
        }