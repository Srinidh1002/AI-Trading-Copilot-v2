"""Canonical FYERS daily interactive OAuth bootstrap.

The module never automates or bypasses FYERS login / 2FA.

If the current access token is missing, invalid, expired or near expiry, the
official FYERS authorization page is opened. The user completes FYERS login in
the browser and a loopback-only HTTP callback receives the authorization code.

The authorization code and access token are never printed.
No order API and no broker fallback exist in this module.
"""

from __future__ import annotations

import os
import secrets
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from services.broker.fyers_auth_v2 import (
    REASON_AUTH_EXPIRED,
    REASON_AUTH_INVALID,
    FyersAuthError,
    FyersCredentialsV2,
    FyersOAuthInputsV2,
    assert_fyers_token_current_v2,
    classify_fyers_response_v2,
    load_fyers_credentials_v2,
    load_fyers_oauth_inputs_v2,
)


class FyersDailyAuthError(RuntimeError):
    """Daily interactive FYERS authentication failed."""


@dataclass(frozen=True)
class FyersDailyAuthResultV2:
    status: str
    seconds_remaining: int | None
    token_replaced: bool
    provider_verified: bool


def _atomic_replace_env_value_v2(
    env_file: str | Path,
    key: str,
    value: str,
) -> None:
    path = Path(env_file).resolve()

    if not path.exists():
        raise FyersDailyAuthError(f"env file does not exist: {path}")

    if not key:
        raise ValueError("key is required")

    if not value:
        raise ValueError("value is required")

    raw = path.read_bytes()

    bom = raw.startswith(b"\xef\xbb\xbf")

    payload = raw[3:] if bom else raw

    text = (
        payload.decode("utf-8")
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    lines = text.splitlines()

    replacement = f"{key}={value}"

    found = False
    output: list[str] = []

    for line in lines:
        if line.startswith(key + "="):
            if found:
                continue

            output.append(replacement)

            found = True
        else:
            output.append(line)

    if not found:
        output.append(replacement)

    final_text = "\n".join(output).rstrip("\n") + "\n"

    final_payload = final_text.encode("utf-8")

    if bom:
        final_payload = b"\xef\xbb\xbf" + final_payload

    temporary = path.with_name(path.name + ".fyers-auth.tmp")

    try:
        temporary.write_bytes(final_payload)

        os.replace(
            temporary,
            path,
        )

    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _loopback_target_v2(
    redirect_uri: str,
) -> tuple[str, int, str]:
    parsed = urlparse(str(redirect_uri or "").strip())

    if parsed.scheme.lower() != "http":
        raise FyersDailyAuthError("FYERS redirect URI must use loopback http")

    host = (parsed.hostname or "").lower()

    if host not in {
        "127.0.0.1",
        "localhost",
    }:
        raise FyersDailyAuthError("FYERS redirect URI must use localhost or 127.0.0.1")

    if parsed.port is None:
        raise FyersDailyAuthError("FYERS redirect URI must include an explicit port")

    return (
        host,
        int(parsed.port),
        parsed.path or "/",
    )


def _capture_loopback_auth_code_v2(
    *,
    auth_url: str,
    redirect_uri: str,
    expected_state: str,
    browser_open: Callable[[str], object] = webbrowser.open,
    timeout_seconds: int = 180,
) -> str:
    host, port, callback_path = _loopback_target_v2(redirect_uri)

    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(
            self,
            _format,
            *args,
        ) -> None:
            return

        def _reply(
            self,
            status: int,
            text: str,
        ) -> None:
            payload = (
                "<html><body><h3>"
                + text
                + "</h3>"
                + "<p>You can close this tab.</p>"
                + "</body></html>"
            ).encode("utf-8")

            self.send_response(status)

            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8",
            )

            self.send_header(
                "Content-Length",
                str(len(payload)),
            )

            self.end_headers()

            self.wfile.write(payload)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)

            if parsed.path != callback_path:
                self._reply(
                    404,
                    "Unexpected callback path",
                )

                return

            query = parse_qs(parsed.query)

            returned_state = (query.get("state") or [""])[0]

            if returned_state != expected_state:
                result["error"] = "OAUTH_STATE_MISMATCH"

                self._reply(
                    400,
                    "FYERS OAuth state mismatch",
                )

                return

            code = (query.get("auth_code") or query.get("code") or [""])[0]

            if not code:
                result["error"] = "AUTH_CODE_MISSING"

                self._reply(
                    400,
                    "FYERS authorization code missing",
                )

                return

            result["code"] = str(code)

            self._reply(
                200,
                "FYERS authentication received successfully",
            )

    try:
        server = HTTPServer(
            (
                host,
                port,
            ),
            Handler,
        )

    except OSError as exc:
        raise FyersDailyAuthError(
            "cannot bind FYERS callback listener on "
            f"{host}:{port}: "
            f"{type(exc).__name__}"
        ) from exc

    server.timeout = 1.0

    try:
        browser_open(auth_url)

        deadline = time.monotonic() + max(
            1,
            int(timeout_seconds),
        )

        while (
            time.monotonic() < deadline
            and "code" not in result
            and "error" not in result
        ):
            server.handle_request()

    finally:
        server.server_close()

    if "error" in result:
        raise FyersDailyAuthError(result["error"])

    code = result.get("code")

    if not code:
        raise FyersDailyAuthError("FYERS login timed out before callback")

    return code


def _default_session_factory_v2(
    **kwargs,
):
    from fyers_apiv3 import fyersModel

    return fyersModel.SessionModel(**kwargs)


def _new_session_v2(
    inputs: FyersOAuthInputsV2,
    *,
    state: str,
    session_factory: Callable[..., object],
):
    return session_factory(
        client_id=inputs.app_id,
        redirect_uri=inputs.redirect_uri,
        response_type="code",
        state=state,
        secret_key=inputs.secret_id,
        grant_type="authorization_code",
    )


def _exchange_auth_code_v2(
    *,
    inputs: FyersOAuthInputsV2,
    auth_code: str,
    state: str,
    session_factory: Callable[..., object],
) -> str:
    session = _new_session_v2(
        inputs,
        state=state,
        session_factory=session_factory,
    )

    session.set_token(auth_code)

    response = session.generate_token()

    if not isinstance(
        response,
        dict,
    ):
        raise FyersDailyAuthError("FYERS token exchange returned non-mapping response")

    auth_error = classify_fyers_response_v2(response)

    if auth_error is not None:
        raise FyersDailyAuthError(
            "FYERS token exchange failed: "
            + str(
                getattr(
                    auth_error,
                    "reason_code",
                    "AUTH_ERROR",
                )
            )
        ) from auth_error

    token = str(response.get("access_token") or "").strip()

    if not token:
        raise FyersDailyAuthError("FYERS token exchange returned no access token")

    return token


def _requires_interactive_reauth_v2(
    exc: FyersAuthError,
) -> bool:
    """Only authentication failures may trigger interactive OAuth."""
    return getattr(
        exc,
        "reason_code",
        None,
    ) in {
        REASON_AUTH_INVALID,
        REASON_AUTH_EXPIRED,
    }


def ensure_fyers_daily_auth_v2(
    *,
    env_file: str | Path = ".env",
    skew_seconds: int = 600,
    force_reauth: bool = False,
    browser_open: Callable[[str], object] = webbrowser.open,
    timeout_seconds: int = 180,
    session_factory: Callable[..., object] = _default_session_factory_v2,
    capture_auth_code: Callable[..., str] = _capture_loopback_auth_code_v2,
    provider_verify: Callable[[FyersCredentialsV2], None] | None = None,
) -> FyersDailyAuthResultV2:
    """Ensure a usable FYERS access token for today's runtime."""

    env_path = Path(env_file).resolve()

    inputs = load_fyers_oauth_inputs_v2(env_file=str(env_path))

    if not force_reauth and inputs.access_token:
        try:
            expiry = assert_fyers_token_current_v2(
                inputs.access_token,
                skew_seconds=skew_seconds,
            )

        except FyersAuthError as exc:
            if not _requires_interactive_reauth_v2(exc):
                raise

        else:
            credentials = load_fyers_credentials_v2(env_file=str(env_path))

            if provider_verify is None:
                return FyersDailyAuthResultV2(
                    status="CURRENT",
                    seconds_remaining=expiry.seconds_remaining,
                    token_replaced=False,
                    provider_verified=False,
                )

            try:
                provider_verify(credentials)

            except FyersAuthError as exc:
                # A provider response proving the token itself is invalid may
                # enter OAuth. Network/rate-limit/provider failures must not.
                if not _requires_interactive_reauth_v2(exc):
                    raise

            else:
                return FyersDailyAuthResultV2(
                    status="CURRENT",
                    seconds_remaining=expiry.seconds_remaining,
                    token_replaced=False,
                    provider_verified=True,
                )

    _loopback_target_v2(inputs.redirect_uri)

    state = secrets.token_urlsafe(24)

    session = _new_session_v2(
        inputs,
        state=state,
        session_factory=session_factory,
    )

    auth_url = session.generate_authcode()

    if not isinstance(
        auth_url,
        str,
    ) or not auth_url.startswith("https://"):
        raise FyersDailyAuthError("FYERS SDK did not return a valid HTTPS auth URL")

    auth_code = capture_auth_code(
        auth_url=auth_url,
        redirect_uri=inputs.redirect_uri,
        expected_state=state,
        browser_open=browser_open,
        timeout_seconds=timeout_seconds,
    )

    new_token = _exchange_auth_code_v2(
        inputs=inputs,
        auth_code=auth_code,
        state=state,
        session_factory=session_factory,
    )

    expiry = assert_fyers_token_current_v2(
        new_token,
        skew_seconds=skew_seconds,
    )

    _atomic_replace_env_value_v2(
        env_path,
        "FYERS_ACCESS_TOKEN",
        new_token,
    )

    os.environ["FYERS_ACCESS_TOKEN"] = new_token

    refreshed = load_fyers_credentials_v2(env_file=str(env_path))

    if refreshed.access_token != new_token:
        raise FyersDailyAuthError(
            "fresh token persistence did not become runtime authority"
        )

    if provider_verify is not None:
        provider_verify(refreshed)

    return FyersDailyAuthResultV2(
        status="REAUTHENTICATED",
        seconds_remaining=expiry.seconds_remaining,
        token_replaced=True,
        provider_verified=(provider_verify is not None),
    )
