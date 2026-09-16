"""Redact SmartAPI authentication material from SDK log records.

This module does not modify the SmartAPI package and does not change
request/response behaviour.  It only sanitizes log text before handlers
emit it.
"""

from __future__ import annotations

import logging
import re


_AUTH_HEADER_RE = re.compile(
    r"""(?i)(['"]?Authorization['"]?\s*:\s*['"]?\s*Bearer\s+)([^'",}\s]+)"""
)

_PRIVATE_KEY_RE = re.compile(
    r"""(?i)(['"]?X-PrivateKey['"]?\s*:\s*['"]?)([^'",}\s]+)"""
)

_GENERIC_BEARER_RE = re.compile(
    r"""(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"""
)


def redact_text(value: object) -> str:
    """Return log-safe text with SmartAPI auth material removed."""
    text = str(value)

    text = _AUTH_HEADER_RE.sub(
        lambda m: m.group(1) + "[REDACTED]",
        text,
    )

    text = _PRIVATE_KEY_RE.sub(
        lambda m: m.group(1) + "[REDACTED]",
        text,
    )

    # Defence in depth in case a Bearer token appears outside a dict header.
    text = _GENERIC_BEARER_RE.sub(
        "Bearer [REDACTED]",
        text,
    )

    return text


class SmartApiSecretRedactionFilter(logging.Filter):
    """Sanitize the fully rendered message before logzero emits it."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            return True

        redacted = redact_text(rendered)

        if redacted != rendered:
            record.msg = redacted
            record.args = ()

        return True


def install_smartapi_log_redaction() -> None:
    """Install idempotent filtering on SmartAPI/logzero's logger."""
    logger = logging.getLogger("logzero_default")

    if not any(
        isinstance(f, SmartApiSecretRedactionFilter)
        for f in logger.filters
    ):
        logger.addFilter(SmartApiSecretRedactionFilter())

    for handler in logger.handlers:
        if not any(
            isinstance(f, SmartApiSecretRedactionFilter)
            for f in handler.filters
        ):
            handler.addFilter(SmartApiSecretRedactionFilter())
