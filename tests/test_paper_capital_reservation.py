"""Task 5 Slice 2 reservation and duplicate prevention certification."""
from datetime import datetime, timezone
import ast
from pathlib import Path

import pytest

from services.contracts.paper_entry_admission_v1 import (
    ExistingPaperReservationV1,
    PaperCapitalReservationInputV1,
    PaperFeePolicyV1,
)
from services.paper_trading.paper_capital_reservation import (
    calculate_paper_entry_fees,
    reserve_paper_entry_capital,
)

NOW = datetime(2026, 8, 3, 9, 31, tzinfo=timezone.utc)

def policy():
    return PaperFeePolicyV1(
        policy_id="fees-v1",
        brokerage_per_order=20.0,
        exchange_transaction_fraction=0.0005,
        sebi_fraction=0.000001,
        stamp_duty_fraction=0.00003,
        stt_fraction=0.000625,
        gst_fraction_on_charges=0.18,
    )

def reservation(**changes):
    values = dict(
        reservation_request_id="request-1",
        recommendation_id="recommendation-1",
        contract="NIFTY06AUG26C25000",
        evaluated_at=NOW,
        available_capital=100_000.0,
        fill_gross_premium_outlay=5_025.0,
        maximum_loss=1_000.0,
        fee_policy=policy(),
        existing_reservations=(),
    )
    values.update(changes)
    return PaperCapitalReservationInputV1(**values)

def evaluate(value=None):
    return reserve_paper_entry_capital(
        reservation_result_id="reservation-result-1",
        reservation_input=value or reservation(),
    )

def test_fee_calculation_is_deterministic():
    result = calculate_paper_entry_fees(reservation())
    assert result.brokerage == 20.0
    assert result.exchange_transaction_charges == pytest.approx(2.5125)
    assert result.sebi_charges == pytest.approx(0.005025)
    assert result.stamp_duty == pytest.approx(0.15075)
    assert result.stt == pytest.approx(3.140625)
    assert result.gst == pytest.approx((20.0 + 2.5125 + 0.005025) * 0.18)
    assert result.total_capital_required == pytest.approx(
        5_025.0 + result.total_fees
    )

def test_capital_is_reserved_including_fees():
    result = evaluate()
    assert result.status == "RESERVED"
    assert result.newly_reserved_capital == pytest.approx(
        result.fee_breakdown.total_capital_required
    )
    assert result.total_reserved_capital == pytest.approx(
        result.newly_reserved_capital
    )
    assert result.remaining_capital == pytest.approx(
        100_000.0 - result.newly_reserved_capital
    )

def test_existing_active_reservations_reduce_available_capital():
    existing = (
        ExistingPaperReservationV1(
            reservation_id="existing-1",
            recommendation_id="old-rec",
            contract="SENSEX07AUG26P80000",
            reserved_capital=90_000.0,
        ),
    )
    result = evaluate(reservation(existing_reservations=existing))
    assert result.existing_reserved_capital == 90_000.0
    assert result.status == "RESERVED"

def test_duplicate_recommendation_is_rejected():
    existing = (
        ExistingPaperReservationV1(
            reservation_id="existing-1",
            recommendation_id="recommendation-1",
            contract="SENSEX07AUG26P80000",
            reserved_capital=10_000.0,
        ),
    )
    result = evaluate(reservation(existing_reservations=existing))
    assert result.status == "REJECTED"
    assert "DUPLICATE_RECOMMENDATION" in result.blockers
    assert result.newly_reserved_capital == 0.0

def test_duplicate_contract_is_rejected():
    existing = (
        ExistingPaperReservationV1(
            reservation_id="existing-1",
            recommendation_id="old-rec",
            contract="NIFTY06AUG26C25000",
            reserved_capital=10_000.0,
        ),
    )
    result = evaluate(reservation(existing_reservations=existing))
    assert result.status == "REJECTED"
    assert "DUPLICATE_ACTIVE_CONTRACT" in result.blockers

def test_insufficient_unreserved_capital_is_rejected():
    existing = (
        ExistingPaperReservationV1(
            reservation_id="existing-1",
            recommendation_id="old-rec",
            contract="SENSEX07AUG26P80000",
            reserved_capital=96_000.0,
        ),
    )
    result = evaluate(reservation(existing_reservations=existing))
    assert result.status == "REJECTED"
    assert "INSUFFICIENT_UNRESERVED_CAPITAL" in result.blockers

def test_inactive_reservation_does_not_block_or_reduce_capital():
    existing = (
        ExistingPaperReservationV1(
            reservation_id="existing-1",
            recommendation_id="recommendation-1",
            contract="NIFTY06AUG26C25000",
            reserved_capital=50_000.0,
            active=False,
        ),
    )
    result = evaluate(reservation(existing_reservations=existing))
    assert result.status == "RESERVED"
    assert result.existing_reserved_capital == 0.0

def test_service_has_no_persistence_monitoring_or_broker_dependency():
    source = Path(
        "services/paper_trading/paper_capital_reservation.py"
    ).read_text(encoding="utf-8")
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = ("repository", "persistence", "monitor", "broker", "dashboard", "sqlite")
    assert not any(any(token in module for token in forbidden) for module in imports)
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

