from datetime import datetime, timezone

from services.contracts.live_option_capture_result_v1 import LiveOptionCaptureResultV1
from services.live_option_decision_pipeline import LiveOptionDecisionPipeline
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.paper_orchestration.certified_live_provider_readers import CertifiedLiveProviderReaders
from tests.test_task8_parent_typed_candidate_certification import captured, cycle


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


class ChainBuilder:
    def __init__(self):
        self.calls = 0

    def build_chain(self, **kwargs):
        self.calls += 1
        return {"underlying": kwargs["underlying"], "contracts": [{"token": "1"}]}


def test_capture_method_exists_without_changing_fetch_all_contract():
    assert callable(getattr(LiveMultiTimeframeData, "fetch_all_with_capture"))


def test_option_capture_is_single_read_and_contains_no_decision_fields():
    builder = ChainBuilder()
    pipeline = LiveOptionDecisionPipeline(option_chain_builder=builder, market_client=object())
    captured = pipeline.capture_option_inputs(
        underlying="NIFTY", spot_price=25000.0, option_exchange="NFO",
        provider_timestamp=NOW, evaluated_at=NOW,
    )
    assert builder.calls == 1
    assert captured.contracts == ({"token": "1"},)
    assert "confidence" not in captured.option_chain
    assert "ranking" not in captured.option_chain
    assert captured.to_dict()["contract_count"] == 1


def test_option_capture_preserves_provider_failure_without_random_values():
    class BrokenBuilder:
        def build_chain(self, **kwargs):
            raise RuntimeError("provider unavailable")

    captured = LiveOptionDecisionPipeline(option_chain_builder=BrokenBuilder(), market_client=object()).capture_option_inputs(
        underlying="SENSEX", spot_price=80000.0, option_exchange="BFO",
        provider_timestamp=NOW, evaluated_at=NOW,
    )
    assert captured.contracts == ()
    assert captured.blockers == ("OPTION_CAPTURE_RUNTIMEERROR",)


def test_live_option_capture_contract_has_safe_immutable_summary():
    captured = LiveOptionCaptureResultV1(
        underlying_symbol="NIFTY", option_exchange="NFO",
        option_chain={"contracts": []}, provider_timestamp=NOW, evaluated_at=NOW,
    )
    assert captured.to_dict()["contract_count"] == 0


def test_shared_parent_uses_one_completed_candle_cutoff_for_both_market_captures():
    nifty, sensex = captured("NIFTY", "NSE", 25000.0), captured("SENSEX", "BSE", 80000.0)
    calls = []
    class Analysis:
        def analyse(self, **kwargs): return {}
    class Options:
        def analyse(self, **kwargs): return {}
    def capture_reader(item, *, candle_cutoff=None):
        calls.append(candle_cutoff)
        return nifty if item.underlying_symbol == "NIFTY" else sensex
    readers = CertifiedLiveProviderReaders(quote_reader=lambda *_: {}, analysis_pipeline=Analysis(), option_decision_pipeline=Options(), available_capital=10000.0, capture_reader=capture_reader)
    readers.prepare_shared_broader_context(cycle("NIFTY", "NSE", nifty), cycle("SENSEX", "BSE", sensex))
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert calls[0].minute % 5 == calls[0].second == calls[0].microsecond == 0
