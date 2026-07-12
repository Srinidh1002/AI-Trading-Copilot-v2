"""
Paper Trading Risk Guard.

Provides fail-closed safety controls before a new paper trade is allowed.

Controls:
- Kill switch.
- Maximum open positions.
- Maximum trades opened per day.
- Maximum daily realized loss.
- Duplicate open-position blocking.
- Input validation.

IMPORTANT:
- PAPER TRADING ONLY.
- This service does not place broker orders.
"""

from datetime import datetime, timezone
import math


class PaperTradingRiskGuard:

    def __init__(
        self,
        *,
        max_open_positions=1,
        max_trades_per_day=5,
        max_daily_realized_loss=500.0,
        block_duplicate_positions=True,
        kill_switch=False,
        now_function=None,
    ):
        self.max_open_positions = (
            self._validate_positive_integer(
                max_open_positions,
                "max_open_positions",
            )
        )

        self.max_trades_per_day = (
            self._validate_positive_integer(
                max_trades_per_day,
                "max_trades_per_day",
            )
        )

        self.max_daily_realized_loss = (
            self._validate_positive_number(
                max_daily_realized_loss,
                "max_daily_realized_loss",
            )
        )

        if not isinstance(
            block_duplicate_positions,
            bool,
        ):
            raise ValueError(
                "block_duplicate_positions must be boolean."
            )

        if not isinstance(
            kill_switch,
            bool,
        ):
            raise ValueError(
                "kill_switch must be boolean."
            )

        self.block_duplicate_positions = (
            block_duplicate_positions
        )

        self.kill_switch = (
            kill_switch
        )

        self.now_function = (
            now_function
            if now_function is not None
            else (
                lambda: datetime.now(
                    timezone.utc
                )
            )
        )

        if not callable(
            self.now_function
        ):
            raise ValueError(
                "now_function must be callable."
            )

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    @staticmethod
    def _validate_positive_integer(
        value,
        field_name,
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
        ):
            raise ValueError(
                f"{field_name} must be a positive integer."
            )

        return value

    @staticmethod
    def _validate_positive_number(
        value,
        field_name,
    ):
        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{field_name} must be a positive number."
            )

        try:
            value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} must be a positive number."
            ) from exc

        if (
            not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(
                f"{field_name} must be a positive number."
            )

        return value

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

    @classmethod
    def _parse_datetime(
        cls,
        value,
    ):
        if isinstance(
            value,
            datetime,
        ):
            parsed = value

        elif isinstance(
            value,
            str,
        ):
            text = value.strip()

            if not text:
                return None

            if text.endswith(
                "Z"
            ):
                text = (
                    text[:-1]
                    + "+00:00"
                )

            try:
                parsed = (
                    datetime.fromisoformat(
                        text
                    )
                )

            except ValueError:
                return None

        else:
            return None

        return parsed

    def _current_datetime(
        self,
    ):
        value = (
            self.now_function()
        )

        parsed = (
            self._parse_datetime(
                value
            )
        )

        if parsed is None:
            raise RuntimeError(
                "now_function returned an invalid datetime."
            )

        return parsed

    @staticmethod
    def _same_calendar_day(
        first,
        second,
    ):
        return (
            first.date()
            == second.date()
        )

    # ---------------------------------------------------------
    # TRADE CLASSIFICATION
    # ---------------------------------------------------------

    @classmethod
    def _is_open_trade(
        cls,
        trade,
    ):
        status = (
            cls._normalize_text(
                cls._trade_value(
                    trade,
                    "status",
                )
            )
        )

        return status == "OPEN"

    @classmethod
    def _is_closed_trade(
        cls,
        trade,
    ):
        status = (
            cls._normalize_text(
                cls._trade_value(
                    trade,
                    "status",
                )
            )
        )

        return status == "CLOSED"

    # ---------------------------------------------------------
    # DAILY STATISTICS
    # ---------------------------------------------------------

    def count_open_positions(
        self,
        trades,
    ):
        return sum(
            1
            for trade in trades
            if self._is_open_trade(
                trade
            )
        )

    def count_trades_opened_today(
        self,
        trades,
        now=None,
    ):
        if now is None:
            now = (
                self._current_datetime()
            )
        else:
            now = (
                self._parse_datetime(
                    now
                )
            )

            if now is None:
                raise ValueError(
                    "now must be a valid datetime."
                )

        count = 0

        for trade in trades:
            opened_at = (
                self._parse_datetime(
                    self._trade_value(
                        trade,
                        "opened_at",
                    )
                )
            )

            if (
                opened_at is not None
                and self._same_calendar_day(
                    opened_at,
                    now,
                )
            ):
                count += 1

        return count

    def get_daily_realized_pnl(
        self,
        trades,
        now=None,
    ):
        if now is None:
            now = (
                self._current_datetime()
            )
        else:
            now = (
                self._parse_datetime(
                    now
                )
            )

            if now is None:
                raise ValueError(
                    "now must be a valid datetime."
                )

        total = 0.0

        for trade in trades:
            if not self._is_closed_trade(
                trade
            ):
                continue

            closed_at = (
                self._parse_datetime(
                    self._trade_value(
                        trade,
                        "closed_at",
                    )
                )
            )

            if (
                closed_at is None
                or not self._same_calendar_day(
                    closed_at,
                    now,
                )
            ):
                continue

            realized_pnl = (
                self._trade_value(
                    trade,
                    "realized_pnl",
                    0.0,
                )
            )

            if realized_pnl is None:
                realized_pnl = 0.0

            try:
                realized_pnl = float(
                    realized_pnl
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                raise ValueError(
                    "Trade realized_pnl must be numeric."
                ) from exc

            if not math.isfinite(
                realized_pnl
            ):
                raise ValueError(
                    "Trade realized_pnl must be finite."
                )

            total += realized_pnl

        return total

    # ---------------------------------------------------------
    # DUPLICATE DETECTION
    # ---------------------------------------------------------

    def find_duplicate_open_position(
        self,
        candidate,
        trades,
    ):
        if not self.block_duplicate_positions:
            return None

        candidate_underlying = (
            self._normalize_text(
                self._trade_value(
                    candidate,
                    "underlying",
                )
            )
        )

        candidate_symbol = (
            self._normalize_text(
                self._trade_value(
                    candidate,
                    "option_symbol",
                )
            )
        )

        candidate_token = (
            self._normalize_text(
                self._trade_value(
                    candidate,
                    "symboltoken",
                )
            )
        )

        for trade in trades:
            if not self._is_open_trade(
                trade
            ):
                continue

            trade_underlying = (
                self._normalize_text(
                    self._trade_value(
                        trade,
                        "underlying",
                    )
                )
            )

            trade_symbol = (
                self._normalize_text(
                    self._trade_value(
                        trade,
                        "option_symbol",
                    )
                )
            )

            trade_token = (
                self._normalize_text(
                    self._trade_value(
                        trade,
                        "symboltoken",
                    )
                )
            )

            same_token = (
                candidate_token
                and trade_token
                and candidate_token
                == trade_token
            )

            same_symbol = (
                candidate_symbol
                and trade_symbol
                and candidate_symbol
                == trade_symbol
            )

            same_underlying = (
                candidate_underlying
                and trade_underlying
                and candidate_underlying
                == trade_underlying
            )

            if (
                same_token
                or same_symbol
                or same_underlying
            ):
                return trade

        return None

    # ---------------------------------------------------------
    # KILL SWITCH
    # ---------------------------------------------------------

    def enable_kill_switch(
        self,
    ):
        self.kill_switch = True

    def disable_kill_switch(
        self,
    ):
        self.kill_switch = False

    # ---------------------------------------------------------
    # RISK DECISION
    # ---------------------------------------------------------

    @staticmethod
    def _decision(
        allowed,
        code,
        message,
        *,
        metrics=None,
    ):
        return {
            "allowed": bool(
                allowed
            ),
            "code": str(
                code
            ),
            "message": str(
                message
            ),
            "metrics": (
                dict(
                    metrics
                )
                if metrics is not None
                else {}
            ),
        }

    def evaluate(
        self,
        candidate,
        trades,
        *,
        now=None,
    ):
        """
        Evaluate whether a new paper trade may be opened.

        Fail-closed:
        Any invalid input or unexpected calculation error blocks entry.
        """

        try:
            if candidate is None:
                return self._decision(
                    False,
                    "INVALID_CANDIDATE",
                    "Paper trade candidate is missing.",
                )

            if trades is None:
                return self._decision(
                    False,
                    "INVALID_TRADE_HISTORY",
                    "Trade history is missing.",
                )

            try:
                trades = list(
                    trades
                )

            except TypeError:
                return self._decision(
                    False,
                    "INVALID_TRADE_HISTORY",
                    "Trade history must be iterable.",
                )

            if self.kill_switch:
                return self._decision(
                    False,
                    "KILL_SWITCH_ACTIVE",
                    (
                        "Paper trading is blocked because "
                        "the kill switch is active."
                    ),
                )

            current_time = (
                self._current_datetime()
                if now is None
                else self._parse_datetime(
                    now
                )
            )

            if current_time is None:
                return self._decision(
                    False,
                    "INVALID_CURRENT_TIME",
                    "Current time is invalid.",
                )

            open_positions = (
                self.count_open_positions(
                    trades
                )
            )

            trades_today = (
                self.count_trades_opened_today(
                    trades,
                    now=current_time,
                )
            )

            daily_realized_pnl = (
                self.get_daily_realized_pnl(
                    trades,
                    now=current_time,
                )
            )

            daily_realized_loss = max(
                0.0,
                -daily_realized_pnl,
            )

            metrics = {
                "open_positions": (
                    open_positions
                ),
                "max_open_positions": (
                    self.max_open_positions
                ),
                "trades_today": (
                    trades_today
                ),
                "max_trades_per_day": (
                    self.max_trades_per_day
                ),
                "daily_realized_pnl": (
                    daily_realized_pnl
                ),
                "daily_realized_loss": (
                    daily_realized_loss
                ),
                "max_daily_realized_loss": (
                    self.max_daily_realized_loss
                ),
            }

            if (
                open_positions
                >= self.max_open_positions
            ):
                return self._decision(
                    False,
                    "MAX_OPEN_POSITIONS_REACHED",
                    (
                        "Maximum number of open paper "
                        "positions has been reached."
                    ),
                    metrics=metrics,
                )

            if (
                trades_today
                >= self.max_trades_per_day
            ):
                return self._decision(
                    False,
                    "MAX_DAILY_TRADES_REACHED",
                    (
                        "Maximum number of paper trades "
                        "for the day has been reached."
                    ),
                    metrics=metrics,
                )

            if (
                daily_realized_loss
                >= self.max_daily_realized_loss
            ):
                return self._decision(
                    False,
                    "MAX_DAILY_LOSS_REACHED",
                    (
                        "Maximum daily realized paper-trading "
                        "loss has been reached."
                    ),
                    metrics=metrics,
                )

            duplicate = (
                self.find_duplicate_open_position(
                    candidate,
                    trades,
                )
            )

            if duplicate is not None:
                duplicate_trade_id = (
                    self._trade_value(
                        duplicate,
                        "trade_id",
                    )
                )

                metrics[
                    "duplicate_trade_id"
                ] = (
                    duplicate_trade_id
                )

                return self._decision(
                    False,
                    "DUPLICATE_OPEN_POSITION",
                    (
                        "A matching paper position is "
                        "already open."
                    ),
                    metrics=metrics,
                )

            return self._decision(
                True,
                "ALLOWED",
                (
                    "Paper trade passed all configured "
                    "risk-guard checks."
                ),
                metrics=metrics,
            )

        except Exception as exc:
            return self._decision(
                False,
                "RISK_GUARD_ERROR",
                (
                    "Paper trade was blocked because the "
                    "risk guard could not complete safely: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    def is_allowed(
        self,
        candidate,
        trades,
        *,
        now=None,
    ):
        return self.evaluate(
            candidate,
            trades,
            now=now,
        )[
            "allowed"
        ]