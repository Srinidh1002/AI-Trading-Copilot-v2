from datetime import datetime, timezone

import pytest

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_orchestration_journal_record_v1 import (
    PaperOrchestrationJournalRecordV1,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.paper_orchestration_stage_result_v1 import (
    PaperOrchestrationStageResultV1,
)
from services.contracts.market_session_validation_v1 import (
    MarketSessionValidationV1,
)
from services.paper_orchestration.paper_orchestration_journal import (
    PaperOrchestrationJournal,
)


NOW = datetime(2026, 1, 8, 9, 30, tzinfo=timezone.utc)


def make_policy():
    return PaperOrchestrationPolicyV1(
        orchestration_policy_id="policy-1",
        policy_timestamp=NOW,
    )


def make_session():
    return MarketSessionValidationV1(
        validation_id="session-1",
        evaluated_at=NOW,
        market_timestamp=NOW,
        symbol="NIFTY",
        exchange="NSE",
        timezone="Asia/Kolkata",
        trading_date=NOW.date(),
        session_state="REGULAR",
        session_phase="REGULAR_TRADING",
        trading_day_status="TRADING_DAY",
        is_trading_day=True,
        regular_session_open=True,
        analysis_allowed=True,
        paper_preparation_allowed=True,
        paper_execution_allowed=True,
    )


def make_cycle_input(key="cycle-key-1"):
    return PaperOrchestrationCycleInputV1(
        cycle_id="cycle-1",
        cycle_idempotency_key=key,
        observation_id="observation-1",
        orchestration_policy=make_policy(),
        underlying_symbol="NIFTY",
        exchange="NSE",
        trading_day_id=NOW.date().isoformat(),
        market_timestamp=NOW,
        received_at=NOW,
        cycle_requested_at=NOW,
        session_validation=make_session(),
        p6_integration_id="p6-1",
        p8_admission_request_id="p8-admission-1",
        p8_admission_idempotency_key="p8-admission-key-1",
        p8_portfolio_event_id="p8-event-1",
        p7_requested_transition_id="p7-transition-1",
        p7_position_id="p7-position-1",
        p7_entry_fill_id="p7-entry-fill-1",
        p8_update_idempotency_key="p8-update-key-1",
        p8_update_event_id="p8-update-event-1",
    )


def make_result(cycle_input):
    stage = PaperOrchestrationStageResultV1(
        stage_result_id="stage-data",
        cycle_id=cycle_input.cycle_id,
        stage="DATA",
        status="COMPLETED",
        started_at=NOW,
        completed_at=NOW,
    )
    return PaperOrchestrationCycleResultV1(
        cycle_result_id="result-1",
        cycle_id=cycle_input.cycle_id,
        cycle_idempotency_key=(
            cycle_input.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
        cycle_status="COMPLETED",
        terminal_stage="DATA",
        started_at=NOW,
        completed_at=NOW,
        stage_results=(stage,),
    )


def make_record(cycle_input):
    return PaperOrchestrationJournalRecordV1(
        journal_record_id="journal-record-1",
        cycle_idempotency_key=(
            cycle_input.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
        cycle_result=make_result(cycle_input),
        persisted_at=NOW,
    )


def test_new_cycle_classification(tmp_path):
    journal = PaperOrchestrationJournal(
        tmp_path / "journal.json"
    )
    cycle_input = make_cycle_input()
    assert journal.classify(
        cycle_idempotency_key=(
            cycle_input.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
    ) == "NEW"


def test_same_payload_duplicate_classification(tmp_path):
    journal = PaperOrchestrationJournal(
        tmp_path / "journal.json"
    )
    cycle_input = make_cycle_input()
    journal.save(make_record(cycle_input))

    assert journal.classify(
        cycle_idempotency_key=(
            cycle_input.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
    ) == "DUPLICATE_SAME_PAYLOAD"


def test_payload_conflict_fails_closed(tmp_path):
    journal = PaperOrchestrationJournal(
        tmp_path / "journal.json"
    )
    first = make_cycle_input()
    journal.save(make_record(first))

    second = make_cycle_input()
    object.__setattr__(
        second,
        "observation_id",
        "observation-2",
    )

    assert journal.classify(
        cycle_idempotency_key=(
            second.cycle_idempotency_key
        ),
        cycle_input_semantic_hash=second.semantic_hash(),
    ) == "IDEMPOTENCY_PAYLOAD_CONFLICT"


def test_journal_rejects_conflicting_save(tmp_path):
    journal = PaperOrchestrationJournal(
        tmp_path / "journal.json"
    )
    first = make_cycle_input()
    journal.save(make_record(first))

    second = make_cycle_input()
    object.__setattr__(
        second,
        "observation_id",
        "observation-2",
    )
    with pytest.raises(
        ValueError,
        match="IDEMPOTENCY_PAYLOAD_CONFLICT",
    ):
        journal.save(make_record(second))


def test_atomic_document_contains_integrity_hash(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal = PaperOrchestrationJournal(journal_path)
    cycle_input = make_cycle_input()
    record = make_record(cycle_input)
    journal.save(record)

    raw = journal.get_raw(
        cycle_input.cycle_idempotency_key
    )
    assert raw["integrity_hash"] == record.integrity_hash
    assert journal.count() == 1
