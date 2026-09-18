from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import time

from datetime import datetime
from pathlib import Path


# Windows redirected stdout/stderr may otherwise inherit cp1252.
# Configure UTF-8 before importing modules that initialize Colorama.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        _reconfigure(
            encoding="utf-8",
            errors="replace",
        )


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from dotenv import load_dotenv

from provider_injected_target_bot_v2 import (
    ProviderInjectedUnifiedTradingBotV2,
)

from services.broker.fyers_data_compatibility_v2 import (
    FyersDataOnlyCompatibilityV2,
)

from services.broker.fyers_legacy_identity_resolver_v2 import (
    FyersLegacyIdentityResolverV2,
)

from services.broker.fyers_provider_runtime_v2 import (
    build_fyers_provider_runtime_v2,
)

from services.broker.fyers_sdk_data_client_v2 import (
    build_fyers_data_client_v2,
)

from services.broker.fyers_streaming_v2 import (
    FyersStreamingDataProviderV2,
)

from services.core.provider_routing_policy_v2 import (
    automatic_fallback_provider,
)

from services.options.fyers_native_option_chain_engine_v2 import (
    FyersNativeOptionChainEngineV2,
)

from services.options.fyers_option_chain_provider_v2 import (
    FyersOptionChainProviderV2,
)


MARKET = "NIFTY"

TRUTHY = {
    "1",
    "true",
    "yes",
    "on",
    "enabled",
}


def _is_true(name: str) -> bool:
    return str(
        os.getenv(name, "")
    ).strip().lower() in TRUTHY


def _apply_safety_boundary() -> None:

    unsafe = [
        name
        for name in (
            "BROKER_SUBMISSION",
            "BROKER_SUBMISSION_ENABLED",
            "LIVE_EXECUTION",
            "LIVE_EXECUTION_ENABLED",
            "LIVE_EXECUTION_ELIGIBLE",
        )
        if _is_true(name)
    ]

    if unsafe:
        raise RuntimeError(
            "Unsafe execution flags enabled: "
            + ",".join(unsafe)
        )

    os.environ["EXECUTION_MODE"] = "PAPER"
    os.environ["BROKER_SUBMISSION"] = "false"
    os.environ["BROKER_SUBMISSION_ENABLED"] = "false"
    os.environ["LIVE_EXECUTION"] = "false"
    os.environ["LIVE_EXECUTION_ENABLED"] = "false"
    os.environ["LIVE_EXECUTION_ELIGIBLE"] = "false"
    os.environ["AUTOMATIC_LAUNCH"] = "false"


def _install_ipv4_fyers_filter():

    original = socket.getaddrinfo

    def filtered(
        host,
        port,
        family=0,
        type=0,
        proto=0,
        flags=0,
    ):

        if (
            isinstance(host, str)
            and host.endswith("fyers.in")
        ):
            family = socket.AF_INET

        return original(
            host,
            port,
            family,
            type,
            proto,
            flags,
        )

    socket.getaddrinfo = filtered
    return original


def _build_fyers_bot():

    load_dotenv(
        ROOT / ".env",
        override=True,
    )

    _apply_safety_boundary()

    if not _is_true("FYERS_DATA_ONLY"):
        raise RuntimeError(
            "FYERS_DATA_ONLY must be true"
        )

    app_id = str(
        os.getenv(
            "FYERS_APP_ID",
            "",
        )
    ).strip()

    access_token = str(
        os.getenv(
            "FYERS_ACCESS_TOKEN",
            "",
        )
    ).strip()

    if not app_id:
        raise RuntimeError(
            "FYERS_APP_ID missing"
        )

    if not access_token:
        raise RuntimeError(
            "FYERS_ACCESS_TOKEN missing"
        )

    rows = json.loads(
        (
            ROOT
            / "data"
            / "instruments.json"
        ).read_text(
            encoding="utf-8-sig"
        )
    )

    if not isinstance(rows, list):
        raise RuntimeError(
            "Instrument master is not a list"
        )

    rest_log = tempfile.mkdtemp(
        prefix=(
            "fyers_"
            + MARKET.lower()
            + "_paper_rest_"
        )
    )

    stream_log = tempfile.mkdtemp(
        prefix=(
            "fyers_"
            + MARKET.lower()
            + "_paper_stream_"
        )
    )

    client = build_fyers_data_client_v2(
        client_id=app_id,
        access_token=access_token,
        log_path=rest_log,
    )

    if getattr(
        client,
        "data_only",
        None,
    ) is not True:
        raise RuntimeError(
            "FYERS client is not data-only"
        )

    if getattr(
        client,
        "order_capability_allowed",
        None,
    ) is not False:
        raise RuntimeError(
            "FYERS order capability is enabled"
        )

    if getattr(
        client,
        "automatic_fallback_allowed",
        None,
    ) is not False:
        raise RuntimeError(
            "FYERS automatic fallback is enabled"
        )

    fallback = automatic_fallback_provider(
        MARKET,
        "QUOTE",
    )

    if fallback is not None:
        raise RuntimeError(
            "Automatic fallback exists: "
            + str(fallback)
        )

    streaming = FyersStreamingDataProviderV2(
        client_id=app_id,
        access_token=access_token,
        log_path=stream_log,
        reconnect=True,
        ipv4_only=True,
    )

    runtime = build_fyers_provider_runtime_v2(
        data_client=client,
        streaming=streaming,
    )

    legacy_identity = (
        FyersLegacyIdentityResolverV2(
            instrument_rows=rows,
            resolver=runtime.resolver,
        )
    )

    compatibility = (
        FyersDataOnlyCompatibilityV2(
            client=client,
            symbol_resolver=legacy_identity,
        )
    )

    native_provider = (
        FyersOptionChainProviderV2(
            client
        )
    )

    native_engine = (
        FyersNativeOptionChainEngineV2(
            market=MARKET,
            provider=native_provider,
            resolver=runtime.resolver,
            legacy_identity_resolver=legacy_identity,
            cache_ttl=60,
            native_strike_count=10,
        )
    )

    bot = ProviderInjectedUnifiedTradingBotV2(
        MARKET,
        provider_runtime=runtime,
        legacy_data_api=compatibility,
        native_option_chain_engine=native_engine,
    )

    if getattr(
        bot,
        "provider_mode",
        None,
    ) != "FYERS_V2_INJECTED":
        raise RuntimeError(
            "Unexpected provider mode"
        )

    if getattr(
        bot,
        "data_only",
        None,
    ) is not True:
        raise RuntimeError(
            "Bot is not data-only"
        )

    if getattr(
        bot,
        "order_capability_allowed",
        None,
    ) is not False:
        raise RuntimeError(
            "Bot order capability enabled"
        )

    if getattr(
        bot,
        "automatic_fallback_allowed",
        None,
    ) is not False:
        raise RuntimeError(
            "Bot automatic fallback enabled"
        )

    if getattr(
        bot,
        "EXECUTION_MODE",
        None,
    ) != "PAPER":
        raise RuntimeError(
            "Bot is not PAPER"
        )

    if getattr(
        bot,
        "BROKER_SUBMISSION",
        None,
    ) is not False:
        raise RuntimeError(
            "Broker submission is not false"
        )

    if getattr(
        bot,
        "LIVE_EXECUTION",
        None,
    ) is not False:
        raise RuntimeError(
            "Live execution is not false"
        )

    return (
        bot,
        streaming,
        rest_log,
        stream_log,
    )


def main() -> int:

    original_getaddrinfo = (
        _install_ipv4_fyers_filter()
    )

    bot = None
    streaming = None
    rest_log = None
    stream_log = None

    try:

        (
            bot,
            streaming,
            rest_log,
            stream_log,
        ) = _build_fyers_bot()

        print(
            "PRIMARY_DATA_PROVIDER=FYERS"
        )

        print(
            "PROVIDER_MODE="
            + str(bot.provider_mode)
        )

        print(
            "EXECUTION_MODE=PAPER"
        )

        print(
            "BROKER_SUBMISSION=False"
        )

        print(
            "LIVE_EXECUTION=False"
        )

        print(
            "ORDER_CAPABILITY_ALLOWED=False"
        )

        print(
            "AUTOMATIC_FALLBACK_ALLOWED=False"
        )

        bot.load_state()

        bot.connect_with_retry()

        bot.load_instruments()

        bot.MARKET_OPEN = (
            datetime.now().replace(
                hour=9,
                minute=15,
                second=0,
                microsecond=0,
            )
        )

        bot.FINAL_EXIT = (
            datetime.now().replace(
                hour=15,
                minute=28,
                second=0,
                microsecond=0,
            )
        )

        print(
            "Market open:",
            bot.is_market_open(),
        )

        print(
            f"{MARKET} entered="
            f"{bot.current_session} "
            f"cert="
            f"{bot.certification_counter}/100"
        )

        attempts = 0
        max_attempts = 1000

        while (
            bot.is_market_open()
            and bot.certification_counter < 100
            and attempts < max_attempts
        ):

            attempts += 1

            print()
            print("=" * 40)

            print(
                "Attempt",
                attempts,
                "| Cert:",
                bot.certification_counter,
                "/100 | Entered:",
                bot.current_session,
            )

            print("=" * 40)

            result = bot.run_single_session()

            if result:

                bot.current_session += 1
                bot.session_history.append(result)
                bot.sessions_completed_today += 1

                print(
                    ">>> TRADE TAKEN - "
                    f"Entered={bot.current_session} "
                    f"Cert="
                    f"{bot.certification_counter}/100"
                )

            else:

                print(
                    ">>> SKIPPED - "
                    "not counted toward 100"
                )

            bot.save_state()

            if (
                bot.is_market_open()
                and bot.certification_counter < 100
                and attempts < max_attempts
            ):
                time.sleep(30)
            else:
                break

        print()
        print("Daily Summary:")

        print(
            "  Entered:",
            bot.current_session,
            "| Cert:",
            bot.certification_counter,
            "/100",
        )

        print(
            "  Attempts:",
            attempts,
        )

        bot.show_daily_summary()

        return 0

    finally:

        if bot is not None:
            try:
                bot.close_provider_subscription()
            except Exception:
                pass

        if streaming is not None:
            try:
                streaming.close()
            except Exception:
                pass

        socket.getaddrinfo = original_getaddrinfo

        if rest_log:
            shutil.rmtree(
                rest_log,
                ignore_errors=True,
            )

        if stream_log:
            shutil.rmtree(
                stream_log,
                ignore_errors=True,
            )


if __name__ == "__main__":
    raise SystemExit(main())
