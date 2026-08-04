from datetime import datetime, timedelta, timezone
import pytest
from services.market.angel_live_observation_normalizer import normalize_angel_candle_series, normalize_angel_live_observation, normalize_angel_spot_response
from services.paper_orchestration.certified_live_provider_readers import NIFTY_MARKET_SPEC, SENSEX_MARKET_SPEC

NOW = datetime(2026, 8, 3, 10, tzinfo=timezone.utc)
ROW = ["2026-08-03T15:20:00+05:30", 100, 102, 99, 101, 10]

@pytest.mark.parametrize("spec", (NIFTY_MARKET_SPEC, SENSEX_MARKET_SPEC))
def test_spot_preserves_exact_certified_identity(spec):
    value = normalize_angel_spot_response(response={"data": {"ltp": 100, "tradingsymbol": spec.underlying_symbol, "exchange": spec.exchange, "symboltoken": spec.symboltoken}}, market_spec=spec, provider_timestamp=NOW, evaluated_at=NOW)
    assert (value.underlying_symbol, value.exchange, value.symboltoken, value.option_exchange) == (spec.underlying_symbol, spec.exchange, spec.symboltoken, spec.option_exchange)

def test_missing_spot_and_empty_candles_fail_closed():
    value = normalize_angel_live_observation(spot_response={}, candle_rows_by_timeframe={}, market_spec=NIFTY_MARKET_SPEC, provider_timestamp=NOW, evaluated_at=NOW)
    assert "SPOT_RESPONSE_MALFORMED" in value.blockers and "TIMEFRAME_UNAVAILABLE_5m" in value.blockers

def test_forming_candle_is_excluded_and_completed_candle_retained():
    completed = ["2026-08-03T15:15:00+05:30", 100, 102, 99, 101, 10]
    forming = ["2026-08-03T15:30:00+05:30", 100, 102, 99, 101, 10]
    result = normalize_angel_candle_series(rows=(completed, forming), market_spec=NIFTY_MARKET_SPEC, timeframe="5m", provider_timestamp=NOW, evaluated_at=NOW)
    assert len(result.candles) == 1 and result.candles[0].is_complete is True

@pytest.mark.parametrize("row", (["bad", 1, 2, 0, 1, 1], ["2026-08-03T15:15:00+05:30", 1, 0.5, 2, 1, 1], ["2026-08-03T15:15:00+05:30", 1, 2, 0.5, 1, -1]))
def test_malformed_or_invalid_ohlcv_is_rejected(row):
    with pytest.raises(ValueError): normalize_angel_candle_series(rows=(row,), market_spec=NIFTY_MARKET_SPEC, timeframe="5m", provider_timestamp=NOW, evaluated_at=NOW)

def test_duplicate_and_cross_market_spot_are_rejected():
    with pytest.raises(ValueError): normalize_angel_candle_series(rows=(ROW, ROW), market_spec=NIFTY_MARKET_SPEC, timeframe="5m", provider_timestamp=NOW, evaluated_at=NOW)
    with pytest.raises(ValueError): normalize_angel_spot_response(response={"data": {"ltp": 1, "tradingsymbol": "SENSEX"}}, market_spec=NIFTY_MARKET_SPEC, provider_timestamp=NOW, evaluated_at=NOW)
