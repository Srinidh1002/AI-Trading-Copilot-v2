"""Task 5 Slice 4 active-position recovery certification."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.active_paper_position_v1 import (
    ActivePaperPositionV1,
)
from services.paper_trading.json_paper_position_repository import (
    JsonPaperPositionRepository,
)
from services.paper_trading.paper_position_recovery import (
    recover_active_paper_position,
)


NOW = datetime(2026, 8, 3, 9, 40, tzinfo=timezone.utc)


def position(**changes):
    values = dict(
        position_id="position-1",
        recommendation_id="recommendation-1",
        reservation_result_id="reservation-1",
        fill_result_id="fill-1",
        opened_at=NOW - timedelta(minutes=5),
        updated_at=NOW - timedelta(seconds=10),
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


def recover(repository, **changes):
    values = dict(
        recovery_result_id="recovery-result-1",
        recovery_cycle_id="recovery-cycle-1",
        evaluated_at=NOW,
        repository=repository,
        maximum_position_age_seconds=60.0,
    )
    values.update(changes)
    return recover_active_paper_position(**values)


def test_empty_repository_reports_no_active_position(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    result = recover(repository)

    assert result.status == "NO_ACTIVE_POSITION"
    assert result.discovered_position_count == 0
    assert result.recovered_position is None


def test_single_active_position_is_recovered(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    expected = position()
    repository.save(expected)

    result = recover(repository)

    assert result.status == "RECOVERED"
    assert result.discovered_position_count == 1
    assert result.recovered_position == expected
    assert result.blockers == ()


def test_recovery_survives_new_repository_instance(tmp_path):
    path = tmp_path / "positions.json"
    JsonPaperPositionRepository(path).save(position())

    restarted_repository = JsonPaperPositionRepository(path)
    result = recover(restarted_repository)

    assert result.status == "RECOVERED"
    assert result.recovered_position.position_id == "position-1"


def test_multiple_active_positions_fail_closed(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    repository.save(position())
    raw = path.read_text(encoding="utf-8")
    second = raw.replace(
        '"position_id":"position-1"',
        '"position_id":"position-2"',
    ).replace(
        '"recommendation_id":"recommendation-1"',
        '"recommendation_id":"recommendation-2"',
    ).replace(
        '"contract":"NIFTY06AUG26C25000"',
        '"contract":"SENSEX07AUG26P80000"',
    ).replace(
        '"underlying_symbol":"NIFTY"',
        '"underlying_symbol":"SENSEX"',
    ).replace(
        '"exchange":"NSE"',
        '"exchange":"BSE"',
    )
    path.write_text(
        "[" + raw[1:-1] + "," + second[1:-1] + "]",
        encoding="utf-8",
    )

    result = recover(
        JsonPaperPositionRepository(path)
    )

    assert result.status == "BLOCKED"
    assert result.discovered_position_count == 2
    assert "MULTIPLE_ACTIVE_POSITIONS" in result.blockers


def test_stale_position_is_blocked(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(
        position(updated_at=NOW - timedelta(seconds=61))
    )

    result = recover(repository)

    assert result.status == "BLOCKED"
    assert "RECOVERED_POSITION_STALE" in result.blockers


def test_future_position_timestamp_is_blocked(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(
        position(updated_at=NOW + timedelta(seconds=1))
    )

    result = recover(repository)

    assert result.status == "BLOCKED"
    assert "POSITION_TIMESTAMP_IN_FUTURE" in result.blockers


def test_processed_events_are_preserved_as_warning(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    repository.save(
        position(processed_event_ids=("target-event-1",))
    )

    result = recover(repository)

    assert result.status == "RECOVERED"
    assert result.recovered_position.processed_event_ids == (
        "target-event-1",
    )
    assert "RECOVERED_WITH_PROCESSED_EVENTS" in result.warnings


def test_corrupt_repository_is_blocked_not_raised(tmp_path):
    path = tmp_path / "positions.json"
    path.write_text("{bad-json", encoding="utf-8")

    result = recover(JsonPaperPositionRepository(path))

    assert result.status == "BLOCKED"
    assert "POSITION_REPOSITORY_UNREADABLE" in result.blockers


def test_recovery_does_not_mutate_repository(tmp_path):
    path = tmp_path / "positions.json"
    repository = JsonPaperPositionRepository(path)
    repository.save(position())
    before = path.read_bytes()

    recover(repository)

    assert path.read_bytes() == before


def test_invalid_recovery_configuration_is_rejected(tmp_path):
    repository = JsonPaperPositionRepository(
        tmp_path / "positions.json"
    )
    with pytest.raises(
        ValueError,
        match="maximum_position_age_seconds",
    ):
        recover(
            repository,
            maximum_position_age_seconds=-1.0,
        )
