from __future__ import annotations

import base64
import json
import os
import time

import pytest

import services.broker.fyers_daily_auth_v2 as daily
from services.broker.fyers_auth_v2 import (
    FyersCredentialsV2,
    FyersOAuthInputsV2,
)


def _jwt(
    exp: int,
) -> str:
    def encode(
        payload: dict,
    ) -> str:
        raw = json.dumps(
            payload,
            separators=(
                ",",
                ":",
            ),
        ).encode("utf-8")

        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return (
        encode(
            {
                "alg": "none",
                "typ": "JWT",
            }
        )
        + "."
        + encode(
            {
                "iat": int(time.time()),
                "exp": exp,
            }
        )
        + ".signature"
    )


def _inputs(
    token: str | None,
) -> FyersOAuthInputsV2:
    return FyersOAuthInputsV2(
        app_id="TESTAPP-100",
        secret_id="SECRET",
        redirect_uri=("http://127.0.0.1:8765/callback"),
        access_token=token,
        source="test",
    )


def _credentials(
    token: str,
) -> FyersCredentialsV2:
    return FyersCredentialsV2(
        app_id="TESTAPP-100",
        secret_id="SECRET",
        access_token=token,
        refresh_token=None,
        redirect_uri=("http://127.0.0.1:8765/callback"),
        pin=None,
        source="test",
    )


def test_loopback_rejects_non_loopback_redirect():
    with pytest.raises(daily.FyersDailyAuthError):
        daily._loopback_target_v2("https://example.com/callback")


def test_atomic_env_replacement_collapses_duplicate_token_definitions(
    tmp_path,
):
    env_path = tmp_path / ".env"

    env_path.write_text(
        "FYERS_APP_ID=TESTAPP-100\n"
        "FYERS_ACCESS_TOKEN=OLD1\n"
        "OTHER_KEY=value\n"
        "FYERS_ACCESS_TOKEN=OLD2\n",
        encoding="utf-8",
    )

    daily._atomic_replace_env_value_v2(
        env_path,
        "FYERS_ACCESS_TOKEN",
        "NEW",
    )

    text = env_path.read_text(encoding="utf-8")

    assert text.count("FYERS_ACCESS_TOKEN=") == 1

    assert "FYERS_ACCESS_TOKEN=NEW" in text

    assert "OTHER_KEY=value" in text


def test_current_token_does_not_start_oauth(
    monkeypatch,
    tmp_path,
):
    token = _jwt(int(time.time()) + 7200)

    monkeypatch.setattr(
        daily,
        "load_fyers_oauth_inputs_v2",
        lambda **kwargs: _inputs(token),
    )

    monkeypatch.setattr(
        daily,
        "load_fyers_credentials_v2",
        lambda **kwargs: _credentials(token),
    )

    verified = []

    result = daily.ensure_fyers_daily_auth_v2(
        env_file=(tmp_path / ".env"),
        provider_verify=(lambda value: verified.append(value.access_token)),
        capture_auth_code=(lambda **kwargs: pytest.fail("OAuth must not run")),
    )

    assert result.status == "CURRENT"
    assert result.token_replaced is False
    assert result.provider_verified is True
    assert verified == [token]


@pytest.mark.parametrize(
    "old_token",
    [
        None,
        "EXPIRED_PLACEHOLDER",
    ],
)
def test_missing_or_invalid_token_runs_oauth(
    monkeypatch,
    tmp_path,
    old_token,
):
    new_token = _jwt(int(time.time()) + 7200)

    env_path = tmp_path / ".env"

    env_path.write_text(
        "FYERS_APP_ID=TESTAPP-100\n"
        + (("FYERS_ACCESS_TOKEN=" + old_token + "\n") if old_token else "")
        + "FYERS_SECRET_ID=SECRET\n"
        + ("FYERS_REDIRECT_URI=http://127.0.0.1:8765/callback\n"),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        daily,
        "load_fyers_oauth_inputs_v2",
        lambda **kwargs: _inputs(old_token),
    )

    class FakeSession:
        def __init__(
            self,
            **kwargs,
        ):
            self.token = None

        def generate_authcode(
            self,
        ):
            return "https://api-t1.fyers.in/api/v3/generate-authcode?test=1"

        def set_token(
            self,
            token,
        ):
            self.token = token

        def generate_token(
            self,
        ):
            assert self.token == "AUTH-CODE"

            return {
                "s": "ok",
                "access_token": new_token,
            }

    monkeypatch.setenv(
        "FYERS_ACCESS_TOKEN",
        (old_token or ""),
    )

    monkeypatch.setattr(
        daily,
        "load_fyers_credentials_v2",
        lambda **kwargs: _credentials(os.environ["FYERS_ACCESS_TOKEN"]),
    )

    result = daily.ensure_fyers_daily_auth_v2(
        env_file=env_path,
        session_factory=FakeSession,
        capture_auth_code=(lambda **kwargs: "AUTH-CODE"),
    )

    assert result.status == "REAUTHENTICATED"

    assert result.token_replaced is True

    persisted = env_path.read_text(encoding="utf-8")

    assert f"FYERS_ACCESS_TOKEN={new_token}" in persisted


def test_structural_provider_failure_does_not_get_hidden(
    monkeypatch,
    tmp_path,
):
    token = _jwt(int(time.time()) + 7200)

    monkeypatch.setattr(
        daily,
        "load_fyers_oauth_inputs_v2",
        lambda **kwargs: _inputs(token),
    )

    monkeypatch.setattr(
        daily,
        "load_fyers_credentials_v2",
        lambda **kwargs: _credentials(token),
    )

    def verify(
        _credentials_value,
    ):
        raise RuntimeError("provider verification failure")

    with pytest.raises(
        RuntimeError,
        match="provider verification failure",
    ):
        daily.ensure_fyers_daily_auth_v2(
            env_file=(tmp_path / ".env"),
            provider_verify=verify,
        )


def test_network_auth_error_does_not_trigger_interactive_oauth(
    monkeypatch,
    tmp_path,
):
    from services.broker.fyers_auth_v2 import FyersAuthError

    token = _jwt(int(time.time()) + 7200)

    monkeypatch.setattr(
        daily,
        "load_fyers_oauth_inputs_v2",
        lambda **kwargs: _inputs(token),
    )

    monkeypatch.setattr(
        daily,
        "load_fyers_credentials_v2",
        lambda **kwargs: _credentials(token),
    )

    capture_called = []

    def capture_auth_code(
        **kwargs,
    ):
        capture_called.append(True)

        pytest.fail("network failure must not trigger OAuth")

    def verify(
        _credentials_value,
    ):
        raise FyersAuthError(
            "NETWORK_ERROR",
            "simulated network failure",
        )

    with pytest.raises(FyersAuthError) as exc_info:
        daily.ensure_fyers_daily_auth_v2(
            env_file=(tmp_path / ".env"),
            provider_verify=verify,
            capture_auth_code=capture_auth_code,
        )

    assert (
        getattr(
            exc_info.value,
            "reason_code",
            None,
        )
        == "NETWORK_ERROR"
    )

    assert capture_called == []
