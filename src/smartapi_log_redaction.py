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



# SmartAPI logs request/response payload dictionaries on some failure
# and debug paths. These fields must therefore be treated as secrets
# even when they appear outside HTTP headers.
#
# Case-insensitive matching also covers camel-case variants such as
# clientCode. Snake-case aliases are included for local/adapter logs.
_SENSITIVE_FIELD_NAMES = (
    r"(?:"
    r"clientcode|client_code|"
    r"password|pin|"
    r"totp|totp_secret|"
    r"refreshToken|refresh_token|"
    r"jwtToken|jwt_token|"
    r"feedToken|feed_token"
    r")"
)

# Python dict repr / JSON / key=value where the value is quoted.
_SENSITIVE_QUOTED_FIELD_RE = re.compile(
    rf"""(?i)(['"]?{_SENSITIVE_FIELD_NAMES}['"]?\s*[:=]\s*)(['"])(.*?)(\2)"""
)

# Defensive support for unquoted forms such as:
# clientCode=ABC123
_SENSITIVE_BARE_FIELD_RE = re.compile(
    rf"""(?i)(['"]?{_SENSITIVE_FIELD_NAMES}['"]?\s*[:=]\s*)(?!['"])(?!\[REDACTED\])([^,\s}}\]]+)"""
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

    # SmartAPI request/response body credentials and tokens.
    text = _SENSITIVE_QUOTED_FIELD_RE.sub(
        lambda m: (
            m.group(1)
            + m.group(2)
            + "[REDACTED]"
            + m.group(2)
        ),
        text,
    )

    text = _SENSITIVE_BARE_FIELD_RE.sub(
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
