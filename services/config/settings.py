"""
Application Settings

Centralized application settings for the
AI Trading Copilot.

Responsibilities
----------------
✓ Default Settings
✓ User Overrides
✓ Runtime Updates
✓ Reset to Defaults
✓ Export Settings
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_SETTINGS = {

    # -------------------------------------------------
    # Application
    # -------------------------------------------------

    "APP_NAME": "AI Trading Copilot",

    "APP_VERSION": "2.0",

    "ENVIRONMENT": "development",

    "DEBUG": True,

    # -------------------------------------------------
    # Trading
    # -------------------------------------------------

    "PAPER_TRADING": True,

    "AUTO_TRADING": False,

    "DEFAULT_CAPITAL": 100000,

    "MAX_TRADES_PER_DAY": 10,

    "MAX_POSITION_SIZE": 0.20,

    "DEFAULT_STOPLOSS_PERCENT": 1.5,

    "DEFAULT_TARGET_PERCENT": 3.0,

    "RISK_PER_TRADE": 1.0,

    # -------------------------------------------------
    # Market
    # -------------------------------------------------

    "MARKET": "INDIA",

    "INDEX": "NIFTY",

    "SYMBOL": "^NSEI",

    "TIMEFRAME": "5m",

    "REFRESH_INTERVAL": 5,

    # -------------------------------------------------
    # AI
    # -------------------------------------------------

    "AI_ENABLED": True,

    "CONFIDENCE_THRESHOLD": 70,

    "USE_NEWS": True,

    "USE_SENTIMENT": True,

    "USE_OPTION_CHAIN": True,

    # -------------------------------------------------
    # Logging
    # -------------------------------------------------

    "LOG_LEVEL": "INFO",

    "SAVE_LOGS": True,

    # -------------------------------------------------
    # Notifications
    # -------------------------------------------------

    "NOTIFICATIONS": True,

    "SOUND_ALERTS": False,

    "EMAIL_ALERTS": False,

    # -------------------------------------------------
    # Reports
    # -------------------------------------------------

    "AUTO_EXPORT_REPORTS": False,

    "REPORT_DIRECTORY": "reports",

    # -------------------------------------------------
    # Database
    # -------------------------------------------------

    "DATABASE_PATH": "database/trades.db",

}


class Settings:

    def __init__(self):

        self._settings = deepcopy(DEFAULT_SETTINGS)

    # --------------------------------------------------

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self._settings.get(

            key,

            default,

        )

    # --------------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
    ):

        self._settings[key] = value

    # --------------------------------------------------

    def update(
        self,
        values: dict[str, Any],
    ):

        self._settings.update(values)

    # --------------------------------------------------

    def remove(
        self,
        key: str,
    ):

        self._settings.pop(

            key,

            None,

        )

    # --------------------------------------------------

    def reset(self):

        self._settings = deepcopy(

            DEFAULT_SETTINGS

        )

    # --------------------------------------------------

    def as_dict(self) -> dict[str, Any]:

        return deepcopy(

            self._settings

        )

    # --------------------------------------------------

    def keys(self):

        return list(

            self._settings.keys()

        )

    # --------------------------------------------------

    def values(self):

        return list(

            self._settings.values()

        )

    # --------------------------------------------------

    def items(self):

        return self._settings.items()

    # --------------------------------------------------

    def exists(
        self,
        key: str,
    ) -> bool:

        return key in self._settings

    # --------------------------------------------------

    def summary(self):

        return {

            "total_settings": len(

                self._settings

            ),

            "environment": self.get(

                "ENVIRONMENT"

            ),

            "market": self.get(

                "MARKET"

            ),

            "paper_trading": self.get(

                "PAPER_TRADING"

            ),

            "auto_trading": self.get(

                "AUTO_TRADING"

            ),

        }