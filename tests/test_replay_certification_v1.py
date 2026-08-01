"""Task 7A Slice 1 replay contract certification."""
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.replay_certification_v1 import (
    ReplayCertificationLedgerV1,
    ReplayScenarioV1,
    ReplayTradeResultV1,
)


NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


def scenario(**changes):
    values = dict(
        scenario_id="nifty-001",
        sequence=1,
        market=("NIFTY", "NSE"),
        scenario_type="TRENDING_UP",
        expected_outcome="CLOSED_TRADE",
        fixture_id="fixture-nifty-001",
        replay_started_at=NOW,
        tags=("trend", "call"),
        expected_actions=("HOLD", "TARGET_3_HIT"),
    )
    values.update(changes)
    return ReplayScenarioV1(**values)


def closed_result(**changes):
    values = dict(
        result_id="result-nifty-001",
        scenario_id="nifty-001",
        sequence=1,
        market=("NIFTY", "NSE"),
        scenario_type="ALL_TARGETS",
        status="CLOSED_TRADE",
        opened=True,
        closed=True,
        opened_at=NOW,
        closed_at=NOW + timedelta(minutes=15),
        closure_reason="TARGET_3",
        realized_pnl=1500.0,
        action_history=(
            "HOLD",
            "TARGET_1_HIT",
            "TARGET_2_HIT",
            "TARGET_3_HIT",
        ),
    )
    values.update(changes)
    return ReplayTradeResultV1(**values)


def no_trade_result(**changes):
    values = dict(
        result_id="result-sensex-001",
        scenario_id="sensex-001",
        sequence=1,
        market=("SENSEX", "BSE"),
        scenario_type="STALE_DATA",
        status="NO_TRADE",
        opened=False,
        closed=False,
        opened_at=None,
        closed_at=None,
        closure_reason=None,
        realized_pnl=0.0,
        action_history=("NO_TRADE",),
        blockers=("STALE_DATA",),
    )
    values.update(changes)
    return ReplayTradeResultV1(**values)


def test_scenario_accepts_only_nifty_or_sensex():
    assert scenario().market == ("NIFTY", "NSE")

    with pytest.raises(ValueError, match="market"):
        scenario(market=("BANKNIFTY", "NSE"))


def test_scenario_is_strictly_offline_paper_only():
    with pytest.raises(ValueError, match="offline PAPER"):
        scenario(network_access_allowed=True)

    with pytest.raises(ValueError, match="offline PAPER"):
        scenario(broker_submission_enabled=True)

    with pytest.raises(ValueError, match="offline PAPER"):
        scenario(live_execution_eligible=True)


def test_closed_trade_must_open_and_close():
    result = closed_result()

    assert result.status == "CLOSED_TRADE"
    assert result.opened is True
    assert result.closed is True

    with pytest.raises(ValueError, match="open and close"):
        closed_result(closed=False)


def test_closed_trade_requires_valid_terminal_evidence():
    with pytest.raises(ValueError, match="timestamps"):
        closed_result(closed_at=None)

    with pytest.raises(ValueError, match="closure_reason"):
        closed_result(closure_reason=None)

    with pytest.raises(ValueError, match="action_history"):
        closed_result(action_history=())


def test_non_trade_result_cannot_claim_position_activity():
    value = no_trade_result()

    assert value.status == "NO_TRADE"
    assert value.realized_pnl == 0.0

    with pytest.raises(ValueError, match="cannot open or close"):
        no_trade_result(opened=True)


def test_blocked_and_failed_require_diagnostics():
    with pytest.raises(ValueError, match="blockers"):
        no_trade_result(
            status="BLOCKED",
            blockers=(),
        )

    with pytest.raises(ValueError, match="errors"):
        no_trade_result(
            status="FAILED",
            blockers=(),
            errors=(),
        )


def test_ledger_counts_trade_and_non_trade_outcomes_separately():
    ledger = ReplayCertificationLedgerV1(
        ledger_id="ledger-1",
        generated_at=NOW,
        results=(
            closed_result(),
            no_trade_result(),
        ),
    )

    assert ledger.nifty_closed_trade_count == 1
    assert ledger.sensex_closed_trade_count == 0
    assert ledger.no_trade_count == 1
    assert ledger.blocked_count == 0
    assert ledger.failed_count == 0
    assert ledger.is_complete is False


def test_ledger_is_complete_only_at_required_per_market_counts():
    results = []
    for sequence in range(1, 61):
        results.append(
            closed_result(
                result_id=f"result-nifty-{sequence}",
                scenario_id=f"nifty-{sequence}",
                sequence=sequence,
            )
        )
        results.append(
            closed_result(
                result_id=f"result-sensex-{sequence}",
                scenario_id=f"sensex-{sequence}",
                sequence=sequence,
                market=("SENSEX", "BSE"),
            )
        )

    ledger = ReplayCertificationLedgerV1(
        ledger_id="ledger-complete",
        generated_at=NOW,
        results=tuple(results),
    )

    assert ledger.nifty_closed_trade_count == 60
    assert ledger.sensex_closed_trade_count == 60
    assert ledger.is_complete is True


def test_any_failed_result_prevents_completion():
    results = []
    for sequence in range(1, 61):
        results.append(
            closed_result(
                result_id=f"result-nifty-{sequence}",
                scenario_id=f"nifty-{sequence}",
                sequence=sequence,
            )
        )
        results.append(
            closed_result(
                result_id=f"result-sensex-{sequence}",
                scenario_id=f"sensex-{sequence}",
                sequence=sequence,
                market=("SENSEX", "BSE"),
            )
        )
    results.append(
        no_trade_result(
            result_id="failed-result",
            scenario_id="failed-scenario",
            sequence=61,
            status="FAILED",
            blockers=(),
            errors=("REPLAY_RUNTIME_FAILURE",),
        )
    )

    ledger = ReplayCertificationLedgerV1(
        ledger_id="ledger-failed",
        generated_at=NOW,
        results=tuple(results),
    )

    assert ledger.failed_count == 1
    assert ledger.is_complete is False


def test_duplicate_result_and_scenario_ids_fail_closed():
    item = closed_result()

    with pytest.raises(ValueError, match="duplicate result_id"):
        ReplayCertificationLedgerV1(
            ledger_id="ledger-duplicate",
            generated_at=NOW,
            results=(item, item),
        )


def test_duplicate_sequence_within_same_market_fails_closed():
    with pytest.raises(ValueError, match="duplicate market sequence"):
        ReplayCertificationLedgerV1(
            ledger_id="ledger-sequence",
            generated_at=NOW,
            results=(
                closed_result(),
                closed_result(
                    result_id="result-nifty-other",
                    scenario_id="nifty-other",
                ),
            ),
        )
