"""FYERS-only runtime composition for MCX PAPER analysis.

This module owns provider composition only.

It does not:
- submit broker orders;
- create an order socket;
- enable live execution;
- perform automatic Angel fallback;
- alter strategy thresholds;
- alter PAPER certification counters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from services.broker.fyers_sdk_data_client_v2 import (
    build_fyers_data_client_v2,
)
from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterStoreV2,
)

from mcx.mcx_fyers_bridge_v2 import (
    MCXFyersBridgeV2,
    build_mcx_fyers_bridge_v2,
)
from mcx.mcx_fyers_native_chain_v2 import (
    MCXFyersNativeChainV2,
)


DEFAULT_MASTER_CACHE_DIR = (
    "data/provider_cache/fyers_master"
)


class MCXFyersRuntimeError(RuntimeError):
    """FYERS MCX runtime composition failed closed."""


@dataclass(frozen=True)
class MCXFyersRuntimeV2:
    data_client: object
    bridge: MCXFyersBridgeV2
    native_chain: MCXFyersNativeChainV2

    provider: str = "FYERS"
    data_only: bool = True
    order_capability_allowed: bool = False
    automatic_fallback_allowed: bool = False
    live_execution_eligible: bool = False

    @property
    def identity(self):
        return self.bridge.identity

    @property
    def data(self):
        return self.bridge.data

    @property
    def chain(self):
        return self.native_chain


def _required_text(value, field):
    text = str(value or "").strip()

    if not text:
        raise MCXFyersRuntimeError(
            f"{field} is required"
        )

    return text


def build_mcx_fyers_runtime_v2(
    *,
    client_id,
    access_token,
    log_path,
    master_cache_dir=DEFAULT_MASTER_CACHE_DIR,
    master_store=None,
    clock=None,
    client_builder=build_fyers_data_client_v2,
):
    """Compose one FYERS data-only MCX runtime."""

    client_id = _required_text(
        client_id,
        "FYERS_APP_ID",
    )

    access_token = _required_text(
        access_token,
        "FYERS_ACCESS_TOKEN",
    )

    log_path = _required_text(
        log_path,
        "log_path",
    )

    if not callable(client_builder):
        raise MCXFyersRuntimeError(
            "client_builder must be callable"
        )

    if master_store is None:
        cache_dir = _required_text(
            master_cache_dir,
            "master_cache_dir",
        )

        master_store = (
            FyersSymbolMasterStoreV2(
                base_dir=cache_dir
            )
        )

    client = client_builder(
        client_id=client_id,
        access_token=access_token,
        log_path=log_path,
    )

    if client is None:
        raise MCXFyersRuntimeError(
            "FYERS data client construction failed"
        )

    bridge = build_mcx_fyers_bridge_v2(
        data_client=client,
        master_store=master_store,
        clock=clock,
    )

    native_chain = MCXFyersNativeChainV2(
        data_client=client,
        identity=bridge.identity,
        data_api=bridge.data,
        clock=clock,
    )

    return MCXFyersRuntimeV2(
        data_client=client,
        bridge=bridge,
        native_chain=native_chain,
    )


def build_mcx_fyers_runtime_from_env_v2(
    *,
    log_path,
    env=None,
    master_cache_dir=None,
    master_store=None,
    clock=None,
    client_builder=build_fyers_data_client_v2,
):
    """Compose from FYERS environment variables only."""

    source = (
        os.environ
        if env is None
        else env
    )

    if not isinstance(source, Mapping):
        raise MCXFyersRuntimeError(
            "env must be a mapping"
        )

    app_id = source.get(
        "FYERS_APP_ID"
    )

    access_token = source.get(
        "FYERS_ACCESS_TOKEN"
    )

    if master_cache_dir is None:
        master_cache_dir = (
            source.get(
                "FYERS_MASTER_CACHE_DIR"
            )
            or DEFAULT_MASTER_CACHE_DIR
        )

    return build_mcx_fyers_runtime_v2(
        client_id=app_id,
        access_token=access_token,
        log_path=log_path,
        master_cache_dir=master_cache_dir,
        master_store=master_store,
        clock=clock,
        client_builder=client_builder,
    )
