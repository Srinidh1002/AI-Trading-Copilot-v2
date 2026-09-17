from datetime import datetime, timezone

import pytest

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
)
from services.paper_orchestration.certified_monitoring_input_factory import (
    CertifiedMonitoringInputFactory,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringInputV1,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


def exact(contract, **fields):
    value = object.__new__(contract)
    for name, item in fields.items():
        object.__setattr__(value, name, item)
    return value


def cycle():
    value = exact(
        PaperOrchestrationCycleInputV1,
        cycle_id="monitor-cycle-1",
        cycle_idempotency_key="monitor-cycle-key-1",
        trading_day_id="2026-01-08",
        cycle_requested_at=NOW,
        p8_update_event_id="p8-update-event-1",
        p8_update_idempotency_key="p8-update-key-1",
    )
    return value


def p7_snapshot(position_id="position-1"):
    position = type("Position", (), {"position_id": position_id})()
    return exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id="paper-trade-1",
        position=position,
    )


def evaluation(position_id="position-1", timestamp=NOW):
    position = type("Position", (), {"position_id": position_id})()
    return exact(
        PaperTradePositionEvaluationInputV1,
        position=position,
        evaluation_timestamp=timestamp,
    )


def factory():
    return CertifiedMonitoringInputFactory(
        portfolio_id="certified-paper-portfolio",
        p7_snapshot_provider=lambda _: p7_snapshot(),
        portfolio_policy_provider=lambda *_: exact(
            PaperPortfolioPolicyV1
        ),
        evaluation_input_builder=lambda *_: evaluation(),
    )


def test_builds_exact_monitoring_input():
    result = factory()(cycle())

    assert type(result) is ExistingPositionMonitoringInputV1
    assert result.portfolio_id == "certified-paper-portfolio"
    assert result.portfolio_event_id == "p8-update-event-1"
    assert result.update_idempotency_key == "p8-update-key-1"
    assert result.updated_at == NOW
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_monitoring_ids_are_deterministic():
    first = factory()(cycle())
    second = factory()(cycle())

    assert first.result_snapshot_id == second.result_snapshot_id


def test_position_mismatch_fails_closed():
    value = CertifiedMonitoringInputFactory(
        portfolio_id="certified-paper-portfolio",
        p7_snapshot_provider=lambda _: p7_snapshot("position-1"),
        portfolio_policy_provider=lambda *_: exact(
            PaperPortfolioPolicyV1
        ),
        evaluation_input_builder=lambda *_: evaluation("position-2"),
    )

    with pytest.raises(ValueError, match="position identity"):
        value(cycle())


def test_timestamp_mismatch_fails_closed():
    other = datetime(2026, 1, 8, 10, 1, tzinfo=timezone.utc)
    value = CertifiedMonitoringInputFactory(
        portfolio_id="certified-paper-portfolio",
        p7_snapshot_provider=lambda _: p7_snapshot(),
        portfolio_policy_provider=lambda *_: exact(
            PaperPortfolioPolicyV1
        ),
        evaluation_input_builder=lambda *_: evaluation(timestamp=other),
    )

    with pytest.raises(ValueError, match="cycle_requested_at"):
        value(cycle())


def test_legacy_mapping_is_rejected():
    value = CertifiedMonitoringInputFactory(
        portfolio_id="certified-paper-portfolio",
        p7_snapshot_provider=lambda _: {},
        portfolio_policy_provider=lambda *_: exact(
            PaperPortfolioPolicyV1
        ),
        evaluation_input_builder=lambda *_: evaluation(),
    )

    with pytest.raises(TypeError, match="PaperTradePersistenceSnapshotV1"):
        value(cycle())
