"""
Credential Manager

Manages broker credentials and service credentials
used throughout the AI Trading Copilot.

Responsibilities
----------------
✓ Store Credentials
✓ Retrieve Credentials
✓ Update Credentials
✓ Remove Credentials
✓ Environment Variable Loading
✓ Credential Validation
"""

from __future__ import annotations

import os
from typing import Any


class CredentialManager:

    def __init__(self):

        self._credentials: dict[str, dict[str, Any]] = {}

    # --------------------------------------------------

    def register(
        self,
        service: str,
        **credentials: Any,
    ):

        self._credentials[
            service.upper()
        ] = credentials

    # --------------------------------------------------

    def load_from_environment(
        self,
        service: str,
        mapping: dict[str, str],
    ) -> bool:

        values = {}

        for field, env_name in mapping.items():

            value = os.getenv(env_name)

            if value is None:

                return False

            values[field] = value

        self.register(
            service,
            **values,
        )

        return True

    # --------------------------------------------------

    def get(
        self,
        service: str,
    ) -> dict[str, Any] | None:

        return self._credentials.get(
            service.upper()
        )

    # --------------------------------------------------

    def update(
        self,
        service: str,
        **credentials: Any,
    ):

        service = service.upper()

        existing = self._credentials.get(
            service,
            {},
        )

        existing.update(credentials)

        self._credentials[service] = existing

    # --------------------------------------------------

    def remove(
        self,
        service: str,
    ) -> bool:

        return (

            self._credentials.pop(
                service.upper(),
                None,
            )

            is not None

        )

    # --------------------------------------------------

    def exists(
        self,
        service: str,
    ) -> bool:

        return service.upper() in self._credentials

    # --------------------------------------------------

    def validate(
        self,
        service: str,
        required_fields: list[str],
    ) -> bool:

        creds = self.get(service)

        if creds is None:

            return False

        return all(

            field in creds

            and str(creds[field]).strip()

            for field in required_fields

        )

    # --------------------------------------------------

    @staticmethod
    def _mask(
        value: Any,
    ) -> str:

        value = str(value)

        if len(value) <= 8:

            return "*" * len(value)

        return (

            value[:4]

            + "*" * (len(value) - 8)

            + value[-4:]

        )

    # --------------------------------------------------

    def masked_credentials(
        self,
        service: str,
    ) -> dict[str, str] | None:

        creds = self.get(service)

        if creds is None:

            return None

        return {

            key: self._mask(value)

            for key, value in creds.items()

        }

    # --------------------------------------------------

    def services(self):

        return sorted(
            self._credentials.keys()
        )

    # --------------------------------------------------

    def summary(self):

        return {

            service: {

                "configured": True,

                "fields": len(

                    self._credentials[service]

                ),

                "credentials": self.masked_credentials(

                    service

                ),

            }

            for service in self.services()

        }

    # --------------------------------------------------

    def clear(self):

        self._credentials.clear()