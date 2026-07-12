"""
Paper Trading Recovery Manager.

Coordinates safe recovery of persisted paper trades after an
application or runtime restart.

Responsibilities:
- Recover persisted trades through PaperTradingEngine.
- Classify recovered trades as OPEN or CLOSED.
- Detect invalid or duplicate recovered trade IDs.
- Fail closed when recovery cannot be completed safely.
- Return a structured recovery report.

IMPORTANT:
- PAPER TRADING ONLY.
- Does not place broker orders.
- Does not modify recovered positions.
"""


class PaperTradingRecoveryManager:

    STATUS_RECOVERED = "RECOVERED"
    STATUS_EMPTY = "EMPTY"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        paper_trading_engine,
        *,
        include_closed=True,
    ):
        if paper_trading_engine is None:
            raise ValueError(
                "paper_trading_engine is required."
            )

        recover_method = getattr(
            paper_trading_engine,
            "recover_trades",
            None,
        )

        if not callable(recover_method):
            raise ValueError(
                "paper_trading_engine must expose "
                "a recover_trades method."
            )

        if not isinstance(
            include_closed,
            bool,
        ):
            raise ValueError(
                "include_closed must be boolean."
            )

        self.paper_trading_engine = (
            paper_trading_engine
        )

        self.include_closed = (
            include_closed
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def recover(
        self,
    ):
        """
        Recover persisted paper trades.

        Returns a structured report and fails closed if:
        - the engine raises an exception;
        - recovery returns invalid data;
        - a recovered trade is invalid;
        - duplicate trade IDs are detected.
        """

        try:
            recovered = (
                self.paper_trading_engine
                .recover_trades(
                    include_closed=(
                        self.include_closed
                    )
                )
            )

        except Exception as exc:
            return self._build_failed_result(
                code="RECOVERY_ERROR",
                message=(
                    "Paper-trading recovery failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if recovered is None:
            return self._build_failed_result(
                code="INVALID_RECOVERY_RESULT",
                message=(
                    "Paper-trading recovery returned None."
                ),
            )

        if isinstance(
            recovered,
            (str, bytes, dict),
        ):
            return self._build_failed_result(
                code="INVALID_RECOVERY_RESULT",
                message=(
                    "Paper-trading recovery must return "
                    "an iterable collection of trades."
                ),
            )

        try:
            recovered_trades = list(
                recovered
            )

        except TypeError:
            return self._build_failed_result(
                code="INVALID_RECOVERY_RESULT",
                message=(
                    "Paper-trading recovery returned "
                    "a non-iterable result."
                ),
            )

        if not recovered_trades:
            return self._build_result(
                status=self.STATUS_EMPTY,
                success=True,
                code="NO_PERSISTED_TRADES",
                message=(
                    "No persisted paper trades were found."
                ),
                recovered_trades=[],
                open_trades=[],
                closed_trades=[],
            )

        validation = (
            self._validate_recovered_trades(
                recovered_trades
            )
        )

        if not validation["valid"]:
            return self._build_failed_result(
                code=validation["code"],
                message=validation["message"],
            )

        open_trades = []
        closed_trades = []

        for trade in recovered_trades:
            status = self._normalize_text(
                self._trade_value(
                    trade,
                    "status",
                )
            )

            if status == "OPEN":
                open_trades.append(
                    trade
                )

            elif status == "CLOSED":
                closed_trades.append(
                    trade
                )

        return self._build_result(
            status=self.STATUS_RECOVERED,
            success=True,
            code="RECOVERY_COMPLETE",
            message=(
                "Persisted paper trades were recovered "
                "successfully."
            ),
            recovered_trades=(
                recovered_trades
            ),
            open_trades=open_trades,
            closed_trades=closed_trades,
        )

    def recover_trades(
        self,
    ):
        """
        Alias for recover().
        """

        return self.recover()

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_recovered_trades(
        self,
        trades,
    ):
        seen_trade_ids = set()

        for index, trade in enumerate(
            trades
        ):
            trade_id = self._trade_value(
                trade,
                "trade_id",
            )

            if not isinstance(
                trade_id,
                str,
            ) or not trade_id.strip():
                return {
                    "valid": False,
                    "code": "INVALID_RECOVERED_TRADE",
                    "message": (
                        "Recovered paper trade at index "
                        f"{index} has an invalid trade_id."
                    ),
                }

            normalized_trade_id = (
                trade_id.strip()
            )

            if (
                normalized_trade_id
                in seen_trade_ids
            ):
                return {
                    "valid": False,
                    "code": "DUPLICATE_TRADE_ID",
                    "message": (
                        "Duplicate recovered paper trade ID "
                        f"detected: {normalized_trade_id}."
                    ),
                }

            seen_trade_ids.add(
                normalized_trade_id
            )

            status = self._normalize_text(
                self._trade_value(
                    trade,
                    "status",
                )
            )

            if status not in {
                "OPEN",
                "CLOSED",
            }:
                return {
                    "valid": False,
                    "code": "INVALID_RECOVERED_TRADE",
                    "message": (
                        "Recovered paper trade "
                        f"{normalized_trade_id} has an "
                        "invalid status."
                    ),
                }

        return {
            "valid": True,
            "code": "VALID",
            "message": (
                "Recovered paper trades are valid."
            ),
        }

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _trade_value(
        trade,
        field_name,
        default=None,
    ):
        if isinstance(
            trade,
            dict,
        ):
            return trade.get(
                field_name,
                default,
            )

        return getattr(
            trade,
            field_name,
            default,
        )

    @staticmethod
    def _normalize_text(
        value,
    ):
        if value is None:
            return ""

        return str(
            value
        ).strip().upper()

    @staticmethod
    def _safe_trade_copy(
        trade,
    ):
        if isinstance(
            trade,
            dict,
        ):
            return dict(
                trade
            )

        if hasattr(
            trade,
            "as_dict",
        ):
            return trade.as_dict()

        if hasattr(
            trade,
            "to_dict",
        ):
            return trade.to_dict()

        return trade

    def _build_result(
        self,
        *,
        status,
        success,
        code,
        message,
        recovered_trades,
        open_trades,
        closed_trades,
    ):
        safe_recovered = [
            self._safe_trade_copy(
                trade
            )
            for trade in recovered_trades
        ]

        safe_open = [
            self._safe_trade_copy(
                trade
            )
            for trade in open_trades
        ]

        safe_closed = [
            self._safe_trade_copy(
                trade
            )
            for trade in closed_trades
        ]

        return {
            "status": status,
            "success": bool(
                success
            ),
            "failed": not bool(
                success
            ),
            "code": code,
            "message": message,
            "include_closed": (
                self.include_closed
            ),
            "recovered_count": len(
                safe_recovered
            ),
            "open_count": len(
                safe_open
            ),
            "closed_count": len(
                safe_closed
            ),
            "recovered_trades": (
                safe_recovered
            ),
            "open_trades": safe_open,
            "closed_trades": (
                safe_closed
            ),
        }

    def _build_failed_result(
        self,
        *,
        code,
        message,
    ):
        return self._build_result(
            status=self.STATUS_FAILED,
            success=False,
            code=code,
            message=message,
            recovered_trades=[],
            open_trades=[],
            closed_trades=[],
        )