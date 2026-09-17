"""Offline SILVERM product-foundation tests.

No provider login.
No network.
No PAPER state mutation.
No certification counter mutation.
"""

from services.core.five_market_universe_v2 import (
    TARGET_FIVE_MARKET_SYMBOLS,
)
from mcx.mcx_contracts import PRODUCTS
from mcx.mcx_external_context import DRIVERS
from mcx.mcx_paper_bot import (
    BROKER_SUBMISSION,
    EXECUTION_MODE,
    LIVE_EXECUTION,
    _SUPPORTED_PRODUCTS,
    _default_state_for,
)
from mcx.mcx_version import (
    PRODUCT_EPOCHS,
    get_product_epochs,
    is_certification_eligible,
)


def test_active_mcx_products_are_exact_requested_three():
    assert tuple(PRODUCTS) == (
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )


def test_silverm_contract_authority():
    cfg = PRODUCTS["SILVERM"]

    assert cfg["product"] == "SILVERM"
    assert cfg["exchange"] == "MCX"
    assert cfg["future_instr_type"] == "FUTCOM"
    assert cfg["option_instr_type"] == "OPTFUT"

    assert cfg["trading_unit"] == 5
    assert cfg["cash_multiplier"] == 5

    assert cfg["quote_base"] == "INR_PER_KG"
    assert cfg["tick_size"] == 1.0
    assert cfg["option_tick_size"] == 0.50
    assert cfg["strike_interval"] == 1000

    assert cfg["option_type"] == "EUROPEAN"
    assert cfg["settlement"] == "OPTIONS_ON_FUTURES"

    assert cfg["session"]["start"] == "09:00"
    assert cfg["session"]["end_default"] == "23:30"
    assert cfg["session"]["end_dst_us_summer"] == "23:55"


def test_active_paper_bot_accepts_silverm_not_natgasmini():
    assert _SUPPORTED_PRODUCTS == (
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )

    assert "NATGASMINI" not in _SUPPORTED_PRODUCTS


def test_silverm_has_independent_precert_epoch():
    cfg = get_product_epochs("SILVERM")

    assert cfg is not None
    assert cfg["strategy_version"] == "MCX_SILVERM_PRECERT_V1"
    assert cfg["epoch"] == "SILVERM_PRECERT_V1"
    assert cfg["version_path"].endswith(
        "mcx_silverm_strategy_version.json"
    )

    # Critical safety condition:
    # do not allow /100 until FYERS PAPER lifecycle is separately proven.
    assert cfg["certification_eligible"] is False
    assert is_certification_eligible("SILVERM") is False


def test_natgasmini_is_not_active_mcx_certification_product():
    assert "NATGASMINI" not in PRODUCT_EPOCHS
    assert is_certification_eligible("NATGASMINI") is False


def test_silverm_default_state_is_independent_and_precert():
    state = _default_state_for("SILVERM")

    assert state["product"] == "SILVERM"
    assert state["epoch"] == "SILVERM_PRECERT_V1"
    assert state["strategy_version"] == "MCX_SILVERM_PRECERT_V1"
    assert state["certification_eligible"] is False
    assert state["total_trades"] == 0
    assert state["total_pnl"] == 0.0
    assert state["active_position"] is None
    assert state["completed_trades"] == []


def test_silverm_has_commodity_specific_external_context():
    cfg = DRIVERS["SILVERM"]

    primary = {
        item[0]: item[1]
        for item in cfg["primary"]
    }

    cross = {
        item[0]: item[1]
        for item in cfg["cross_asset"]
    }

    assert primary["Silver"] == "SI=F"
    assert cross["USDINR"] == "USDINR=X"
    assert cross["DXY"] == "DX-Y.NYB"
    assert cross["US10Y"] == "^TNX"
    assert cross["Copper"] == "HG=F"


def test_canonical_five_market_and_active_mcx_sets_agree():
    assert TARGET_FIVE_MARKET_SYMBOLS == (
        "NIFTY",
        "SENSEX",
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    )

    assert set(_SUPPORTED_PRODUCTS) == {
        "CRUDEOILM",
        "GOLDM",
        "SILVERM",
    }


def test_paper_safety_boundary_is_unchanged():
    assert EXECUTION_MODE == "PAPER"
    assert BROKER_SUBMISSION is False
    assert LIVE_EXECUTION is False
