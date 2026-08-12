from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore, Task9PredictionPaperTradeBindingV1
from services.contracts.task9_prediction_paper_market_identity_v1 import build_task9_prediction_paper_market_identity
from services.contracts.prediction_observation_v1 import PredictionObservationV1
from tests.test_task916_prediction_lifecycle_timing_policy import prediction


NOW = datetime(2026, 8, 10, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def binding(*, market="NIFTY", underlying_exchange=None, derivative_exchange=None):
    return Task9PredictionPaperTradeBindingV1(
        official_run_id="run", prediction_id=f"prediction:{market}:CALL", market=market,
        paper_trade_id=f"trade:{market}", paper_position_id=f"position:{market}",
        option_symbol=f"{market}26AUG25000CE", entered_at=NOW,
        underlying_exchange=underlying_exchange, derivative_exchange=derivative_exchange,
    )


@pytest.mark.parametrize(("market", "exchange", "venue"), (("NIFTY", "NSE", "NFO"), ("SENSEX", "BSE", "BFO")))
def test_registered_underlying_and_derivative_venues_form_explicit_bridge(market, exchange, venue):
    value = build_task9_prediction_paper_market_identity(
        prediction=prediction("CALL", NOW, market, exchange), binding=binding(market=market),
    )
    assert (value.underlying_symbol, value.underlying_exchange, value.derivative_exchange) == (market, exchange, venue)
    assert value.prediction_id == f"prediction:{market}:CALL"
    assert value.option_symbol == f"{market}26AUG25000CE"


@pytest.mark.parametrize(("market", "underlying", "derivative"), (("NIFTY", "NSE", "BFO"), ("SENSEX", "BSE", "NFO"), ("NIFTY", "BSE", "NFO"), ("NIFTY", "NSE", "UNKNOWN")))
def test_invalid_venue_relationships_fail_closed(market, underlying, derivative):
    with pytest.raises(ValueError):
        binding(market=market, underlying_exchange=underlying, derivative_exchange=derivative)


def test_restart_recovers_explicit_dual_identity_and_legacy_binding_is_compatible(tmp_path):
    path = tmp_path / "bindings.json"; store = Task9PredictionPaperTradeBindingStore(path)
    legacy = binding()
    assert store.save(legacy) == "SAVED"
    recovered = Task9PredictionPaperTradeBindingStore(path).by_trade("trade:NIFTY")
    bridge = build_task9_prediction_paper_market_identity(prediction=prediction("CALL", NOW), binding=recovered)
    assert (bridge.underlying_exchange, bridge.derivative_exchange, bridge.paper_trade_id) == ("NSE", "NFO", "trade:NIFTY")
    assert store.save(legacy) == "DUPLICATE_SAME_PAYLOAD"


def test_wait_and_no_trade_have_no_paper_identity_bridge():
    for action in ("WAIT", "NO_TRADE"):
        record = prediction(action, NOW)
        assert record.parent_selected is False
        with pytest.raises(ValueError, match="mismatch"):
            build_task9_prediction_paper_market_identity(prediction=record, binding=binding())


@pytest.mark.parametrize(("market", "exchange", "venue"), (("NIFTY", "NSE", "NFO"), ("SENSEX", "BSE", "BFO")))
def test_projection_target_identity_uses_prediction_venue_not_paper_option_venue(market, exchange, venue):
    record = prediction("CALL", NOW, market, exchange)
    bridge = build_task9_prediction_paper_market_identity(prediction=record, binding=binding(market=market))
    target = PredictionObservationV1(
        observation_id=f"target:{market}", prediction_id=record.prediction_id, parent_cycle_id=record.parent_cycle_id,
        underlying_symbol=bridge.underlying_symbol, exchange=bridge.underlying_exchange,
        sequence_number=1, observed_at=NOW, underlying_price=25000.0 if market == "NIFTY" else 80000.0,
        option_premium=100.0, source_observation_id="p7-observation",
    )
    assert (target.underlying_symbol, target.exchange, bridge.derivative_exchange) == (market, exchange, venue)
