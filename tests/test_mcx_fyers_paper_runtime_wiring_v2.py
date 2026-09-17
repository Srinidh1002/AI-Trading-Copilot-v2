"""Offline verification of MCX PAPER bot FYERS cutover.

No credentials.
No network.
No PAPER state write.
No certification mutation.
"""

from pathlib import Path

import pytest

from mcx import mcx_paper_bot as bot


class FakeRuntime:
    provider = "FYERS"
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    live_execution_eligible = False

    def __init__(self):
        self.data = object()
        self.identity = object()
        self.native_chain = object()


class TimestampedFYERSData:
    def getMarketData(
        self,
        mode,
        exchange_tokens,
    ):
        token = str(
            exchange_tokens["MCX"][0]
        )

        return {
            "status": True,
            "data": {
                "fetched": [{
                    "symbolToken": token,
                    "ltp": 100.0,
                    "tradeVolume": 5000,
                    "opnInterest": 25000,
                    "depth": {
                        "buy": [{
                            "price": 99.95,
                            "quantity": 100,
                            "orders": 5,
                        }],
                        "sell": [{
                            "price": 100.05,
                            "quantity": 100,
                            "orders": 5,
                        }],
                    },
                    "provider": "FYERS",
                }]
            },
        }

    def ltpData(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        return {
            "status": True,
            "provider": "FYERS",
            "data": {
                "exchange_timestamp":
                    1789725600,
                "timestamp":
                    1789725600,
                "ltp": 100.0,
            },
        }


class NoTimestampFYERSData(
    TimestampedFYERSData
):
    def ltpData(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        return {
            "status": True,
            "provider": "FYERS",
            "data": {
                "ltp": 100.0,
            },
        }


def test_login_composes_only_fyers_runtime(
    monkeypatch,
    tmp_path,
):
    expected = FakeRuntime()
    calls = []

    def fake_builder(
        *,
        log_path,
    ):
        calls.append(log_path)
        return expected

    monkeypatch.setattr(
        bot,
        "build_mcx_fyers_runtime_from_env_v2",
        fake_builder,
    )

    monkeypatch.chdir(
        tmp_path
    )

    result = bot.login()

    assert result is expected
    assert len(calls) == 1

    assert (
        Path(calls[0]).as_posix()
        == "logs/mcx_fyers_client"
    )


def test_execution_quote_is_fyers_provider_and_uses_provider_timestamp():
    token = "MCX:SILVERM_OPT"

    q = bot.fetch_execution_quote_or_none(
        TimestampedFYERSData(),
        "SILVERM",
        token,
        option_meta={
            "symbol": token,
            "type": "CE",
            "strike": 180000.0,
            "expiry": "2026-09-25",
        },
        tick=0.05,
    )

    assert q is not None

    assert q["provider"] == "FYERS"
    assert q["source_mode"] == "REST_FULL"

    assert (
        q["exchange_feed_time"]
        == 1789725600
    )

    assert (
        q["exchange_trade_time"]
        == 1789725600
    )

    assert (
        q["validation_status"]
        == "VALID"
    )

    assert (
        "MISSING_FEED_TIME"
        not in q["rejection_reasons"]
    )

    assert (
        q["raw_payload_hash"]
        is not None
    )


def test_missing_fyers_timestamp_fails_closed_not_local_now():
    token = "MCX:GOLDM_OPT"

    q = bot.fetch_execution_quote_or_none(
        NoTimestampFYERSData(),
        "GOLDM",
        token,
        option_meta={
            "symbol": token,
            "type": "PE",
            "strike": 125000.0,
            "expiry": "2026-09-25",
        },
        tick=0.05,
    )

    assert q is not None

    assert q["provider"] == "FYERS"

    assert (
        q["exchange_feed_time"]
        is None
    )

    assert (
        q["exchange_trade_time"]
        is None
    )

    assert (
        q["validation_status"]
        == "INVALID"
    )

    assert (
        "MISSING_FEED_TIME"
        in q["rejection_reasons"]
    )


def test_active_source_has_no_angel_acquisition_authority():
    text = Path(
        "src/mcx/mcx_paper_bot.py"
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "SmartConnect",
        "from SmartApi",
        "import pyotp",
        "ANGEL_API_KEY",
        "ANGEL_USER_ID",
        "ANGEL_PASSWORD",
        "ANGEL_TOTP_SECRET",
        "MCXIdentityResolver",
        "from mcx.mcx_chain import build_chain",
        'provider="AngelOne"',
    )

    assert not [
        marker
        for marker in forbidden
        if marker in text
    ]


def test_active_source_uses_fyers_runtime_identity_and_native_chain():
    text = Path(
        "src/mcx/mcx_paper_bot.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "build_mcx_fyers_runtime_from_env_v2"
        in text
    )

    assert (
        "runtime.identity.resolve_active"
        in text
    )

    assert (
        "runtime.native_chain.build"
        in text
    )

    assert 'provider="FYERS"' in text


def test_paper_safety_flags_remain_frozen():
    assert bot.EXECUTION_MODE == "PAPER"
    assert bot.BROKER_SUBMISSION is False
    assert bot.LIVE_EXECUTION is False

    assert bot.STOP_LOSS_PCT == -8.0
    assert bot.T1_PCT == 15.0
    assert bot.T2_PCT == 30.0
    assert bot.T3_PCT == 50.0

    assert bot.ENTRY_THRESHOLD == 70
    assert bot.DEPLOYABLE_CAPITAL == 100_000
