"""
FYERS authentication lifecycle - canonical single authority.

This module is the ONLY place in the repository that reads FYERS
credential environment variables. Every other caller passes credentials
explicitly.

Responsibilities:
  * Load credentials from exactly one source.
  * Never log or print token values.
  * Detect an expired JWT before any FYERS call is made.
  * Classify FYERS error responses into safe reason codes.

Explicitly out of scope:
  * No order capability.
  * No live capital.
  * No automatic fallback.
  * No refresh-token flow. FYERS disabled validate-refresh-token
    ("Refresh token API is currently disabled to comply with SEBI
    regulations"). Access tokens expire daily at 06:30 IST and require
    manual OAuth re-auth via the FYERS web flow.
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

try:
    from dotenv import load_dotenv as _load_dotenv
    from dotenv import dotenv_values as _dotenv_values
except Exception:
    _load_dotenv = None
    _dotenv_values = None


# ---- Safe reason codes (loggable, never contain token material) ----
REASON_OK                = "OK"
REASON_AUTH_INVALID      = "AUTH_INVALID"
REASON_AUTH_EXPIRED      = "AUTH_EXPIRED"
REASON_AUTH_MISSING      = "AUTH_MISSING"
REASON_NETWORK_ERROR     = "NETWORK_ERROR"
REASON_RATE_LIMIT        = "RATE_LIMIT"
REASON_PROVIDER_ERROR    = "PROVIDER_ERROR"
REASON_MALFORMED         = "MALFORMED_RESPONSE"

_AUTH_INVALID_CODES = {-15, -16, -17, -8}
_RATE_LIMIT_CODES   = {429, -429}


@dataclass(frozen=True)
class FyersCredentialsV2:
    app_id: str
    secret_id: Optional[str]
    access_token: str
    refresh_token: Optional[str]
    redirect_uri: Optional[str]
    pin: Optional[str]
    source: str


class FyersAuthError(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        provider_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.reason_code = reason_code
        self.provider_code = provider_code


_FYERS_ENV_KEYS = (
    "FYERS_APP_ID",
    "FYERS_SECRET_ID",
    "FYERS_ACCESS_TOKEN",
    "FYERS_REFRESH_TOKEN",
    "FYERS_REDIRECT_URI",
    "FYERS_PIN",
    "FYERS_DATA_ONLY",
)


def build_fyers_child_env_v2(env_file: str, parent_env=None) -> dict[str, str]:
    """Return a child environment whose FYERS authority is the named .env file.

    ``load_dotenv(override=False)`` is intentionally retained for legacy callers;
    the canonical launcher uses this function instead so an inherited stale token
    cannot win over the token just written by daily OAuth.
    """
    if _dotenv_values is None:
        raise FyersAuthError(REASON_AUTH_MISSING, "python-dotenv unavailable")
    values = _dotenv_values(env_file)
    if not values:
        raise FyersAuthError(REASON_AUTH_MISSING, "canonical FYERS env file unreadable")
    child = dict(os.environ if parent_env is None else parent_env)
    for key in _FYERS_ENV_KEYS:
        child.pop(key, None)
    for key in _FYERS_ENV_KEYS:
        value = values.get(key)
        if value is not None:
            child[key] = str(value)
    if not child.get("FYERS_APP_ID") or not child.get("FYERS_ACCESS_TOKEN"):
        raise FyersAuthError(REASON_AUTH_MISSING, "canonical FYERS credentials missing")
    return child


def load_canonical_credentials_v2(env_file: str) -> FyersCredentialsV2:
    """Read-only canonical credential reader.

    Reads ONLY from the named env file. Does not mutate os.environ. Does not
    honor parent-process FYERS_* values. Use this in any process that must
    prove credentials come from a specific file, e.g. the preflight launcher.

    Raises FyersAuthError(REASON_AUTH_MISSING) if the file is unreadable or
    if FYERS_APP_ID or FYERS_ACCESS_TOKEN are missing from the file itself.
    Never prints token values.
    """
    if _dotenv_values is None:
        raise FyersAuthError(REASON_AUTH_MISSING, "python-dotenv unavailable")
    try:
        values = _dotenv_values(env_file)
    except Exception as exc:
        raise FyersAuthError(REASON_AUTH_MISSING, "canonical env unreadable") from exc
    if not values:
        raise FyersAuthError(REASON_AUTH_MISSING, "canonical env file empty")

    def _val(key):
        raw = values.get(key)
        return str(raw).strip() if raw is not None else ""

    app_id = _val("FYERS_APP_ID")
    access_token = _val("FYERS_ACCESS_TOKEN")
    secret_id = _val("FYERS_SECRET_ID") or None
    refresh_token = _val("FYERS_REFRESH_TOKEN") or None
    redirect_uri = _val("FYERS_REDIRECT_URI") or None
    pin = _val("FYERS_PIN") or None

    if not app_id:
        raise FyersAuthError(
            REASON_AUTH_MISSING, "FYERS_APP_ID missing in canonical env file"
        )
    if not access_token:
        raise FyersAuthError(
            REASON_AUTH_MISSING, "FYERS_ACCESS_TOKEN missing in canonical env file"
        )

    return FyersCredentialsV2(
        app_id=app_id,
        secret_id=secret_id,
        access_token=access_token,
        refresh_token=refresh_token,
        redirect_uri=redirect_uri,
        pin=pin,
        source=f"canonical:{env_file}",
    )


def load_fyers_credentials_v2(
    env_file: Optional[str] = None,
) -> FyersCredentialsV2:
    """
    Canonical credential reader.

    Precedence:
      1. Explicit env_file (if provided).
      2. Default .env in cwd (non-overriding).
      3. Already-set process environment (untouched).

    Raises FyersAuthError(REASON_AUTH_MISSING) if FYERS_APP_ID or
    FYERS_ACCESS_TOKEN are absent. Never prints token values.
    """
    if _load_dotenv is not None:
        _load_dotenv(env_file, override=False)

    app_id        = (os.getenv("FYERS_APP_ID")        or "").strip()
    access_token  = (os.getenv("FYERS_ACCESS_TOKEN")  or "").strip()
    secret_id     = (os.getenv("FYERS_SECRET_ID")     or "").strip() or None
    refresh_token = (os.getenv("FYERS_REFRESH_TOKEN") or "").strip() or None
    redirect_uri  = (os.getenv("FYERS_REDIRECT_URI")  or "").strip() or None
    pin           = (os.getenv("FYERS_PIN")           or "").strip() or None

    source = (
        f"env_file:{env_file}" if env_file
        else "process_env_or_default_env"
    )

    if not app_id:
        raise FyersAuthError(
            REASON_AUTH_MISSING, "FYERS_APP_ID not set"
        )
    if not access_token:
        raise FyersAuthError(
            REASON_AUTH_MISSING, "FYERS_ACCESS_TOKEN not set"
        )

    return FyersCredentialsV2(
        app_id=app_id,
        secret_id=secret_id,
        access_token=access_token,
        refresh_token=refresh_token,
        redirect_uri=redirect_uri,
        pin=pin,
        source=source,
    )


@dataclass(frozen=True)
class JwtExpiryV2:
    is_jwt: bool
    exp_epoch: Optional[int]
    iat_epoch: Optional[int]
    seconds_remaining: Optional[int]
    payload_keys: tuple


def decode_jwt_exp_v2(token: str) -> JwtExpiryV2:
    """
    Decode JWT payload to read exp/iat. Signature is not verified -
    we are checking timing only, not trust. Never prints the token.
    """
    if not token:
        return JwtExpiryV2(False, None, None, None, ())

    parts = token.split(".")
    if len(parts) != 3:
        return JwtExpiryV2(False, None, None, None, ())

    try:
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return JwtExpiryV2(False, None, None, None, ())

    now = int(time.time())
    exp = payload.get("exp")
    iat = payload.get("iat")

    return JwtExpiryV2(
        is_jwt=True,
        exp_epoch=int(exp) if exp is not None else None,
        iat_epoch=int(iat) if iat is not None else None,
        seconds_remaining=(int(exp) - now) if exp is not None else None,
        payload_keys=tuple(sorted(payload.keys())),
    )


def assert_fyers_token_current_v2(
    token: str,
    *,
    skew_seconds: int = 60,
) -> JwtExpiryV2:
    """
    Raise FyersAuthError(REASON_AUTH_EXPIRED) if exp is past or within skew.
    Raise FyersAuthError(REASON_AUTH_INVALID) if the token has no exp claim
    or is not a JWT.
    """
    info = decode_jwt_exp_v2(token)

    if not info.is_jwt:
        raise FyersAuthError(
            REASON_AUTH_INVALID,
            "access token is not a JWT; cannot verify expiry",
        )

    if info.exp_epoch is None:
        raise FyersAuthError(
            REASON_AUTH_INVALID,
            "access token JWT has no exp claim",
        )

    if (
        info.seconds_remaining is not None
        and info.seconds_remaining <= skew_seconds
    ):
        raise FyersAuthError(
            REASON_AUTH_EXPIRED,
            f"access token expired or within skew "
            f"({info.seconds_remaining}s remaining)",
        )

    return info


def classify_fyers_response_v2(
    response: Mapping[str, Any],
) -> Optional[FyersAuthError]:
    """
    Return FyersAuthError if the response is an FYERS error, else None.

    s=error can never be treated as market data by any caller that routes
    through this function.
    """
    if not isinstance(response, Mapping):
        return FyersAuthError(
            REASON_MALFORMED, "response is not a mapping"
        )

    status = response.get("s")
    code = response.get("code")
    message = str(response.get("message", ""))[:200]

    if status is None:
        return FyersAuthError(
            REASON_MALFORMED,
            "response has no 's' field",
            provider_code=code,
        )

    if status == "ok":
        return None

    if status == "error":
        if code in _AUTH_INVALID_CODES:
            return FyersAuthError(
                REASON_AUTH_INVALID,
                message or "auth invalid",
                provider_code=code,
            )
        if code in _RATE_LIMIT_CODES:
            return FyersAuthError(
                REASON_RATE_LIMIT,
                message or "rate limited",
                provider_code=code,
            )
        return FyersAuthError(
            REASON_PROVIDER_ERROR,
            message or "provider error",
            provider_code=code,
        )

    return FyersAuthError(
        REASON_MALFORMED,
        f"unrecognised status: {status!r}",
        provider_code=code,
    )


def classify_fyers_exception_v2(
    exc: BaseException,
) -> FyersAuthError:
    name = type(exc).__name__.lower()
    msg = str(exc)[:200]

    if "timeout" in name or "connection" in name or "socket" in name:
        return FyersAuthError(REASON_NETWORK_ERROR, msg or name)

    if "ratelimit" in name or "too many" in msg.lower():
        return FyersAuthError(REASON_RATE_LIMIT, msg or name)

    return FyersAuthError(REASON_PROVIDER_ERROR, msg or name)
@dataclass(frozen=True)
class FyersOAuthInputsV2:
    """Static OAuth inputs plus an optional current access token."""

    app_id: str
    secret_id: str
    redirect_uri: str
    access_token: str | None
    source: str


def load_fyers_oauth_inputs_v2(
    *,
    env_file: str | None = None,
) -> FyersOAuthInputsV2:
    """Load the canonical inputs required to perform FYERS daily OAuth.

    Unlike load_fyers_credentials_v2(), access_token is deliberately optional.
    This allows the official interactive OAuth flow to recover when yesterday's
    access token is expired or has been removed.

    This remains inside fyers_auth_v2.py so credential environment reads retain
    one canonical repository authority.
    """
    if _load_dotenv is not None:
        _load_dotenv(
            env_file,
            override=False,
        )

    app_id = (
        os.getenv(
            "FYERS_APP_ID"
        )
        or ""
    ).strip()

    secret_id = (
        os.getenv(
            "FYERS_SECRET_ID"
        )
        or ""
    ).strip()

    redirect_uri = (
        os.getenv(
            "FYERS_REDIRECT_URI"
        )
        or ""
    ).strip()

    access_token = (
        os.getenv(
            "FYERS_ACCESS_TOKEN"
        )
        or ""
    ).strip() or None

    source = (
        f"env_file:{env_file}"
        if env_file
        else "process_env_or_default_env"
    )

    if not app_id:
        raise FyersAuthError(
            REASON_AUTH_MISSING,
            "FYERS_APP_ID not set",
        )

    if not secret_id:
        raise FyersAuthError(
            REASON_AUTH_MISSING,
            "FYERS_SECRET_ID not set",
        )

    if not redirect_uri:
        raise FyersAuthError(
            REASON_AUTH_MISSING,
            "FYERS_REDIRECT_URI not set",
        )

    return FyersOAuthInputsV2(
        app_id=app_id,
        secret_id=secret_id,
        redirect_uri=redirect_uri,
        access_token=access_token,
        source=source,
    )
