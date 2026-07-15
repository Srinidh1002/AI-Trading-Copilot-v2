from pathlib import Path

import pytest

from services.underlying_registry import (
    UnderlyingRegistry,
)


LIVE_ENTRY_POINT = Path(
    "live_option_decision_nifty.py"
)


def read_live_source():
    return LIVE_ENTRY_POINT.read_text(
        encoding="utf-8"
    )


def test_live_entry_point_imports_underlying_registry():
    source = read_live_source()

    assert (
        "from services.underlying_registry import ("
        in source
    )

    assert (
        "UnderlyingRegistry,"
        in source
    )


def test_live_entry_point_resolves_canonical_underlying():
    source = read_live_source()

    assert (
        "UNDERLYING_CONFIGURATION = ("
        in source
    )

    assert (
        "UnderlyingRegistry.get("
        in source
    )

    assert (
        '"NIFTY"'
        in source
    )


def test_live_entry_point_derives_market_identity():
    source = read_live_source()

    required_patterns = [
        "UNDERLYING_CONFIGURATION.underlying",
        "UNDERLYING_CONFIGURATION.exchange",
        "UNDERLYING_CONFIGURATION.symboltoken",
        "UNDERLYING_CONFIGURATION.option_exchange",
    ]

    for pattern in required_patterns:
        assert pattern in source


def test_hardcoded_nifty_token_constant_is_removed():
    source = read_live_source()

    assert (
        'NIFTY_TOKEN = "99926000"'
        not in source
    )

    assert (
        "NIFTY_TOKEN"
        not in source
    )


def test_spot_fetch_uses_resolved_market_identity():
    source = read_live_source()

    assert (
        "exchange_tokens={\n"
        "                SPOT_EXCHANGE: [\n"
        "                    SPOT_SYMBOLTOKEN"
        in source
    )


def test_pipeline_uses_resolved_market_identity():
    source = read_live_source()

    assert (
        "exchange=SPOT_EXCHANGE"
        in source
    )

    assert (
        "symboltoken=(\n"
        "                SPOT_SYMBOLTOKEN"
        in source
    )

    assert (
        "underlying=UNDERLYING"
        in source
    )


def test_source_decision_identity_is_dynamic():
    source = read_live_source()

    assert (
        'f"{SPOT_EXCHANGE}:"'
        in source
    )

    assert (
        'f"{UNDERLYING}:"'
        in source
    )

    assert (
        'f"{SPOT_SYMBOLTOKEN}:"'
        in source
    )


def test_paper_trading_uses_resolved_market_identity():
    source = read_live_source()

    process_position = source.index(
        "paper_trading_orchestrator.process_decision("
    )

    process_source = source[
        process_position:
        process_position + 1500
    ]

    assert (
        "underlying=UNDERLYING"
        in process_source
    )

    assert (
        "exchange=SPOT_EXCHANGE"
        in process_source
    )

    assert (
        "SPOT_SYMBOLTOKEN"
        in process_source
    )


def test_journal_metadata_uses_resolved_market_identity():
    source = read_live_source()

    journal_position = source.index(
        "market_cycle_journal.record_cycle("
    )

    journal_source = source[
        journal_position:
        journal_position + 2500
    ]

    assert (
        '"underlying": (\n'
        "                    UNDERLYING"
        in journal_source
    )

    assert (
        '"exchange": (\n'
        "                    SPOT_EXCHANGE"
        in journal_source
    )

    assert (
        '"symboltoken": (\n'
        "                    SPOT_SYMBOLTOKEN"
        in journal_source
    )


def test_execution_identity_literals_are_removed():
    source = read_live_source()

    forbidden_patterns = [
        'exchange="NSE"',
        'underlying="NIFTY"',
        '"underlying": "NIFTY"',
        '"exchange": "NSE"',
        'f"NSE:"',
        'f"NIFTY:"',
    ]

    for pattern in forbidden_patterns:
        assert pattern not in source


def test_registry_configuration_matches_current_nifty_identity():
    configuration = (
        UnderlyingRegistry.get(
            "NIFTY"
        )
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )

    assert (
        configuration.exchange
        == "NSE"
    )

    assert (
        configuration.symboltoken
        == "99926000"
    )

    assert (
        configuration.option_exchange
        == "NFO"
    )


@pytest.mark.parametrize(
    "underlying",
    [
        "SENSEX",
        "BANKNIFTY",
        "FINNIFTY",
    ],
)
def test_unregistered_live_markets_fail_closed(
    underlying,
):
    with pytest.raises(
        ValueError,
        match="Unsupported underlying",
    ):
        UnderlyingRegistry.get(
            underlying
        )
