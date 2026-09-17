"""F10 bounded operational FYERS runtime proof.

Builds the production V2 FYERS runtime, installs it in the shared orchestrator,
resolves one NIFTY underlying, reads one quote and receives one DataSocket tick.
DATA ONLY. No orders. No automatic fallback. No PAPER certification.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from services.broker.fyers_provider_runtime_v2 import (
    build_fyers_provider_runtime_v2,
)
from services.broker.fyers_sdk_data_client_v2 import (
    build_fyers_data_client_v2,
)
from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)
from services.broker.shared_market_data_hub_v2 import (
    SharedMarketDataHubV2,
)
from services.broker.shared_provider_orchestrator_v2 import (
    SharedProviderOrchestratorV2,
)
from services.core.provider_routing_policy_v2 import (
    automatic_fallback_provider,
    resolve_operational_primary,
)


MARKETS = (
    "NIFTY",
    "SENSEX",
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)
DATA_KINDS = (
    "INSTRUMENT",
    "QUOTE",
    "DEPTH",
    "HISTORICAL",
    "STREAMING",
)


def _load_environment(path: str) -> bool:
    env_path = Path(path).expanduser().resolve()
    if not env_path.is_file():
        print("ENV FILE NOT FOUND")
        return False
    load_dotenv(dotenv_path=env_path, override=False)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--ipv4-only", action="store_true")
    args = parser.parse_args()

    if not _load_environment(args.env_file):
        return 2

    app_id = os.getenv("FYERS_APP_ID")
    token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not token:
        print("MISSING CREDENTIALS: FYERS_APP_ID / FYERS_ACCESS_TOKEN")
        return 2

    os.makedirs("logs/f10_fyers_rest", exist_ok=True)
    os.makedirs("logs/f10_fyers_stream", exist_ok=True)

    data_client = build_fyers_data_client_v2(
        client_id=app_id,
        access_token=token,
        log_path="logs/f10_fyers_rest",
    )
    streaming = FyersStreamingDataProviderV2(
        client_id=app_id,
        access_token=token,
        log_path="logs/f10_fyers_stream",
        reconnect=True,
        ipv4_only=args.ipv4_only,
    )
    runtime = build_fyers_provider_runtime_v2(
        data_client=data_client,
        streaming=streaming,
    )

    hub = SharedMarketDataHubV2()
    orchestrator = SharedProviderOrchestratorV2(
        market_data_hub=hub,
    )
    orchestrator.install_runtime(runtime)

    print("F10 FYERS OPERATIONAL RUNTIME PROOF")
    print("as_of =", datetime.now(timezone.utc).isoformat())

    route_count = 0
    for market in MARKETS:
        for kind in DATA_KINDS:
            provider = resolve_operational_primary(market, kind)
            if provider != "FYERS":
                print("ROUTING FAILURE", market, kind, provider)
                return 1
            if automatic_fallback_provider(market, kind) is not None:
                print("FALLBACK FAILURE", market, kind)
                return 1
            route_count += 1
    print("operational_primary_routes =", route_count)

    consumer = "F10_LIVE_PROOF"
    acquired = orchestrator.get_operational_primary_runtime(
        market_symbol="NIFTY",
        data_kind="QUOTE",
        consumer_id=consumer,
    )
    if acquired is not runtime:
        print("RUNTIME ACQUIRE FAILURE")
        return 1

    instrument = runtime.resolver.resolve(
        market_symbol="NIFTY",
        instrument_type="UNDERLYING",
        as_of=datetime.now(timezone.utc),
    )
    print("resolved =", instrument["provider_symbol"])

    quote = runtime.quote_depth.get_quote(instrument)
    print("quote_last_price =", quote["last_price"])
    print("quote_data_only =", quote["data_only"])

    ticks = []
    event = threading.Event()

    def on_tick(tick):
        ticks.append(tick)
        event.set()

    subscription_id = None
    success = False
    try:
        subscription_id = orchestrator.subscribe(
            provider="FYERS",
            consumer_id=consumer,
            instruments=(instrument,),
            callback=on_tick,
        )
        connected = streaming.wait_until_connected(
            min(args.timeout, 8.0)
        )
        event.wait(timeout=args.timeout)

        print("stream_connected =", connected)
        print("stream_ticks =", len(ticks))
        print("stream_healthy =", streaming.is_healthy(30))
        print("stream_errors =", streaming.snapshot()["error_count"])

        success = (
            connected
            and len(ticks) >= 1
            and streaming.is_healthy(30)
            and streaming.snapshot()["error_count"] == 0
        )
    finally:
        if subscription_id is not None:
            try:
                orchestrator.unsubscribe(
                    provider="FYERS",
                    consumer_id=consumer,
                )
            except Exception:
                pass
        try:
            orchestrator.release_runtime(
                provider="FYERS",
                consumer_id=consumer,
            )
        except Exception:
            pass
        try:
            orchestrator.close_provider("FYERS")
        except Exception:
            streaming.close()

    print("runtime_closed =", not orchestrator.is_runtime_installed("FYERS"))
    print("FYERS_DATA_ONLY=True")
    print("ORDER_CAPABILITY_ALLOWED=False")
    print("AUTOMATIC_FALLBACK_ALLOWED=False")
    print("LIVE_EXECUTION_ELIGIBLE=False")
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    print("P8D0_F10_LIVE_RUNTIME_PROOF=", "PASS" if success else "HOLD")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
