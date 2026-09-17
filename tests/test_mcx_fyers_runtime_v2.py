"""Offline tests for FYERS-only MCX runtime composition."""

from pathlib import Path

import pytest

from mcx.mcx_fyers_runtime_v2 import (
    MCXFyersRuntimeError,
    build_mcx_fyers_runtime_from_env_v2,
    build_mcx_fyers_runtime_v2,
)


class FakeClient:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def quotes(self, data=None):
        return {"s": "ok", "d": []}

    def depth(self, data=None):
        return {"s": "ok", "d": {}}

    def history(self, data=None):
        return {"s": "ok", "candles": []}

    def optionchain(self, data=None):
        return {
            "s": "ok",
            "data": {
                "optionsChain": []
            },
        }

    def futures_chain(self, data=None):
        return {
            "s": "ok",
            "data": {},
        }


class FakeStore:
    def get_index(self, segment):
        raise RuntimeError(
            "offline fake store"
        )


class Builder:
    def __init__(self):
        self.calls = []

    def __call__(
        self,
        *,
        client_id,
        access_token,
        log_path,
    ):
        self.calls.append({
            "client_id": client_id,
            "access_token": access_token,
            "log_path": log_path,
        })

        return FakeClient()


def test_explicit_runtime_is_fyers_data_only():
    builder = Builder()

    runtime = build_mcx_fyers_runtime_v2(
        client_id="APP-100",
        access_token="TOKEN-200",
        log_path="dummy-log",
        master_store=FakeStore(),
        client_builder=builder,
    )

    assert runtime.provider == "FYERS"
    assert runtime.data_only is True

    assert (
        runtime.order_capability_allowed
        is False
    )

    assert (
        runtime.automatic_fallback_allowed
        is False
    )

    assert (
        runtime.live_execution_eligible
        is False
    )

    assert runtime.data is runtime.bridge.data
    assert (
        runtime.identity
        is runtime.bridge.identity
    )

    assert runtime.chain is runtime.native_chain

    assert builder.calls == [{
        "client_id": "APP-100",
        "access_token": "TOKEN-200",
        "log_path": "dummy-log",
    }]


def test_environment_composition_reads_only_fyers_provider_inputs():
    builder = Builder()

    env = {
        "FYERS_APP_ID": "FYERS-APP",
        "FYERS_ACCESS_TOKEN": "FYERS-TOKEN",
        "FYERS_MASTER_CACHE_DIR": "fake-cache",

        # These deliberately exist.
        # Runtime composition must not consume them.
        "ANGEL_API_KEY": "SHOULD-NOT-BE-USED",
        "ANGEL_USER_ID": "SHOULD-NOT-BE-USED",
        "ANGEL_PASSWORD": "SHOULD-NOT-BE-USED",
        "ANGEL_TOTP_SECRET": "SHOULD-NOT-BE-USED",
    }

    runtime = (
        build_mcx_fyers_runtime_from_env_v2(
            log_path="dummy-log",
            env=env,
            master_store=FakeStore(),
            client_builder=builder,
        )
    )

    assert runtime.provider == "FYERS"

    assert builder.calls == [{
        "client_id": "FYERS-APP",
        "access_token": "FYERS-TOKEN",
        "log_path": "dummy-log",
    }]


@pytest.mark.parametrize(
    "env",
    (
        {
            "FYERS_ACCESS_TOKEN": "TOKEN",
        },
        {
            "FYERS_APP_ID": "APP",
        },
        {},
    ),
)
def test_missing_fyers_credentials_fail_closed(env):
    with pytest.raises(
        MCXFyersRuntimeError
    ):
        build_mcx_fyers_runtime_from_env_v2(
            log_path="dummy-log",
            env=env,
            master_store=FakeStore(),
            client_builder=Builder(),
        )


def test_source_exposes_no_angel_or_order_capability():
    text = Path(
        "src/mcx/mcx_fyers_runtime_v2.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "SmartConnect",
        "pyotp",
        "SmartApi",
        "placeOrder",
        "place_order",
        "modifyOrder",
        "cancelOrder",
        "FyersOrderSocket",
        "generateSession",
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]


def test_runtime_safety_flags_are_fixed_false():
    runtime = build_mcx_fyers_runtime_v2(
        client_id="APP",
        access_token="TOKEN",
        log_path="logs",
        master_store=FakeStore(),
        client_builder=Builder(),
    )

    assert runtime.data.data_only is True

    assert (
        runtime.data.order_capability_allowed
        is False
    )

    assert (
        runtime.data.automatic_fallback_allowed
        is False
    )
