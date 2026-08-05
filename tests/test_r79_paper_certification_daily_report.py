from dataclasses import FrozenInstanceError

import pytest

from tests.r79_reporting_helpers import build_daily


def test_daily_report_reconciles_authoritative_sources():
    report = build_daily()

    assert report.source_prediction_count == 2
    assert report.official_prediction_count == 2
    assert report.completed_outcome_count == 2
    assert report.pending_outcome_count == 0
    assert report.excluded_prediction_count == 0
    assert report.no_trade_cycle_count == 1
    assert report.entry_count == 1
    assert report.closed_position_count == 1
    assert report.win_count == 0
    assert report.loss_count == 1
    assert report.break_even_count == 0
    assert report.ending_capital == (
        report.starting_capital + report.net_pnl
    )
    assert dict(report.market_distribution)["NIFTY"] == 2
    actions = dict(report.action_distribution)
    assert actions["CALL"] == 1
    assert actions["PUT"] == 0
    assert actions["WAIT"] == 1
    selected = dict(report.selected_market_distribution)
    assert selected == {"NIFTY": 1, "SENSEX": 0}
    outcomes = dict(report.outcome_distribution)
    assert outcomes["NO_TRADE_CORRECT"] == 1
    assert outcomes["STOP_HIT"] == 1
    assert outcomes["T1_HIT"] == 0
    incidents = dict(report.incident_distribution)
    assert incidents["DATA_PROVIDER"] == 1
    assert incidents["LIFECYCLE"] == 0
    duplicates = dict(report.duplicate_distribution)
    assert duplicates["PREDICTION"] == 1
    assert duplicates["ENTRY"] == 0


def test_daily_report_is_immutable_and_deterministic():
    first = build_daily()
    second = build_daily()

    assert first == second
    assert first.to_json() == second.to_json()
    assert len(first.semantic_hash) == 64

    with pytest.raises(FrozenInstanceError):
        first.net_pnl = 0.0


def test_excluded_replay_is_audited_not_marked_pending():
    report = build_daily(include_excluded=True)

    assert report.source_prediction_count == 3
    assert report.official_prediction_count == 2
    assert report.pending_outcome_count == 0
    assert report.excluded_prediction_count == 1
    assert report.excluded_audit[0].status == "EXCLUDED_REPLAY"
    assert report.excluded_audit[0].reason_codes == (
        "RECORD_SOURCE_REPLAY",
    )
    assert dict(report.market_distribution) == {
        "NIFTY": 2,
        "SENSEX": 1,
    }
