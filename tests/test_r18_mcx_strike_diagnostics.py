from __future__ import annotations

from mcx.mcx_strike import (
    MIN_OPTION_OI,
    MIN_OPTION_VOLUME,
    format_strike_diagnostics,
    select_strike,
    select_strike_with_diagnostics,
)


def _entry(*, ltp, oi, vol, token, symbol):
    return {
        "ltp": ltp,
        "oi": oi,
        "vol": vol,
        "token": token,
        "symbol": symbol,
    }


def test_selector_skips_higher_scored_ineligible_candidate():
    chain = {
        "status": "OK",
        "atm": 1000,
        "ce_data": {},
        "pe_data": {
            # ATM gets the larger distance bonus but fails both liquidity floors.
            1000: _entry(
                ltp=50,
                oi=MIN_OPTION_OI - 1,
                vol=MIN_OPTION_VOLUME - 1,
                token="BAD",
                symbol="MCX:BADPE",
            ),
            # Slightly farther strike passes the unchanged hard floors.
            1100: _entry(
                ltp=42,
                oi=MIN_OPTION_OI,
                vol=MIN_OPTION_VOLUME,
                token="GOOD",
                symbol="MCX:GOODPE",
            ),
        },
    }

    selected, diag = select_strike_with_diagnostics(chain, "BEARISH")

    assert selected is not None
    assert selected["strike"] == 1100
    assert selected["token"] == "GOOD"
    assert diag["status"] == "SELECTED"
    assert diag["candidate_count"] == 2
    assert diag["eligible_count"] == 1
    assert diag["top_candidates"][0]["strike"] == 1000
    assert diag["top_candidates"][0]["eligible"] is False


def test_no_eligible_liquidity_is_explained_without_lowering_floors():
    chain = {
        "status": "OK",
        "atm": 1000,
        "ce_data": {},
        "pe_data": {
            1000: _entry(
                ltp=50,
                oi=100,
                vol=50,
                token="PE1",
                symbol="MCX:PE1",
            ),
            1100: _entry(
                ltp=40,
                oi=MIN_OPTION_OI,
                vol=MIN_OPTION_VOLUME - 1,
                token="PE2",
                symbol="MCX:PE2",
            ),
        },
    }

    selected, diag = select_strike_with_diagnostics(chain, "BEARISH")

    assert selected is None
    assert select_strike(chain, "BEARISH") is None
    assert diag["status"] == "NO_ELIGIBLE_LIQUIDITY"
    assert diag["eligible_count"] == 0
    assert diag["min_oi"] == MIN_OPTION_OI
    assert diag["min_volume"] == MIN_OPTION_VOLUME

    lines = format_strike_diagnostics(diag)
    assert lines[0].startswith("STRIKE_DIAG status=NO_ELIGIBLE_LIQUIDITY")
    assert any("passes_oi=False" in line for line in lines[1:])
    assert any("passes_vol=False" in line for line in lines[1:])


def test_invalid_bias_fails_closed():
    selected, diag = select_strike_with_diagnostics(
        {"status": "OK", "atm": 1000, "ce_data": {}, "pe_data": {}},
        "SIDEWAYS",
    )

    assert selected is None
    assert diag["status"] == "INVALID_BIAS"
