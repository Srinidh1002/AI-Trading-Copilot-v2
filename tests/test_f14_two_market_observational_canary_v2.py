from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from services.observation.two_market_canary_v2 import (  # noqa: E402
    CanaryMarketResultV2,
    CanaryObservationError,
    observe_market_v2,
    select_market_v2,
)


class FakeWs:
    def __init__(self, status="HEALTHY"):
        self.status = status

    def health_str(self):
        return self.status


class FakeMarketIntel:
    def __init__(self, consensus="BULLISH"):
        self.consensus = consensus

    def get_multi_timeframe_technicals(self):
        return {
            "consensus": self.consensus,
            "1h": {"trend": "UP"},
            "15m": {"trend": "UP"},
            "5m": {"trend": "FLAT"},
        }


class FakeRanker:
    def rank(self, chain, direction, atm):
        score = 91.0 if direction == "BULLISH" else 83.0
        opt_type = "CE" if direction == "BULLISH" else "PE"
        return {
            "status": "OK",
            "top_pick": {
                "strike": atm,
                "type": opt_type,
                "ltp": 100.0,
                "symbol": f"TEST{opt_type}",
                "token": f"TOKEN-{opt_type}",
                "bid": 99.0,
                "ask": 101.0,
                "oi": 1000,
                "volume": 5000,
                "spread_pct": 2.0,
                "passes_liquidity": True,
                "score": score,
            },
        }


class FakeCapital:
    capital = 100000

    def compute_paper_fill(self, bid, ask, ltp, direction="BUY"):
        assert direction == "BUY"
        return 101.1, "OK"

    def compute_lot_size(self, fill, lot_size):
        return 2


class FakeBot:
    provider_mode = "FYERS_V2_INJECTED"
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False
    EXECUTION_MODE = "PAPER"
    BROKER_SUBMISSION = False
    LIVE_EXECUTION = False
    STOP_LOSS_PERCENT = 5
    T1_PERCENT = 15
    T2_PERCENT = 30
    T3_PERCENT = 50

    def __init__(self, market="NIFTY", *, chain_status="OK", quote_complete=True):
        self.market = market
        self.current_session = 0
        self.total_trades = 0
        self.certification_counter = 0
        self.active_trades = {}
        self.completed_trades = []
        self.contract_index = {"anything": "present"}
        self.market_intel = FakeMarketIntel()
        self.strike_ranker = FakeRanker()
        self.capital_engine = FakeCapital()
        self.ws_feed = FakeWs()
        self.ws_healthy = True
        self._last_premarket_state = None
        self._last_regime_ctx = {"regime": "UNKNOWN"}
        self._chain_status = chain_status
        self._quote_complete = quote_complete
        self.original_persist_called = False

    def _persist_prediction(self, **kwargs):
        self.original_persist_called = True
        raise AssertionError("disk persistence must be replaced by canary")

    def connect_with_retry(self, max_retries=1, retry_delay=0):
        return True

    def load_instruments(self):
        return True

    def get_spot(self):
        return 23270.6 if self.market == "NIFTY" else 74314.59

    def get_expiry(self):
        return "22SEP2026" if self.market == "NIFTY" else "24SEP2026"

    def get_options(self, spot, expiry):
        atm = 23250.0 if self.market == "NIFTY" else 74300.0
        if self._chain_status == "OK":
            self._last_chain = {
                "status": "OK",
                "provider": "FYERS",
                "request_count": 1,
                "per_contract_depth_requests": 0,
                "pcr_oi": 1.25,
                "ce_data": {},
                "pe_data": {},
            }
            return [{"type": "CE", "strike": atm, "ltp": 100.0}], atm
        self._last_chain = {
            "status": "EVIDENCE_UNAVAILABLE",
            "reason": "NATIVE_EXPIRY_IDENTITY_MISMATCH",
            "request_count": 1,
            "per_contract_depth_requests": 0,
        }
        return [], atm

    def get_enhanced_sentiment(self, spot, options):
        self._last_premarket_state = object()
        self._last_regime_ctx = {"regime": "TRENDING_UP", "confidence": 0.8}
        self._persist_prediction(
            bias="BULLISH",
            bias_confidence="MODERATE",
            readiness="READY",
            action="BUY_CALL",
            blockers=[],
            bull_score=2.5,
            bear_score=0.5,
            bull_pillars=3,
            bear_pillars=0,
            coverage_pct=85.0,
            spot=spot,
            spot_freshness="FRESH",
            regime="TRENDING_UP",
            selected_trade=None,
            config_version="test",
        )
        return "BULLISH"

    def _fetch_option_quote_full(self, symbol, token):
        if self._quote_complete:
            return {"ltp": 100.0, "bid": 99.0, "ask": 101.0}
        return {"ltp": 100.0, "bid": None, "ask": None}


def test_observation_uses_memory_sink_and_preserves_counters(monkeypatch):
    import contract_metadata

    monkeypatch.setattr(contract_metadata, "resolve_lot_size", lambda *a, **k: (75, "TEST"))
    bot = FakeBot()
    result = observe_market_v2(bot)

    assert result.connected is True
    assert result.counters_unchanged is True
    assert bot.original_persist_called is False
    assert result.prediction["persisted_to_disk"] is False
    assert result.chain_status == "OK"
    assert result.chain_request_count == 1
    assert result.chain_depth_fanout == 0
    assert result.pcr_oi == 1.25
    assert result.mtf_consensus == "BULLISH"
    assert result.regime == "TRENDING_UP"
    assert result.websocket_healthy is True
    assert result.premarket_available is True


def test_execution_probe_uses_full_quote_fill_lot_and_existing_targets(monkeypatch):
    import contract_metadata

    monkeypatch.setattr(contract_metadata, "resolve_lot_size", lambda *a, **k: (75, "TEST"))
    result = observe_market_v2(FakeBot())

    assert result.diagnostic_candidate["type"] == "CE"
    assert result.diagnostic_candidate["score"] == 91.0
    assert result.executable_quote == {"ltp": 100.0, "bid": 99.0, "ask": 101.0}
    assert result.paper_fill == 101.1
    assert result.lot_size == 75
    assert result.lots_affordable == 2
    assert result.targets == {
        "sl": 96.045,
        "t1": 116.265,
        "t2": 131.43,
        "t3": 151.65,
    }


def test_incomplete_executable_quote_never_fabricates_fill_or_targets(monkeypatch):
    import contract_metadata

    monkeypatch.setattr(contract_metadata, "resolve_lot_size", lambda *a, **k: (75, "TEST"))
    result = observe_market_v2(FakeBot(quote_complete=False))
    assert result.executable_quote == {"ltp": 100.0, "bid": None, "ask": None}
    assert result.paper_fill is None
    assert result.lot_size is None
    assert result.lots_affordable is None
    assert result.targets is None


def test_chain_rollover_mismatch_is_observed_without_candidate(monkeypatch):
    import contract_metadata

    monkeypatch.setattr(contract_metadata, "resolve_lot_size", lambda *a, **k: (75, "TEST"))
    result = observe_market_v2(FakeBot("SENSEX", chain_status="EVIDENCE_UNAVAILABLE"))
    assert result.chain_status == "EVIDENCE_UNAVAILABLE"
    assert result.chain_reason == "NATIVE_EXPIRY_IDENTITY_MISMATCH"
    assert result.diagnostic_candidate is None
    assert result.paper_fill is None
    assert result.targets is None
    assert result.counters_unchanged is True


def test_neutral_prediction_can_rank_both_sides_for_diagnostics(monkeypatch):
    import contract_metadata

    monkeypatch.setattr(contract_metadata, "resolve_lot_size", lambda *a, **k: (75, "TEST"))
    bot = FakeBot()

    def neutral(spot, options):
        bot._last_premarket_state = object()
        bot._last_regime_ctx = {"regime": "RANGE_BOUND"}
        bot._persist_prediction(
            bias="NEUTRAL",
            bias_confidence="WEAK",
            readiness="WAIT",
            action="WAIT",
            blockers=[],
            coverage_pct=70.0,
            regime="RANGE_BOUND",
        )
        return "NEUTRAL"

    bot.get_enhanced_sentiment = neutral
    result = observe_market_v2(bot)
    assert result.diagnostic_candidate["diagnostic_direction"] == "BULLISH"
    assert result.diagnostic_candidate["score"] == 91.0
    assert result.prediction["action"] == "WAIT"


def test_counter_mutation_is_detected(monkeypatch):
    import contract_metadata

    monkeypatch.setattr(contract_metadata, "resolve_lot_size", lambda *a, **k: (75, "TEST"))
    bot = FakeBot()

    def mutating(spot, options):
        bot.total_trades += 1
        bot._persist_prediction(
            bias="NEUTRAL",
            bias_confidence="WEAK",
            readiness="WAIT",
            action="WAIT",
            blockers=[],
            coverage_pct=50.0,
            regime="UNKNOWN",
        )
        return "NEUTRAL"

    bot.get_enhanced_sentiment = mutating
    result = observe_market_v2(bot)
    assert result.counters_unchanged is False


def test_requires_provider_injected_data_only_bot():
    bot = FakeBot()
    bot.provider_mode = "ANGEL"
    with pytest.raises(CanaryObservationError, match="FYERS_INJECTED_BOT_REQUIRED"):
        observe_market_v2(bot)


def _result(market, *, readiness, score, confidence="MODERATE"):
    return CanaryMarketResultV2(
        market=market,
        connected=True,
        spot=1.0,
        expiry="X",
        atm=1.0,
        option_count=1,
        chain_status="OK",
        chain_reason=None,
        chain_request_count=1,
        chain_depth_fanout=0,
        pcr_oi=1.0,
        mtf_consensus="BULLISH",
        regime="TRENDING_UP",
        prediction={
            "coverage_pct": 90.0,
            "bias_confidence": confidence,
            "readiness": readiness,
        },
        diagnostic_candidate={"score": score},
        executable_quote=None,
        paper_fill=None,
        lot_size=None,
        lots_affordable=None,
        targets=None,
        websocket_status="HEALTHY",
        websocket_healthy=True,
        counters_unchanged=True,
        premarket_available=True,
        provider_mode="FYERS_V2_INJECTED",
    )


def test_market_selector_uses_existing_selector_without_new_thresholds():
    nifty = _result("NIFTY", readiness="READY", score=95.0, confidence="STRONG")
    sensex = _result("SENSEX", readiness="BLOCKED", score=90.0)
    selected = select_market_v2(nifty, sensex)
    assert selected["selection"] == "SELECT_NIFTY"
    assert selected["reason"] == "Only NIFTY eligible"
