"""Task 5 Slice 3 active position repository certification."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)


NOW = datetime(2026, 8, 3, 9, 35, tzinfo=timezone.utc)


def position(**changes):
    values = dict(
        position_id="position-1",
        recommendation_id="recommendation-1",
        reservation_result_id="reservation-1",
        fill_result_id="fill-1",
        opened_at=NOW,
        updated_at=NOW,
        underlying_symbol="NIFTY",
        exchange="NSE",
        option_right="CALL",
        contract="NIFTY06AUG26C25000",
        expiry="2026-08-06",
        strike=25_000.0,
        entry_price=100.5,
        stop_loss=95.0,
        target_1=110.0,
        target_2=120.0,
        target_3=130.0,
        initial_lots=2,
        remaining_lots=2,
        lot_size=25,
        initial_quantity=50,
        remaining_quantity=50,
        reserved_capital=5_050.0,
        maximum_loss=1_000.0,
    )
    values.update(changes)
    return ActivePaperPositionV1(**values)


def test_repository_persists_and_reloads_active_position(tmp_path):
    path = tmp_path / "paper_positions.json"
    repository = JsonPaperPositionRepository(path)
    repository.save(position())

    reloaded = JsonPaperPositionRepository(path)
    assert reloaded.get("position-1") == position()
    assert reloaded.list_active() == (position(),)


def test_repository_updates_position_and_preserves_single_record(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    original = position()
    repository.save(original)
    updated = replace(
        original,
        updated_at=NOW + timedelta(seconds=1),
        lifecycle_state="PARTIALLY_EXITED",
        remaining_lots=1,
        remaining_quantity=25,
        target_1_hit=True,
        realized_pnl=237.5,
        processed_event_ids=("event-1",),
    )
    repository.save(updated)

    assert repository.list_all() == (updated,)
    assert repository.list_active() == (updated,)


def test_closed_position_is_retained_but_not_active(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    closed = position(
        lifecycle_state="CLOSED",
        remaining_lots=0,
        remaining_quantity=0,
        target_1_hit=True,
        target_2_hit=True,
        target_3_hit=True,
    )
    repository.save(closed)

    assert repository.list_all() == (closed,)
    assert repository.list_active() == ()


def test_duplicate_active_recommendation_is_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(position())

    with pytest.raises(ValueError, match="duplicate active"):
        repository.save(
            position(
                position_id="position-2",
                contract="SENSEX07AUG26P80000",
                underlying_symbol="SENSEX",
                exchange="BSE",
            )
        )


def test_duplicate_active_contract_is_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(position())

    with pytest.raises(ValueError, match="duplicate active"):
        repository.save(
            position(
                position_id="position-2",
                recommendation_id="recommendation-2",
            )
        )


def test_stale_update_is_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(
        position(updated_at=NOW + timedelta(seconds=2))
    )

    with pytest.raises(ValueError, match="stale"):
        repository.save(position(updated_at=NOW))


def test_corrupt_repository_fails_closed(tmp_path):
    path = tmp_path / "positions.json"
    path.write_text("{bad-json", encoding="utf-8")
    repository = JsonPaperPositionRepository(path)

    with pytest.raises(ValueError, match="invalid PAPER"):
        repository.list_all()


def test_repository_writes_valid_json_without_temp_file(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    repository.save(position())

    assert json.loads(path.read_text(encoding="utf-8"))
    assert not path.with_suffix(".json.tmp").exists()


def test_position_contract_enforces_geometry_and_size():
    with pytest.raises(ValueError, match="trade geometry"):
        position(stop_loss=105.0)
    with pytest.raises(ValueError, match="initial_quantity"):
        position(initial_quantity=49)
    with pytest.raises(ValueError, match="PAPER-only"):
        position(broker_order_submission=True)
