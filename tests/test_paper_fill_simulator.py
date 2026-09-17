"""Task 5 Slice 1 PAPER order/fill simulation certification."""
from datetime import datetime, timedelta, timezone
import ast
from pathlib import Path

import pytest

from services.contracts.paper_fill_simulation_v1 import (
    PaperEntryOrderV1,
    PaperFillQuoteEvidenceV1,
    PaperFillResultV1,
)
from services.paper_trading.paper_fill_simulator import (
    simulate_paper_entry_fill,
)


NOW = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)


def order(**changes):
    values = dict(
        order_id="order-1",
        recommendation_id="recommendation-1",
        parent_cycle_id="parent-1",
        submitted_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        option_right="CALL",
        contract="NIFTY06AUG26C25000",
        expiry="2026-08-06",
        strike=25_000.0,
        order_type="LIMIT",
        limit_price=101.0,
        lots=2,
        lot_size=25,
        quantity=50,
        maximum_capital=5_100.0,
        maximum_loss=1_000.0,
        maximum_slippage_fraction=0.01,
    )
    values.update(changes)
    return PaperEntryOrderV1(**values)


def quote(**changes):
    values = dict(
        quote_id="quote-1",
        contract="NIFTY06AUG26C25000",
        observed_at=NOW + timedelta(seconds=1),
        bid_price=99.5,
        ask_price=100.5,
        last_price=100.0,
        available_ask_quantity=500,
        source="REPLAY",
    )
    values.update(changes)
    return PaperFillQuoteEvidenceV1(**values)


def simulate(order_value=None, quote_value=None):
    return simulate_paper_entry_fill(
        fill_result_id="fill-1",
        order=order_value or order(),
        quote=quote_value or quote(),
    )


def test_marketable_limit_order_fills_deterministically():
    result = simulate()
    assert type(result) is PaperFillResultV1
    assert result.status == "FILLED"
    assert result.filled_quantity == 50
    assert result.filled_lots == 2
    assert result.fill_price == 100.5
    assert result.gross_premium_outlay == 5_025.0
    assert result.slippage_amount_per_unit == 0.0
    assert result.slippage_fraction == 0.0
    assert result.remaining_quantity == 0


def test_market_order_fills_at_ask():
    result = simulate(
        order_value=order(
            order_type="MARKET",
            limit_price=None,
        )
    )
    assert result.status == "FILLED"
    assert result.fill_price == 100.5


def test_non_marketable_limit_order_is_not_filled():
    result = simulate(order_value=order(limit_price=100.0))
    assert result.status == "NOT_FILLED"
    assert result.fill_price is None
    assert result.remaining_quantity == 50
    assert "LIMIT_PRICE_NOT_MARKETABLE" in result.blockers


def test_insufficient_quantity_is_not_filled_all_or_none():
    result = simulate(
        quote_value=quote(available_ask_quantity=49)
    )
    assert result.status == "NOT_FILLED"
    assert result.filled_quantity == 0
    assert result.remaining_quantity == 50
    assert "INSUFFICIENT_ASK_QUANTITY" in result.blockers


def test_stale_quote_is_rejected():
    result = simulate(quote_value=quote(is_stale=True))
    assert result.status == "REJECTED"
    assert "STALE_FILL_QUOTE" in result.blockers


def test_fill_exceeding_capital_is_rejected():
    result = simulate(
        order_value=order(maximum_capital=5_000.0),
    )
    assert result.status == "REJECTED"
    assert "FILL_EXCEEDS_MAXIMUM_CAPITAL" in result.blockers


def test_order_contract_rejects_invalid_quantity_and_live_flags():
    with pytest.raises(ValueError, match="quantity"):
        order(quantity=49)
    with pytest.raises(ValueError, match="PAPER-only"):
        order(broker_order_submission=True)


def test_quote_contract_and_time_are_strict():
    with pytest.raises(ValueError, match="bid_price"):
        quote(bid_price=101.0, ask_price=100.0)
    with pytest.raises(ValueError, match="precedes"):
        simulate(
            quote_value=quote(
                observed_at=NOW - timedelta(seconds=1)
            )
        )


def test_simulator_has_no_persistence_capital_reservation_or_monitoring():
    source = Path(
        "services/paper_trading/paper_fill_simulator.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    forbidden = (
        "repository",
        "persistence",
        "portfolio",
        "monitor",
        "broker",
        "dashboard",
        "sqlite",
    )
    assert not any(
        any(token in module for token in forbidden)
        for module in imports
    )
    for token in (
        "place_order(",
        "submit_order(",
        "random.",
        "datetime.now(",
        "datetime.utcnow(",
        "uuid4(",
        "time.sleep(",
    ):
        assert token not in source
