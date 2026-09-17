from datetime import datetime, timedelta, timezone

import pytest

from services.contracts import PaperOrderStateV1
from services.paper import InMemoryPaperOrderRepository

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
CASES = (("NIFTY", "NSE", "BUY", "CALL"), ("BANKNIFTY", "NSE", "SELL", "PUT"),
         ("FINNIFTY", "NSE", "BUY", "CALL"), ("SENSEX", "BSE", "SELL", "PUT"))


@pytest.mark.parametrize("symbol,exchange,action,option_type", CASES)
@pytest.mark.parametrize("repeat", range(10))
def test_four_index_states_preserve_long_premium_details(symbol, exchange, action, option_type, repeat):
    repo = InMemoryPaperOrderRepository(); order_id = f"{symbol}-{repeat}"
    value = PaperOrderStateV1(order_id, NOW, NOW, "SUBMITTED", f"request-{order_id}", f"key-{order_id}", symbol, exchange,
        authorization_id="auth", paper_candidate_id=f"candidate-{symbol}", canonical_risk_result_id=f"risk-{symbol}",
        trading_symbol=f"{symbol}{option_type}", action=action, option_type=option_type, position_side="LONG",
        quantity=50, lots=1, reference_price=10.0)
    repo.save(value)
    stored = repo.get(order_id)
    assert stored == value and stored.trading_symbol.startswith(symbol) and stored.position_side == "LONG"
    assert stored.quantity == 50 and stored.lots == 1 and stored.reference_price == 10.0
    assert repo.get_by_execution_request_id(value.execution_request_id) == value
    assert repo.list_by_identity(symbol, exchange) == (value,)
    filled = PaperOrderStateV1(order_id, NOW, NOW + timedelta(seconds=1), "FILLED", value.execution_request_id, value.idempotency_key, symbol, exchange,
        authorization_id=value.authorization_id, execution_result_id=f"result-{order_id}", paper_candidate_id=value.paper_candidate_id,
        canonical_risk_result_id=value.canonical_risk_result_id, trading_symbol=value.trading_symbol, action=action,
        option_type=option_type, position_side="LONG", quantity=50, lots=1, reference_price=10.0, fill_price=11.0)
    assert repo.transition(order_id, next_state=filled).order_status == "FILLED"


def test_identity_filter_never_infers_identity_from_trading_symbol():
    repo = InMemoryPaperOrderRepository()
    value = PaperOrderStateV1("order", NOW, NOW, "SUBMITTED", "request", "key", "SENSEX", "BSE",
        authorization_id="auth", paper_candidate_id="candidate", canonical_risk_result_id="risk",
        trading_symbol="NIFTYCE", action="BUY", option_type="CALL", position_side="LONG",
        quantity=50, lots=1, reference_price=10.0)
    repo.save(value)
    assert repo.list_by_identity("SENSEX", "BSE") == (value,)
    assert repo.list_by_identity("NIFTY", "NSE") == ()
