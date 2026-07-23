"""
==============================================================
Session Manager
==============================================================

Singleton wrapper around the shared AngelMarketDataClient.

Responsibilities
----------------
✓ Own the shared AngelMarketDataClient instance
✓ Provide backward-compatible API access
✓ Execute broker requests
✓ Re-authenticate automatically when required
==============================================================
"""

from __future__ import annotations

import time
from typing import Any, Callable

from services.broker.shared_client import (
    get_market_client,
)


class SessionManager:

    _instance = None

    # -----------------------------------------------------

    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    # -----------------------------------------------------

    def __init__(self):

        if hasattr(self, "_initialized"):
            return

        self._initialized = True

        # Use the ONE shared market client
        self.client = get_market_client()

        self.last_login = time.time()

        self.max_retries = 2

    # -----------------------------------------------------

    @property
    def api(self):

        self.client.login()

        return self.client.api

    # -----------------------------------------------------

    def reconnect(self):

        self.client.login(
            force=True,
        )

        self.last_login = time.time()

    # -----------------------------------------------------

    def is_alive(self) -> bool:

        try:

            self.client.login()

            return True

        except Exception:

            return False

    # -----------------------------------------------------

    def ensure_session(self):

        self.client.login()

    # -----------------------------------------------------

    def execute(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:

        attempt = 0

        while attempt <= self.max_retries:

            try:

                self.ensure_session()

                return func(
                    *args,
                    **kwargs,
                )

            except Exception:

                attempt += 1

                if attempt > self.max_retries:
                    raise

                self.reconnect()

    # -----------------------------------------------------

    def summary(self):

        return {

            "Connected": self.is_alive(),

            "Last Login": self.last_login,

            "Retries": self.max_retries,

        }