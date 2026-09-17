from datetime import datetime, timezone

import pytest

from services.contracts.certified_shared_market_context_v1 import CertifiedSharedMarketContextV1
from tests.fixtures.broader_market_intelligence import series


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make(**changes):
    value = dict(
        cycle_id="shared-cycle", evaluated_at=NOW,
        nifty_candle_series={"5m": series("NIFTY", "NSE")},
        sensex_candle_series={"5m": series("SENSEX", "BSE")},
        nifty_broader_market=None, sensex_broader_market=None,
        source_timestamps={}, cache_metadata={"cache": {"hit": False}},
    )
    value.update(changes)
    return CertifiedSharedMarketContextV1(**value)


def test_shared_context_preserves_exact_order_and_safe_serialization():
    value = make()
    assert [item["underlying_symbol"] for item in value.to_dict()["markets"]] == ["NIFTY", "SENSEX"]
    assert value.to_dict() == make().to_dict()
    assert "candles" not in str(value.to_dict())


def test_shared_context_rejects_wrong_identity_naive_time_and_secrets():
    with pytest.raises(ValueError):
        make(nifty_candle_series={"5m": series("SENSEX", "BSE")})
    with pytest.raises(ValueError):
        make(evaluated_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        make(cache_metadata={"authorization": "never"})
    with pytest.raises(TypeError):
        make(cache_metadata={"client": object()})
