"""
Paper Position Lifecycle Runner.

Coordinates live price updates for existing paper trades.

Responsibilities:
- Read currently open paper trades.
- Obtain a current option price from an injected price provider.
- Validate the returned price.
- Call PaperTradingEngine.update_price(..., auto_close=True).
- Allow the existing engine to handle P&L, stop-loss, target,
  lifecycle audit, and persistence.
- Isolate failures between individual paper trades.
- Return a structured run report.

IMPORTANT:
- Paper trading only.
- No broker order placement.
- No real trade execution.
"""

from copy import deepcopy
from datetime import datetime, timezone
import math


class PaperPositionLifecycleRunner:
    """
    Manage one lifecycle update cycle for open paper positions.

    Parameters
    ----------
    paper_trading_engine:
        Existing PaperTradingEngine instance.

    price_provider:
        Callable receiving one paper-trade dictionary and returning
        the current option price.

        Example:

            def price_provider(trade):
                return 125.50
    """

    def __init__(
        self,
        paper_trading_engine,
        price_provider,
    ):
        if paper_trading_engine is None:
            raise ValueError(
                "paper_trading_engine is required."
            )

        if price_provider is None:
            raise ValueError(
                "price_provider is required."
            )

        if not callable(price_provider):
            raise ValueError(
                "price_provider must be callable."
            )

        self.paper_trading_engine = (
            paper_trading_engine
        )

        self.price_provider = (
            price_provider
        )

    # ---------------------------------------------------------
    # PRICE VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def validate_price(
        price,
    ):
        """
        Validate a current option price.

        Returns
        -------
        float
            Validated positive finite price.

        Raises
        ------
        ValueError
            If the price is invalid.
        """

        if isinstance(
            price,
            bool,
        ):
            raise ValueError(
                "Current price must be numeric, "
                "not boolean."
            )

        try:

            validated_price = float(
                price
            )

        except (
            TypeError,
            ValueError,
        ) as exc:

            raise ValueError(
                "Current price must be numeric."
            ) from exc

        if not math.isfinite(
            validated_price
        ):
            raise ValueError(
                "Current price must be finite."
            )

        if validated_price <= 0:

            raise ValueError(
                "Current price must be greater than zero."
            )

        return validated_price

    # ---------------------------------------------------------
    # TRADE ID EXTRACTION
    # ---------------------------------------------------------

    @staticmethod
    def _get_trade_id(
        trade,
    ):
        if not isinstance(
            trade,
            dict,
        ):
            raise ValueError(
                "Open trade must be a dictionary."
            )

        trade_id = trade.get(
            "trade_id"
        )

        if not isinstance(
            trade_id,
            str,
        ):

            raise ValueError(
                "Open trade must contain a valid trade_id."
            )

        trade_id = (
            trade_id.strip()
        )

        if not trade_id:

            raise ValueError(
                "Open trade must contain a valid trade_id."
            )

        return trade_id

    # ---------------------------------------------------------
    # RUN ONE TRADE
    # ---------------------------------------------------------

    def process_trade(
        self,
        trade,
        *,
        updated_at=None,
    ):
        """
        Process one open paper trade.

        A price-provider failure or invalid price raises an exception.
        The batch-level run() method isolates such failures.
        """

        trade_id = (
            self._get_trade_id(
                trade
            )
        )

        current_price = (
            self.price_provider(
                deepcopy(
                    trade
                )
            )
        )

        current_price = (
            self.validate_price(
                current_price
            )
        )

        updated_trade = (
            self.paper_trading_engine.update_price(
                trade_id=trade_id,
                current_price=current_price,
                updated_at=updated_at,
                auto_close=True,
            )
        )

        return {
            "trade_id": trade_id,
            "status": "PROCESSED",
            "current_price": (
                current_price
            ),
            "trade": deepcopy(
                updated_trade
            ),
            "error": None,
        }

    # ---------------------------------------------------------
    # RUN ALL OPEN TRADES
    # ---------------------------------------------------------

    def run(
        self,
        *,
        updated_at=None,
    ):
        """
        Process all currently open paper trades.

        Failure isolation:
        - One failed trade does not stop other trades.
        - Failures are returned in the report.
        - No real orders are placed.

        Returns
        -------
        dict
            Structured lifecycle run report.
        """

        if updated_at is None:

            updated_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

        open_trades = (
            self.paper_trading_engine.get_open_trades()
        )

        if open_trades is None:

            open_trades = []

        if not isinstance(
            open_trades,
            list,
        ):

            raise ValueError(
                "get_open_trades() must return a list."
            )

        results = []

        processed = 0

        failed = 0

        for trade in open_trades:

            trade_id = None

            try:

                trade_id = (
                    self._get_trade_id(
                        trade
                    )
                )

                result = (
                    self.process_trade(
                        trade,
                        updated_at=updated_at,
                    )
                )

                results.append(
                    result
                )

                processed += 1

            except Exception as exc:

                results.append(
                    {
                        "trade_id": (
                            trade_id
                        ),
                        "status": "ERROR",
                        "current_price": None,
                        "trade": None,
                        "error": str(
                            exc
                        ),
                    }
                )

                failed += 1

        open_after = (
            self.paper_trading_engine.count_open_trades()
        )

        closed_after = (
            self.paper_trading_engine.count_closed_trades()
        )

        return {
            "status": (
                "COMPLETED"
                if failed == 0
                else "COMPLETED_WITH_ERRORS"
            ),
            "updated_at": updated_at,
            "open_trades_found": (
                len(
                    open_trades
                )
            ),
            "processed": processed,
            "failed": failed,
            "open_trades_after": (
                open_after
            ),
            "closed_trades_after": (
                closed_after
            ),
            "results": deepcopy(
                results
            ),
        }

    # ---------------------------------------------------------
    # ALIAS
    # ---------------------------------------------------------

    def run_once(
        self,
        *,
        updated_at=None,
    ):
        """
        Alias for one lifecycle processing cycle.
        """

        return self.run(
            updated_at=updated_at
        )