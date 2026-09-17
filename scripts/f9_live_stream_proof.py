"""F9 bounded FYERS DataSocket proof through the production V2 adapter.

DATA ONLY. No order API. No order socket. No PAPER certification.
Uses the F8 resolver to derive the five active streaming identities and
subscribes through FyersStreamingDataProviderV2.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
)
from services.broker.fyers_sdk_data_client_v2 import (
    build_fyers_data_client_v2,
)
from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)


def _resolve_five_markets(resolver, as_of):
    requests = (
        ("NIFTY", "UNDERLYING"),
        ("SENSEX", "UNDERLYING"),
        ("CRUDEOILM", "FUTURE"),
        ("GOLDM", "FUTURE"),
        ("NATGASMINI", "FUTURE"),
    )
    return tuple(
        resolver.resolve(
            market_symbol=market,
            instrument_type=kind,
            as_of=as_of,
        )
        for market, kind in requests
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--ipv4-only", action="store_true")
    parser.add_argument("--min-ticks", type=int, default=1)
    args = parser.parse_args()

    load_dotenv()
    app_id = os.getenv("FYERS_APP_ID")
    token = os.getenv("FYERS_ACCESS_TOKEN")
    if not app_id or not token:
        print("MISSING CREDENTIALS: FYERS_APP_ID / FYERS_ACCESS_TOKEN")
        return 2

    rest_log_dir = "logs/f9_fyers_rest"
    stream_log_dir = "logs/f9_fyers_stream"
    os.makedirs(rest_log_dir, exist_ok=True)
    os.makedirs(stream_log_dir, exist_ok=True)

    rest_client = build_fyers_data_client_v2(
        client_id=app_id,
        access_token=token,
        log_path=rest_log_dir,
    )
    resolver = FyersFiveMarketInstrumentResolverV2(data_client=rest_client)
    as_of = datetime.now(timezone.utc)
    instruments = _resolve_five_markets(resolver, as_of)

    print("F9 FYERS STREAMING READ-ONLY PROOF")
    print("as_of =", as_of.isoformat())
    print("resolved_symbols =", len(instruments))
    for item in instruments:
        print(
            " ",
            item["market_symbol"],
            item["instrument_type"],
            "->",
            item["provider_symbol"],
        )

    received = []
    seen = set()
    event = threading.Event()

    def on_tick(tick):
        received.append(tick)
        symbol = tick["provider_symbol"]
        if symbol not in seen:
            seen.add(symbol)
            print(
                " first_tick",
                tick.get("market_symbol"),
                symbol,
                "ltp=",
                tick["ltp"],
                "timestamp_source=",
                tick["timestamp_source"],
            )
        if len(received) >= max(args.min_ticks, 1):
            event.set()

    provider = FyersStreamingDataProviderV2(
        client_id=app_id,
        access_token=token,
        log_path=stream_log_dir,
        reconnect=True,
        ipv4_only=args.ipv4_only,
    )

    subscription_id = None
    success = False
    try:
        subscription_id = provider.subscribe(instruments, on_tick)
        connected = provider.wait_until_connected(min(args.timeout, 8.0))
        print("connected =", connected)

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline and len(received) < args.min_ticks:
            event.wait(timeout=0.25)

        snap = provider.snapshot()
        print("messages_received =", len(received))
        print("unique_symbols_seen =", len(seen))
        print("connection_generation =", snap["connection_generation"])
        print("stream_error_count =", snap["error_count"])
        print("last_error =", snap["last_error"])
        success = connected and len(received) >= args.min_ticks
    finally:
        if subscription_id is not None:
            try:
                provider.unsubscribe(subscription_id)
            except Exception:
                pass
        provider.close()

    print("FYERS_DATA_ONLY=True")
    print("ORDER_CAPABILITY_ALLOWED=False")
    print("AUTOMATIC_FALLBACK_ALLOWED=False")
    print("LIVE_EXECUTION_ELIGIBLE=False")
    print("ORDER_API_EXECUTED=False")
    print("ORDER_SOCKET_CREATED=False")
    print("PAPER_CERTIFICATION_STARTED=False")
    print("P8D0_F9_LIVE_STREAM_PROOF=", "PASS" if success else "HOLD")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
