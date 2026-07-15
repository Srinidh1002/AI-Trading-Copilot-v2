"""
Trading runtime configuration.

Provides one validated, immutable runtime configuration object
for live research, paper trading, and future user-facing trading
configuration.

The configuration is intentionally independent of broker order
execution. It describes runtime intent only.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass


DEFAULT_CAPITAL = 10_000.0
DEFAULT_RISK_PER_TRADE_PERCENT = 1.0
DEFAULT_UNDERLYING = "NIFTY"
DEFAULT_TRADING_MODE = "RESEARCH"
DEFAULT_PAPER_TRADING = True


SUPPORTED_TRADING_MODES = frozenset(
    {
        "RESEARCH",
        "PAPER",
    }
)


@dataclass(
    frozen=True,
    slots=True,
)
class TradingRuntimeConfig:
    """
    Immutable validated trading runtime configuration.

    This object does not authorize real broker orders.
    """

    capital: float = DEFAULT_CAPITAL

    risk_per_trade_percent: float = (
        DEFAULT_RISK_PER_TRADE_PERCENT
    )

    underlying: str = DEFAULT_UNDERLYING

    trading_mode: str = DEFAULT_TRADING_MODE

    paper_trading: bool = DEFAULT_PAPER_TRADING

    def __post_init__(self):
        normalized_capital = self._normalize_capital(
            self.capital
        )

        normalized_risk = self._normalize_risk_percent(
            self.risk_per_trade_percent
        )

        normalized_underlying = (
            self._normalize_underlying(
                self.underlying
            )
        )

        normalized_trading_mode = (
            self._normalize_trading_mode(
                self.trading_mode
            )
        )

        normalized_paper_trading = (
            self._normalize_paper_trading(
                self.paper_trading
            )
        )

        object.__setattr__(
            self,
            "capital",
            normalized_capital,
        )

        object.__setattr__(
            self,
            "risk_per_trade_percent",
            normalized_risk,
        )

        object.__setattr__(
            self,
            "underlying",
            normalized_underlying,
        )

        object.__setattr__(
            self,
            "trading_mode",
            normalized_trading_mode,
        )

        object.__setattr__(
            self,
            "paper_trading",
            normalized_paper_trading,
        )

    @staticmethod
    def _normalize_capital(value):
        if isinstance(value, bool):
            raise ValueError(
                "capital must be a positive number"
            )

        try:
            normalized = float(value)

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "capital must be a positive number"
            ) from exc

        if normalized <= 0:
            raise ValueError(
                "capital must be greater than zero"
            )

        return normalized

    @staticmethod
    def _normalize_risk_percent(value):
        if isinstance(value, bool):
            raise ValueError(
                "risk_per_trade_percent must be a number"
            )

        try:
            normalized = float(value)

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "risk_per_trade_percent must be a number"
            ) from exc

        if normalized <= 0:
            raise ValueError(
                "risk_per_trade_percent must be greater "
                "than zero"
            )

        if normalized > 100:
            raise ValueError(
                "risk_per_trade_percent must not exceed 100"
            )

        return normalized

    @staticmethod
    def _normalize_underlying(value):
        if not isinstance(value, str):
            raise ValueError(
                "underlying must be a string"
            )

        normalized = value.strip().upper()

        if not normalized:
            raise ValueError(
                "underlying cannot be empty"
            )

        return normalized

    @staticmethod
    def _normalize_trading_mode(value):
        if not isinstance(value, str):
            raise ValueError(
                "trading_mode must be a string"
            )

        normalized = value.strip().upper()

        if normalized not in SUPPORTED_TRADING_MODES:
            supported = ", ".join(
                sorted(
                    SUPPORTED_TRADING_MODES
                )
            )

            raise ValueError(
                "unsupported trading_mode: "
                f"{normalized}. "
                f"Supported modes: {supported}"
            )

        return normalized

    @staticmethod
    def _normalize_paper_trading(value):
        if not isinstance(value, bool):
            raise ValueError(
                "paper_trading must be a boolean"
            )

        return value

    @property
    def risk_budget(self):
        """
        Maximum configured capital risk for one trade.
        """

        return round(
            self.capital
            * (
                self.risk_per_trade_percent
                / 100.0
            ),
            4,
        )

    @property
    def real_orders_allowed(self):
        """
        Real broker orders are intentionally unavailable.
        """

        return False

    def to_dict(self):
        """
        Return an independent serializable configuration snapshot.
        """

        return deepcopy(
            {
                "capital": self.capital,
                "risk_per_trade_percent": (
                    self.risk_per_trade_percent
                ),
                "risk_budget": self.risk_budget,
                "underlying": self.underlying,
                "trading_mode": self.trading_mode,
                "paper_trading": self.paper_trading,
                "real_orders_allowed": (
                    self.real_orders_allowed
                ),
            }
        )


def build_trading_runtime_config(
    *,
    capital=DEFAULT_CAPITAL,
    risk_per_trade_percent=(
        DEFAULT_RISK_PER_TRADE_PERCENT
    ),
    underlying=DEFAULT_UNDERLYING,
    trading_mode=DEFAULT_TRADING_MODE,
    paper_trading=DEFAULT_PAPER_TRADING,
):
    """
    Build one validated runtime configuration.
    """

    return TradingRuntimeConfig(
        capital=capital,
        risk_per_trade_percent=(
            risk_per_trade_percent
        ),
        underlying=underlying,
        trading_mode=trading_mode,
        paper_trading=paper_trading,
    )