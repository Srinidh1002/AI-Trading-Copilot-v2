"""
Validators

Validation utilities for the
AI Trading Copilot.

Responsibilities
----------------
✓ Email Validation
✓ URL Validation
✓ Symbol Validation
✓ Numeric Validation
✓ Date Validation
✓ File Validation
✓ Dictionary Validation
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


class Validators:

    EMAIL_PATTERN = re.compile(
        r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )

    URL_PATTERN = re.compile(
        r"^https?://.+"
    )

    SYMBOL_PATTERN = re.compile(
        r"^[A-Za-z0-9^._-]+$"
    )

    # --------------------------------------------------

    @staticmethod
    def is_email(value: str) -> bool:

        return bool(

            Validators.EMAIL_PATTERN.fullmatch(

                value.strip()

            )

        )

    # --------------------------------------------------

    @staticmethod
    def is_url(value: str) -> bool:

        return bool(

            Validators.URL_PATTERN.fullmatch(

                value.strip()

            )

        )

    # --------------------------------------------------

    @staticmethod
    def is_symbol(value: str) -> bool:

        return bool(

            Validators.SYMBOL_PATTERN.fullmatch(

                value.strip()

            )

        )

    # --------------------------------------------------

    @staticmethod
    def is_non_empty(value: Any) -> bool:

        return value not in (

            None,

            "",

            [],

            {},

            (),

        )

    # --------------------------------------------------

    @staticmethod
    def is_int(value: Any) -> bool:

        try:

            int(value)

            return True

        except Exception:

            return False

    # --------------------------------------------------

    @staticmethod
    def is_float(value: Any) -> bool:

        try:

            float(value)

            return True

        except Exception:

            return False

    # --------------------------------------------------

    @staticmethod
    def is_positive_number(value: Any) -> bool:

        try:

            return float(value) > 0

        except Exception:

            return False

    # --------------------------------------------------

    @staticmethod
    def is_non_negative(value: Any) -> bool:

        try:

            return float(value) >= 0

        except Exception:

            return False

    # --------------------------------------------------

    @staticmethod
    def in_range(
        value: float,
        minimum: float,
        maximum: float,
    ) -> bool:

        return minimum <= value <= maximum

    # --------------------------------------------------

    @staticmethod
    def is_date(
        value: str,
        fmt: str = "%Y-%m-%d",
    ) -> bool:

        try:

            datetime.strptime(

                value,

                fmt,

            )

            return True

        except Exception:

            return False

    # --------------------------------------------------

    @staticmethod
    def file_exists(
        path: str | Path,
    ) -> bool:

        return Path(path).exists()

    # --------------------------------------------------

    @staticmethod
    def directory_exists(
        path: str | Path,
    ) -> bool:

        return Path(path).is_dir()

    # --------------------------------------------------

    @staticmethod
    def is_dict(
        value: Any,
    ) -> bool:

        return isinstance(

            value,

            dict,

        )

    # --------------------------------------------------

    @staticmethod
    def is_list(
        value: Any,
    ) -> bool:

        return isinstance(

            value,

            list,

        )

    # --------------------------------------------------

    @staticmethod
    def has_keys(
        dictionary: dict,
        required_keys: list[str],
    ) -> bool:

        return all(

            key in dictionary

            for key in required_keys

        )

    # --------------------------------------------------

    @staticmethod
    def validate_required(
        data: dict[str, Any],
        required: list[str],
    ) -> list[str]:

        return [

            key

            for key in required

            if key not in data

            or data[key] in (

                None,

                "",

            )

        ]

    # --------------------------------------------------

    @staticmethod
    def summary() -> dict[str, Any]:

        return {

            "module": "Validators",

            "status": "ready",

            "supported": [

                "email",

                "url",

                "symbol",

                "number",

                "date",

                "file",

                "dictionary",

            ],

        }