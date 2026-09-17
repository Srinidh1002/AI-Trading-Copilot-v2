from pathlib import Path

from src.liquidity_gate import LiquidityGate
from src.option_chain_engine import OptionChainEngine
from src.strike_ranker import StrikeRanker


EXPIRY = "17SEP2026"
ATM = 23500


def _instrument():
    return {
        "symbol": "NIFTY17SEP2623500CE",
        "token": "101",
        "strike": float(ATM),
        "expiry": EXPIRY,
        "type": "CE",
        "market": "NIFTY",
        "exchange": "NFO",
    }


class FakeMarketData:
    def __init__(self, row):
        self.row = dict(row)

    def getMarketData(self, mode, payload):
        assert mode == "FULL"

        return {
            "data": {
                "fetched": [
                    dict(self.row)
                ]
            }
        }


def _engine(row):
    return OptionChainEngine(
        FakeMarketData(row),
        market="NIFTY",
        option_exchange="NFO",
        strike_divisor=100,
        cache_ttl=0,
    )


def _rank(chain):
    gate = LiquidityGate(
        max_spread_pct=2.0,
        min_volume=100,
        min_oi=500,
    )

    return StrikeRanker(
        gate
    ).rank(
        chain,
        "BULLISH",
        ATM,
    )


def test_ltp_without_provider_bid_ask_fails_liquidity_closed():
    engine = _engine(
        {
            "symbolToken": "101",
            "ltp": 100.0,
            "oi": 5000,
            "volume": 5000,
        }
    )

    chain = engine.fetch(
        EXPIRY,
        ATM,
        [_instrument()],
        strike_range=0,
        force=True,
    )

    assert chain["status"] == "OK"

    option = chain[
        "ce_data"
    ][ATM]

    assert option["ltp"] == 100.0
    assert option["bid"] == 0.0
    assert option["ask"] == 0.0

    assert (
        option["bid_ask_source"]
        == "UNAVAILABLE"
    )

    assert option["spread"] is None
    assert option["spread_pct"] is None

    ranking = _rank(
        chain
    )

    assert ranking["top_pick"] is None
    assert len(ranking["candidates"]) == 1

    candidate = ranking[
        "candidates"
    ][0]

    assert (
        candidate["passes_liquidity"]
        is False
    )

    assert (
        "NO_BID_ASK"
        in candidate["reject_reasons"]
    )


def test_real_provider_depth_can_pass_liquidity():
    engine = _engine(
        {
            "symbolToken": "101",
            "ltp": 100.0,
            "oi": 5000,
            "volume": 5000,
            "bestFiveBuyData": [
                {
                    "price": 99.5,
                }
            ],
            "bestFiveSellData": [
                {
                    "price": 100.5,
                }
            ],
        }
    )

    chain = engine.fetch(
        EXPIRY,
        ATM,
        [_instrument()],
        strike_range=0,
        force=True,
    )

    assert chain["status"] == "OK"

    option = chain[
        "ce_data"
    ][ATM]

    assert option["bid"] == 99.5
    assert option["ask"] == 100.5

    assert (
        option["bid_ask_source"]
        == "PROVIDER_MARKET_DATA"
    )

    assert option["spread"] == 1.0
    assert option["spread_pct"] == 1.0

    ranking = _rank(
        chain
    )

    assert ranking["top_pick"] is not None

    assert (
        ranking["top_pick"]
        ["passes_liquidity"]
        is True
    )


def test_source_contains_no_ltp_derived_bid_ask():
    text = Path(
        "src/option_chain_engine.py"
    ).read_text(
        encoding="utf-8",
    )

    assert "ltp_v * 0.999" not in text
    assert "ltp_v * 1.001" not in text
