from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_historical_certification_replay import (
    RECORD_SOURCE,
    Task9HistoricalCertificationReplay,
    Task9HistoricalReplayError,
    Task9HistoricalReplayReceiptStore,
)
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.task9_live_paper_trade_counting_input_v1 import Task9LivePaperTradeCountingInputV1


IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 8, 10)
BOUNDARY = datetime(2026, 8, 10, 10, 0, tzinfo=IST)


def _row(timestamp, close=100, high=101, low=99):
    return [timestamp.isoformat(), 100, high, low, close, 10]


def _session_rows():
    def interval(minutes, final_hour, final_minute):
        current = datetime(2026, 8, 10, 9, 15, tzinfo=IST)
        final = datetime(2026, 8, 10, final_hour, final_minute, tzinfo=IST)
        rows = []
        while current <= final:
            rows.append(_row(current))
            current = current + timedelta(minutes=minutes)
        return rows

    five_minute = interval(5, 15, 25)
    five_minute[9] = _row(datetime(2026, 8, 10, 10, 0, tzinfo=IST), high=102, low=99.5)
    return {
        "5m": five_minute,
        "15m": interval(15, 15, 15),
        "1h": [_row(datetime(2026, 8, 10, hour, 0, tzinfo=IST)) for hour in range(9, 15)],
        "1d": [
            _row(datetime(2026, 8, 7, 0, 0, tzinfo=IST)),
        ],
    }


def _reader(*, broken_market=None, calls=None):
    def read(**kwargs):
        if calls is not None:
            calls.append((kwargs["market"], kwargs["exchange"]))
        result = _session_rows()
        if kwargs["market"] == broken_market:
            result["5m"] = []
        return result
    return read


def test_replay_accepts_friday_daily_evidence_for_monday_session(tmp_path):
    receipt = _replay(tmp_path).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"]["NIFTY"]["timeframes"]["1d"][-1]["timestamp"] == "2026-08-07T00:00:00+05:30"


@pytest.mark.parametrize("daily", (datetime(2026, 8, 10, 0, 0, tzinfo=IST), datetime(2026, 8, 11, 0, 0, tzinfo=IST)))
def test_replay_rejects_current_or_future_daily_evidence(tmp_path, daily):
    def reader(**_):
        rows = _session_rows(); rows["1d"] = [_row(daily)]; return rows
    receipt = Task9HistoricalCertificationReplay(completed_session_reader=reader, receipt_store=Task9HistoricalReplayReceiptStore(tmp_path)).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"]["NIFTY"]["status"] == "UNAVAILABLE"


def _replay(tmp_path, **kwargs):
    return Task9HistoricalCertificationReplay(
        completed_session_reader=_reader(
            broken_market=kwargs.get("broken_market"),
            calls=kwargs.get("calls"),
        ),
        receipt_store=Task9HistoricalReplayReceiptStore(tmp_path / "historical"),
        production_action_reader=kwargs.get("production_action_reader"),
        production_lifecycle_evaluator=kwargs.get("production_lifecycle_evaluator"),
        decision_engine=kwargs.get("decision_engine"),
        report_publisher=kwargs.get("report_publisher"),
    )


def test_completed_trading_date_persists_exact_timestamp_provenance_and_is_idempotent(tmp_path):
    calls = []
    replay = _replay(tmp_path, calls=calls)

    first = replay.replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    second = Task9HistoricalCertificationReplay(
        completed_session_reader=_reader(calls=calls),
        receipt_store=Task9HistoricalReplayReceiptStore(tmp_path / "historical"),
    ).replay(trading_date=DAY, cycle_boundary=BOUNDARY)

    assert first == second
    assert first["record_source"] == RECORD_SOURCE
    assert first["counting_status"] == "EXCLUDED_HISTORICAL_REPLAY"
    assert first["broker_order_submission"] is False
    assert first["live_execution_eligible"] is False
    assert first["markets"]["NIFTY"]["timeframes"]["5m"][0]["timestamp"] == "2026-08-10T09:15:00+05:30"
    assert calls == [("NIFTY", "NSE"), ("SENSEX", "BSE")]


@pytest.mark.parametrize("bad_day", (date(2026, 8, 9), date(2026, 1, 26)))
def test_weekend_and_holiday_are_rejected_before_reader(tmp_path, bad_day):
    calls = []
    with pytest.raises(Task9HistoricalReplayError, match="NON_TRADING_DATE"):
        _replay(tmp_path, calls=calls).replay(
            trading_date=bad_day,
            cycle_boundary=datetime.combine(bad_day, BOUNDARY.time(), IST),
        )
    assert calls == []


@pytest.mark.parametrize(("broken", "healthy"), (("NIFTY", "SENSEX"), ("SENSEX", "NIFTY")))
def test_one_market_failure_does_not_erase_the_other_market(tmp_path, broken, healthy):
    receipt = _replay(tmp_path, broken_market=broken).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"][broken]["status"] == "UNAVAILABLE"
    assert receipt["markets"][healthy]["status"] == "COMPLETED"


@pytest.mark.parametrize(
    ("action", "expected"),
    (("CALL", "UNEVALUABLE"), ("PUT", "UNEVALUABLE"), ("WAIT", "GOOD_WAIT"), ("NO_TRADE", "GOOD_WAIT")),
)
def test_replay_actions_use_later_same_session_candles_without_live_trade_state(tmp_path, action, expected):
    receipt = _replay(tmp_path, decision_engine=lambda _: {"action": action}).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"]["NIFTY"]["decision"]["action"] == action
    assert receipt["markets"]["NIFTY"]["outcome"]["status"] == expected
    if action in {"WAIT", "NO_TRADE"}:
        assert receipt["markets"]["NIFTY"]["outcome"]["authority"].endswith("evaluate_prediction_outcome")
    assert receipt["counting_status"] != "COUNTED_TRADE"


def test_replay_uses_typed_production_pre_entry_action_seam(tmp_path):
    def action_reader(evidence):
        return PreEntryMarketActionV1(
            action_id=f"action:{evidence['market_replay_id']}",
            underlying_symbol=evidence["market"], exchange=evidence["exchange"],
            cycle_id=evidence["market_replay_id"], observation_id=f"{evidence['market_replay_id']}:observation",
            candidate_id=None, action="WAIT", candidate_direction="NEUTRAL", candidate_eligibility="INELIGIBLE",
            confidence=0.0, score=0.0, regime_suitability=None, selected_for_parent_comparison=False,
            source_ledger_id=None, evaluated_at=BOUNDARY, reasons=("DIRECTION_NEUTRAL_NO_ENTRY",),
        )
    receipt = Task9HistoricalCertificationReplay(
        completed_session_reader=_reader(), receipt_store=Task9HistoricalReplayReceiptStore(tmp_path),
        production_action_reader=action_reader,
    ).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"]["NIFTY"]["decision"]["authority"].endswith("resolve_pre_entry_market_action")
    assert receipt["markets"]["NIFTY"]["decision"]["action"] == "WAIT"


def test_internal_decision_error_is_not_mislabeled_as_reader_failure(tmp_path):
    receipt = _replay(
        tmp_path,
        decision_engine=lambda _: (_ for _ in ()).throw(RuntimeError("bug")),
    ).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"]["NIFTY"]["reason"] == "HISTORICAL_REPLAY_INTERNAL_ERROR"
    assert receipt["markets"]["SENSEX"]["reason"] == "HISTORICAL_REPLAY_INTERNAL_ERROR"


def test_call_uses_only_explicit_production_lifecycle_adapter(tmp_path):
    receipt = Task9HistoricalCertificationReplay(
        completed_session_reader=_reader(), receipt_store=Task9HistoricalReplayReceiptStore(tmp_path),
        decision_engine=lambda _: {"action": "CALL"},
        production_lifecycle_evaluator=lambda **_: {
            "planner_authority": "services.trade_planning.selected_option_entry_stop_target_planner.plan_selected_option_entry_stop_targets",
            "terminal_authority": "services.paper_trading.paper_trade_position_evaluator.evaluate_open_paper_trade_position",
            "entry": 101.0, "stop": 95.0, "targets": (105.0, 110.0, 115.0), "terminal_outcome": "TARGET_1",
        },
    ).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    outcome = receipt["markets"]["NIFTY"]["outcome"]
    assert outcome["terminal_authority"].endswith("evaluate_open_paper_trade_position")
    assert outcome["terminal_outcome"] == "TARGET_1"


@pytest.mark.parametrize("mutator", ("missing", "incomplete", "future", "duplicate", "malformed"))
def test_bad_completed_session_candles_fail_closed_per_market(tmp_path, mutator):
    def read(**kwargs):
        value = _session_rows()
        if kwargs["market"] == "NIFTY":
            if mutator == "missing":
                value.pop("1h")
            elif mutator == "incomplete":
                value["5m"].pop()
            elif mutator == "future":
                value["5m"].append(_row(datetime(2026, 8, 10, 15, 30, tzinfo=IST)))
            elif mutator == "duplicate":
                value["5m"][1] = value["5m"][0]
            else:
                value["5m"][1] = ["bad", 1, 2, 1, 2, 1]
        return value
    receipt = Task9HistoricalCertificationReplay(completed_session_reader=read, receipt_store=Task9HistoricalReplayReceiptStore(tmp_path)).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["markets"]["NIFTY"]["status"] == "UNAVAILABLE"
    assert receipt["markets"]["SENSEX"]["status"] == "COMPLETED"


def test_corrupt_replay_cache_fails_closed_and_dashboard_failure_cannot_mutate_receipt(tmp_path):
    root = tmp_path / "historical"
    store = Task9HistoricalReplayReceiptStore(root)
    store.path.parent.mkdir(parents=True)
    store.path.write_text("not-json", encoding="utf-8")
    with pytest.raises(Task9HistoricalReplayError, match="CACHE_CORRUPT"):
        store.load("x")

    published = []
    receipt = Task9HistoricalCertificationReplay(
        completed_session_reader=_reader(),
        receipt_store=Task9HistoricalReplayReceiptStore(tmp_path / "good"),
        report_publisher=lambda _: (_ for _ in ()).throw(RuntimeError("dashboard")),
    ).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert published == []
    assert Task9HistoricalReplayReceiptStore(tmp_path / "good").load(receipt["replay_id"]) == receipt


def test_replay_root_never_mutates_live_root_portfolio_or_blocker(tmp_path):
    live_root = tmp_path / "official-live-task9"
    blocker = tmp_path / "blocker"
    portfolio = tmp_path / "portfolio"
    for root in (live_root, blocker, portfolio):
        root.mkdir()
        (root / "sentinel.json").write_text('{"unchanged":true}', encoding="utf-8")
    receipt = _replay(tmp_path).replay(trading_date=DAY, cycle_boundary=BOUNDARY)
    assert receipt["execution_mode"] == "PAPER"
    for root in (live_root, blocker, portfolio):
        assert (root / "sentinel.json").read_text(encoding="utf-8") == '{"unchanged":true}'


def test_historical_replay_source_is_rejected_by_live_counting_input():
    prediction = PredictionRecordV1(
        prediction_id="replay-prediction", parent_cycle_id="replay-cycle", decision_result_id="replay-decision", child_result_id="replay-child", observation_id="replay-observation",
        underlying_symbol="NIFTY", exchange="NSE", requested_at=BOUNDARY, completed_at=BOUNDARY, market_timestamp=BOUNDARY, received_at=BOUNDARY,
        start_underlying_price=100.0, terminal_status="COMPLETED", candidate_id=None, predicted_direction="UNAVAILABLE", predicted_action="NO_TRADE",
        eligibility="UNAVAILABLE", confidence=0.0, score=0.0, rank_value=0.0, eligible_for_comparison=False, outcome_reason="INELIGIBLE", parent_decision="NO_TRADE", parent_selected=False,
    )
    with pytest.raises(ValueError, match="record_source"):
        Task9LivePaperTradeCountingInputV1(
            prediction=prediction, lifecycle_outcome=None, reconciliation=None, record_source="HISTORICAL_REPLAY",
            session_status="OUT_OF_SESSION", evidence_status="VALID", official_run_id="official", record_run_id="historical",
            official_start_at=BOUNDARY, evaluated_at=BOUNDARY,
        )
