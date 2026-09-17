from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.broker.fyers_sdk_data_client_v2 import (
    FyersDataOnlySdkFacadeV2,
    build_fyers_data_client_v2,
)


class FakeRawFyersModel:
    def __init__(self, **kwargs) -> None:
        self.constructor_kwargs = (
            kwargs
        )

        self.calls = []

    def _response(
        self,
        name,
        data,
    ):
        self.calls.append(
            (
                name,
                data,
            )
        )

        return {
            "s": "ok",
            "name": name,
            "data": data,
        }

    def quotes(self, data=None):
        return self._response(
            "quotes",
            data,
        )

    def depth(self, data=None):
        return self._response(
            "depth",
            data,
        )

    def history(self, data=None):
        return self._response(
            "history",
            data,
        )

    def optionchain(self, data=None):
        return self._response(
            "optionchain",
            data,
        )

    def futures_chain(self, data=None):
        return self._response(
            "futures_chain",
            data,
        )

    def expiry_dates(self, data):
        return self._response(
            "expiry_dates",
            data,
        )

    def fno_historical_data(self, data):
        return self._response(
            "fno_historical_data",
            data,
        )

    # Deliberate raw order surface.
    # The facade must not expose this.
    def place_order(self, data=None):
        raise AssertionError(
            "order method must never be reachable"
        )


class CapturingFactory:
    def __init__(self) -> None:
        self.kwargs = None
        self.instance = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs

        self.instance = (
            FakeRawFyersModel(
                **kwargs
            )
        )

        return self.instance


def build(
    token="RAW_TOKEN",
):
    factory = CapturingFactory()

    facade = build_fyers_data_client_v2(
        client_id="APP-100",
        access_token=token,
        log_path="TEMP_LOG_DIR",
        model_factory=factory,
    )

    return (
        factory,
        facade,
    )


def test_factory_builds_synchronous_sdk_client():
    factory, facade = build()

    assert isinstance(
        facade,
        FyersDataOnlySdkFacadeV2,
    )

    assert factory.kwargs == {
        "client_id":
            "APP-100",
        "token":
            "RAW_TOKEN",
        "is_async":
            False,
        "log_path":
            "TEMP_LOG_DIR",
    }


def test_factory_strips_client_id_prefix_from_token():
    factory, _ = build(
        "APP-100:RAW_TOKEN"
    )

    assert (
        factory.kwargs[
            "token"
        ]
        == "RAW_TOKEN"
    )


def test_facade_forwards_only_data_methods():
    factory, facade = build()

    methods = (
        "quotes",
        "depth",
        "history",
        "optionchain",
        "futures_chain",
        "expiry_dates",
        "fno_historical_data",
    )

    for method_name in methods:
        method = getattr(
            facade,
            method_name,
        )

        result = method(
            {
                "probe": method_name
            }
        )

        assert (
            result[
                "s"
            ]
            == "ok"
        )

    assert [
        item[0]
        for item in factory.instance.calls
    ] == list(
        methods
    )


def test_facade_does_not_expose_order_surface():
    _, facade = build()

    forbidden = (
        "place_order",
        "placeOrder",
        "modify_order",
        "modifyOrder",
        "cancel_order",
        "cancelOrder",
        "orderbook",
        "orderBook",
        "positions",
        "funds",
    )

    assert not any(
        hasattr(
            facade,
            name,
        )
        for name in forbidden
    )

    assert facade.data_only is True
    assert (
        facade.order_capability_allowed
        is False
    )
    assert (
        facade.automatic_fallback_allowed
        is False
    )


def test_factory_requires_explicit_credentials_and_log_path():
    factory = CapturingFactory()

    with pytest.raises(
        ValueError
    ):
        build_fyers_data_client_v2(
            client_id="",
            access_token="TOKEN",
            log_path="LOG",
            model_factory=factory,
        )

    with pytest.raises(
        ValueError
    ):
        build_fyers_data_client_v2(
            client_id="APP",
            access_token="",
            log_path="LOG",
            model_factory=factory,
        )

    with pytest.raises(
        ValueError
    ):
        build_fyers_data_client_v2(
            client_id="APP",
            access_token="TOKEN",
            log_path="",
            model_factory=factory,
        )


def test_module_does_not_read_environment_or_import_fyers_eagerly():
    path = Path(
        "services/broker/fyers_sdk_data_client_v2.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )

    top_level_imports = []

    for node in tree.body:
        if isinstance(
            node,
            ast.Import,
        ):
            top_level_imports.extend(
                alias.name
                for alias in node.names
            )

        elif isinstance(
            node,
            ast.ImportFrom,
        ) and node.module:
            top_level_imports.append(
                node.module
            )

    assert (
        "fyers_apiv3"
        not in top_level_imports
    )

    text = path.read_text(
        encoding="utf-8"
    )

    assert "load_dotenv" not in text
    assert "dotenv_values" not in text
    assert "os.environ" not in text
    assert "getenv(" not in text
