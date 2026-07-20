"""
==============================================================
Session Manager
==============================================================

Responsibilities
----------------
✓ Own the SmartAPI client
✓ Ensure only one authenticated session exists
✓ Monitor session health
✓ Automatically reconnect when required
✓ Retry broker calls on failure
✓ Central access point for all services
==============================================================
"""

from __future__ import annotations

import time
from typing import Any, Callable

from services.broker.smart_api_client import SmartAPIClient


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

        self.client = SmartAPIClient()

        self.last_login = time.time()

        self.max_retries = 2

    # -----------------------------------------------------

    @property
    def api(self):
        return self.client.get_api()

    # -----------------------------------------------------

    def reconnect(self):

        print("\n[SessionManager] Reconnecting...")

        self.client.reconnect()

        self.last_login = time.time()

        print("[SessionManager] Connected.\n")

    # -----------------------------------------------------

    def is_alive(self) -> bool:

        try:

            profile = self.client.get_profile()

            return bool(profile)

        except Exception:

            return False

    # -----------------------------------------------------

    def ensure_session(self):

        if not self.is_alive():

            self.reconnect()

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

                return func(*args, **kwargs)

            except Exception as exc:

                attempt += 1

                print(
                    f"[SessionManager] Attempt "
                    f"{attempt} failed: {exc}"
                )

                if attempt > self.max_retries:
                    raise

                self.reconnect()

    # -----------------------------------------------------

    def summary(self):

        return {

            "Connected": self.is_alive(),

            "Client": self.client.get_profile().get("Client ID"),

            "User": self.client.get_profile().get("Name"),

            "Last Login": self.last_login,

            "Retries": self.max_retries,

        }