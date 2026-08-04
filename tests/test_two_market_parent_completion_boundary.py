from dataclasses import replace
from datetime import timedelta

from services.paper_orchestration.two_market_parent_cycle_coordinator import (
    run_two_market_parent_cycle,
)
from tests.test_two_market_parent_cycle_coordinator import (
    candidate_for,
    parent,
)


def test_parent_final_completion_expands_to_latest_child_receipt():
    value = parent()

    received = {
        "NIFTY": value.completed_at + timedelta(seconds=30),
        "SENSEX": value.completed_at + timedelta(seconds=45),
    }

    def evaluate(symbol, exchange, observation_id):
        candidate = candidate_for(
            symbol,
            observation_id,
            requested_at=value.requested_at,
            received_at=received[symbol],
        )
        assert candidate.exchange == exchange
        return candidate

    result = run_two_market_parent_cycle(
        value,
        child_evaluator=evaluate,
    )

    assert tuple(
        entry.child.terminal_status for entry in result.entries
    ) == ("COMPLETED", "COMPLETED")
    assert result.completed_at == received["SENSEX"]
    assert tuple(
        entry.child.received_at for entry in result.entries
    ) == (
        received["NIFTY"],
        received["SENSEX"],
    )
