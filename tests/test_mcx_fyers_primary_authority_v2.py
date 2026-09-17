"""Hard guard: canonical MCX sources cannot regain Angel primary authority."""

from pathlib import Path

from mcx.mcx_fyers_runtime_v2 import (
    MCXFyersRuntimeV2,
)


ACTIVE_PROVIDER_FILES = (
    "src/mcx/mcx_paper_bot.py",
    "src/mcx/mcx_chain.py",
    "src/mcx/mcx_probe.py",
    "src/mcx/mcx_snapshot.py",
    "src/mcx/mcx_replay.py",
    "src/mcx/mcx_exec_quote.py",
    "src/mcx/mcx_health.py",
)


def test_active_mcx_sources_have_no_angel_login_authority():
    forbidden = (
        "SmartConnect",
        "from SmartApi",
        "import SmartApi",
        "import pyotp",
        "ANGEL_API_KEY",
        "ANGEL_USER_ID",
        "ANGEL_CLIENT_ID",
        "ANGEL_PASSWORD",
        "ANGEL_PIN",
        "ANGEL_TOTP_SECRET",
        'provider="AngelOne"',
    )

    bad = []

    for file_name in ACTIVE_PROVIDER_FILES:
        text = Path(
            file_name
        ).read_text(
            encoding="utf-8"
        )

        for marker in forbidden:
            if marker in text:
                bad.append(
                    (file_name, marker)
                )

    assert not bad, bad


def test_runtime_primary_is_fyers_and_no_fallback():
    assert MCXFyersRuntimeV2.provider == "FYERS"
    assert MCXFyersRuntimeV2.data_only is True

    assert (
        MCXFyersRuntimeV2
        .automatic_fallback_allowed
        is False
    )

    assert (
        MCXFyersRuntimeV2
        .order_capability_allowed
        is False
    )

    assert (
        MCXFyersRuntimeV2
        .live_execution_eligible
        is False
    )


def test_legacy_chain_has_no_standalone_provider_login():
    text = Path(
        "src/mcx/mcx_chain.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "def login(" not in text
    assert "generateSession" not in text

    assert (
        "LEGACY_CHAIN_RETIRED = True"
        in text
    )


def test_probe_snapshot_and_replay_use_fyers_runtime():
    for file_name in (
        "src/mcx/mcx_probe.py",
        "src/mcx/mcx_snapshot.py",
        "src/mcx/mcx_replay.py",
    ):
        text = Path(
            file_name
        ).read_text(
            encoding="utf-8"
        )

        assert (
            "build_mcx_fyers_runtime_from_env_v2"
            in text
        )


def test_exec_quote_default_is_provider_neutral():
    text = Path(
        "src/mcx/mcx_exec_quote.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        'provider="UNSPECIFIED"'
        in text
    )

    assert "AngelOne" not in text
