"""
API Key Manager

Secure storage and retrieval of API keys for the
AI Trading Copilot.

Responsibilities
----------------
✓ Register API Keys
✓ Retrieve API Keys
✓ Update API Keys
✓ Delete API Keys
✓ Environment Variable Support
✓ Key Validation
"""

from __future__ import annotations

import os
from typing import Any


class APIKeyManager:

    def __init__(self):

        self._keys: dict[str, str] = {}

    # --------------------------------------------------

    def register(
        self,
        service: str,
        api_key: str,
    ):

        self._keys[service.upper()] = api_key

    # --------------------------------------------------

    def load_from_environment(
        self,
        service: str,
        env_variable: str,
    ) -> bool:

        value = os.getenv(env_variable)

        if not value:

            return False

        self.register(
            service,
            value,
        )

        return True

    # --------------------------------------------------

    def get(
        self,
        service: str,
        default: str | None = None,
    ) -> str | None:

        return self._keys.get(
            service.upper(),
            default,
        )

    # --------------------------------------------------

    def exists(
        self,
        service: str,
    ) -> bool:

        return service.upper() in self._keys

    # --------------------------------------------------

    def update(
        self,
        service: str,
        api_key: str,
    ):

        self._keys[service.upper()] = api_key

    # --------------------------------------------------

    def remove(
        self,
        service: str,
    ) -> bool:

        return (
            self._keys.pop(
                service.upper(),
                None,
            )
            is not None
        )

    # --------------------------------------------------

    def validate(
        self,
        service: str,
    ) -> bool:

        key = self.get(service)

        return bool(
            key
            and isinstance(key, str)
            and len(key.strip()) > 10
        )

    # --------------------------------------------------

    def services(self):

        return sorted(
            self._keys.keys()
        )

    # --------------------------------------------------

    def masked_key(
        self,
        service: str,
    ) -> str | None:

        key = self.get(service)

        if not key:

            return None

        if len(key) <= 8:

            return "*" * len(key)

        return (

            key[:4]

            + "*" * (len(key) - 8)

            + key[-4:]

        )

    # --------------------------------------------------

    def summary(self):

        return {

            service: {

                "configured": True,

                "valid": self.validate(service),

                "key": self.masked_key(service),

            }

            for service in self.services()

        }

    # --------------------------------------------------

    def clear(self):

        self._keys.clear()