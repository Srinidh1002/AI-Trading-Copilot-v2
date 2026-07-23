"""
Environment Manager

Loads, validates and manages environment variables
for the AI Trading Copilot.

Responsibilities
----------------
✓ Load Environment Variables
✓ Read Variables
✓ Update Runtime Variables
✓ Required Variable Validation
✓ Environment Summary
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class EnvironmentManager:

    def __init__(
        self,
        dotenv_path: str = ".env",
    ):

        self.dotenv_path = Path(dotenv_path)

        if self.dotenv_path.exists():

            load_dotenv(
                dotenv_path=self.dotenv_path,
                override=True,
            )

    # --------------------------------------------------

    @staticmethod
    def get(
        key: str,
        default: Any = None,
    ) -> Any:

        return os.getenv(
            key,
            default,
        )

    # --------------------------------------------------

    @staticmethod
    def set(
        key: str,
        value: Any,
    ):

        os.environ[key] = str(value)

    # --------------------------------------------------

    @staticmethod
    def exists(
        key: str,
    ) -> bool:

        return key in os.environ

    # --------------------------------------------------

    @staticmethod
    def remove(
        key: str,
    ) -> bool:

        return os.environ.pop(
            key,
            None,
        ) is not None

    # --------------------------------------------------

    @staticmethod
    def all() -> dict[str, str]:

        return dict(os.environ)

    # --------------------------------------------------

    @staticmethod
    def validate(
        required_keys: list[str],
    ) -> bool:

        return all(

            os.getenv(key)

            not in (

                None,

                "",

            )

            for key in required_keys

        )

    # --------------------------------------------------

    @staticmethod
    def missing(
        required_keys: list[str],
    ) -> list[str]:

        return [

            key

            for key in required_keys

            if os.getenv(key)

            in (

                None,

                "",

            )

        ]

    # --------------------------------------------------

    @staticmethod
    def masked(
        key: str,
    ) -> str | None:

        value = os.getenv(key)

        if value is None:

            return None

        if len(value) <= 8:

            return "*" * len(value)

        return (

            value[:4]

            + "*" * (len(value) - 8)

            + value[-4:]

        )

    # --------------------------------------------------

    def summary(self):

        return {

            "dotenv_file": str(

                self.dotenv_path

            ),

            "dotenv_exists": self.dotenv_path.exists(),

        }

    # --------------------------------------------------

    @staticmethod
    def reload():

        load_dotenv(
            override=True,
        )