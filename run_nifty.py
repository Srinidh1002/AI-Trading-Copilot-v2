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


from services.broker.fyers_auth_v2 import (
    FyersAuthError,
    assert_fyers_token_current_v2,
    load_fyers_credentials_v2,
)
from services.broker.fyers_provider_runtime_v2 import (
    check_fyers_provider_health_v2,
)


def _build_fyers_bot():

    load_dotenv(
        ROOT / ".env",
        override=False,
    )

    _apply_safety_boundary()

    if not _is_true("FYERS_DATA_ONLY"):
        raise RuntimeError(
            "FYERS_DATA_ONLY must be true"
        )

    _creds = load_fyers_credentials_v2(
        env_file=str(ROOT / ".env")
    )

    try:
        assert_fyers_token_current_v2(_creds.access_token)
    except FyersAuthError as _auth_exc:
        raise SystemExit(
            "STARTUP_BLOCKED: PROVIDER_AUTH: "
            + _auth_exc.reason_code
            + "|provider_code=" + str(_auth_exc.provider_code)
        )

    app_id = _creds.app_id
    access_token = _creds.access_token

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

    _health = check_fyers_provider_health_v2(client)
    if not _health.ok:
        raise SystemExit(
            "STARTUP_BLOCKED: PROVIDER_HEALTH: "
            + _health.reason_code
            + "|provider_code=" + str(_health.provider_code)
        )
    print(
        "PROVIDER_HEALTH=OK"
        + "|SYMBOL=" + _health.symbol
        + "|HAD_QUOTE=" + str(_health.had_quote)
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


def _f15r2_compute_exit_code(exc_info):
    """F15-R2 M9b: map in-flight exception to process exit code.

    Used inside main()'s finally so os._exit() can propagate the same
    exit status Python would have produced.
    """
    exc_type, exc_val, _ = exc_info
    if exc_type is None:
        return 0
    if exc_type is SystemExit and exc_val is not None:
        code = getattr(exc_val, "code", 0)
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    return 1


def main() -> int:

    import os as _os
    _os.environ.setdefault("PAPER_MARKET_NAME", MARKET)
    from services.paper_orchestration.cooperative_stop_v2 import (
        STATUS_FLAT_SAFE_TO_EXIT as _COOP_FLAT,
        STATUS_POSITION_MANAGEMENT_ACTIVE as _COOP_POS_MGMT,
        acknowledge as _coop_ack,
        stop_requested as _coop_stop_requested,
    )
    from services.paper_orchestration.worker_heartbeat_v2 import beat as _hb_beat
    from services.paper_orchestration.worker_lock_v2 import acquire_market_worker_lock
    acquire_market_worker_lock(MARKET)

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

        if not bot.load_state():
            raise SystemExit(
                'STARTUP_BLOCKED: STATE_AUTHORITY:'
                + str(getattr(bot, 'state_load_classification', 'UNKNOWN'))
            )

        _cert_start = bot.activate_current_certification_epoch_if_safe()
        print(
            "CERTIFICATION_START_STATUS="
            + str(_cert_start.get("status"))
            + "|STRATEGY_VERSION="
            + str(_cert_start.get("strategy_version"))
            + "|CERTIFICATION_EPOCH="
            + str(_cert_start.get("certification_epoch"))
        )
        if _cert_start.get("status") not in ("CURRENT", "ACTIVATED"):
            raise RuntimeError("CERTIFICATION_START_BLOCKED: " + repr(_cert_start))

        if not bot.connect_with_retry():
            raise SystemExit("STARTUP_BLOCKED: PRIMARY_PROVIDER_CONNECTION_FAILED")

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

        def _hb(stage):
            _hb_beat(
                MARKET, stage,
                cycle_number=attempts,
                has_active_position=bool(getattr(bot, "active_trades", None)),
            )

        while (
            bot.is_market_open()
            and bot.certification_counter < 100
            and attempts < max_attempts
        ):

            if _coop_stop_requested():
                if not bot.active_trades:
                    bot.save_state()
                    _coop_ack(reason="FLAT_ACK_EXIT",
                              status=_COOP_FLAT,
                              has_active_position=False)
                    print("COOPERATIVE_STOP_FLAT — saved and ACKed")
                    return 0
                print("COOPERATIVE_STOP_POSITION_OPEN — managing to terminal")
                _coop_ack(reason="POSITION_MANAGEMENT_ACTIVE",
                          status=_COOP_POS_MGMT,
                          has_active_position=True)
                _coop_stop_active = True
            else:
                _coop_stop_active = False

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

            _hb("SESSION")
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
                _hb("SLEEP")
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

        # F15-R2 M9b: force-exit inside finally. main() reached its
        # return/raise site, but the interpreter was blocking at
        # Py_Finalize on a non-daemon FYERS DataSocket reader thread
        # that streaming.close() does not join. os._exit() bypasses
        # Py_Finalize and terminates the process immediately. Exit
        # code is derived from any in-flight exception.
        import sys as _sys_fin
        import os as _os_fin
        _sys_fin.stdout.flush()
        _sys_fin.stderr.flush()
        _os_fin._exit(_f15r2_compute_exit_code(_sys_fin.exc_info()))


if __name__ == "__main__":
    # F15-R2 M9b: after main() returns, hard-exit to bypass any
    # non-daemon SDK threads (e.g. FYERS DataSocket reader) that
    # would otherwise keep the interpreter alive after cleanup.
    # Observed after FLAT_ACK_EXIT: worker ACKed flat but the parent
    # process lingered indefinitely because the streaming reader
    # thread never joined. Exit code from main() is preserved.
    import os as _os_exit
    import sys as _sys_exit
    try:
        _code = main()
    except SystemExit as _se:
        _code = _se.code if isinstance(_se.code, int) else 0
    _sys_exit.stdout.flush()
    _sys_exit.stderr.flush()
    _os_exit._exit(_code)
