from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.paper_orchestration.certified_live_provider_readers import (
    NIFTY_MARKET_SPEC,
    SENSEX_MARKET_SPEC,
    CertifiedLiveProviderReaders,
    market_spec_for,
)


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 1, 8, 10, 0, tzinfo=IST)


class AnalysisPipeline:
    def __init__(self):
        self.calls = []

    def analyse(self, **kwargs):
        self.calls.append(kwargs)
        return {"spot_price": 25000.0, "decision": "BULLISH"}


class OptionPipeline:
    def __init__(self, decision="NO_TRADE"):
        self.calls = []
        self.decision = decision

    def analyse(self, **kwargs):
        self.calls.append(kwargs)
        return {"decision": self.decision}


def readers(option_decision="NO_TRADE"):
    return CertifiedLiveProviderReaders(
        quote_reader=lambda exchange, token, underlying: {
            "ltp": 25000.0,
            "market_timestamp": NOW,
            "received_at": NOW,
        },
        analysis_pipeline=AnalysisPipeline(),
        option_decision_pipeline=OptionPipeline(option_decision),
        available_capital=10000.0,
    )


def test_certified_market_specs_are_locked():
    assert NIFTY_MARKET_SPEC.symboltoken == "99926000"
    assert NIFTY_MARKET_SPEC.option_exchange == "NFO"
    assert SENSEX_MARKET_SPEC.symboltoken == "99919000"
    assert SENSEX_MARKET_SPEC.option_exchange == "BFO"


def test_market_spec_rejects_unsupported_identity():
    with pytest.raises(ValueError):
        market_spec_for("BANKNIFTY", "NSE")


def test_provider_requires_read_only_pipeline_interfaces():
    with pytest.raises(TypeError, match="analyse"):
        CertifiedLiveProviderReaders(
            quote_reader=lambda *args: {},
            analysis_pipeline=object(),
            option_decision_pipeline=OptionPipeline(),
            available_capital=10000,
        )


def test_constructor_rejects_zero_capital():
    with pytest.raises(ValueError, match="available_capital"):
        CertifiedLiveProviderReaders(
            quote_reader=lambda *args: {},
            analysis_pipeline=AnalysisPipeline(),
            option_decision_pipeline=OptionPipeline(),
            available_capital=0,
        )


def test_reader_module_exposes_no_live_execution_switch():
    value = readers()
    assert not hasattr(value, "live_execution_enabled")
    assert not hasattr(value, "place_order")
    assert not hasattr(value, "submit_order")
