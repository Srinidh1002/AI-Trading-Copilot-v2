from datetime import timedelta

import pytest

from services.analysis.shared_broader_market_context import CORRELATION_TIMEFRAME, build_certified_shared_broader_context
from services.market.angel_live_observation_normalizer import normalize_angel_live_observation
from services.paper_orchestration.certified_live_provider_readers import market_spec_for
from tests.test_task8_parent_typed_candidate_certification import NOW, _rows


def observation(symbol, exchange, spot, *, rows=None, evaluated_at=NOW):
    spec = market_spec_for(symbol, exchange)
    values = {name: _rows(name, spot) for name in ("5m", "15m", "1h", "1d")}
    if rows is not None:
        values = rows
    return normalize_angel_live_observation(
        spot_response={"data": {"ltp": spot, "tradingsymbol": symbol, "exchange": exchange, "symboltoken": spec.symboltoken}},
        candle_rows_by_timeframe=values, market_spec=spec, provider_timestamp=NOW, evaluated_at=evaluated_at,
    )


def test_shared_context_builds_nifty_and_sensex_primary_correlation_once_each():
    result = build_certified_shared_broader_context(
        nifty_observation=observation("NIFTY", "NSE", 25000.0),
        sensex_observation=observation("SENSEX", "BSE", 80000.0), evaluated_at=NOW,
    )
    assert CORRELATION_TIMEFRAME == "5m"
    assert result.nifty_broader_market.cross_market_evidence[0].related_symbol == "SENSEX"
    assert result.sensex_broader_market.cross_market_evidence[0].related_symbol == "NIFTY"
    assert "optional breadth evidence is unavailable" in result.nifty_broader_market.warnings
    assert "optional volatility context is unavailable" in result.sensex_broader_market.warnings


def test_missing_timeframe_is_explicit_and_cross_market_boundary_is_fail_closed():
    rows = {name: _rows(name, 25000.0) for name in ("15m", "1h", "1d")}
    result = build_certified_shared_broader_context(
        nifty_observation=observation("NIFTY", "NSE", 25000.0, rows=rows),
        sensex_observation=observation("SENSEX", "BSE", 80000.0), evaluated_at=NOW,
    )
    assert result.blockers == ("CORRELATION_TIMEFRAME_UNAVAILABLE_5M",)
    assert result.nifty_broader_market is None
    with pytest.raises(ValueError):
        build_certified_shared_broader_context(
            nifty_observation=observation("NIFTY", "NSE", 25000.0),
            sensex_observation=observation("SENSEX", "BSE", 80000.0, evaluated_at=NOW + timedelta(seconds=1)),
            evaluated_at=NOW,
        )
