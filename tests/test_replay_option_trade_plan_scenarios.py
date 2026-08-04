from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from services.contracts.option_contract_universe_v1 import OptionContractUniverseV1
from services.contracts.option_contract_v1 import OptionContractV1
from services.options.pipeline import create_canonical_trade_plan
from services.options.policies import TradePlanPolicy


NOW = datetime(2026, 7, 27, 10, tzinfo=timezone.utc)


@dataclass
class Snapshot:
    snapshot_id: str = "snapshot-1"


@dataclass
class Analysis:
    analysis_id: str = "analysis-1"


@dataclass
class Decision:
    action: str = "BUY"
    authorization_status: str = "ANALYSIS_ONLY"
    snapshot_id: str = "snapshot-1"
    decision_id: str = "decision-1"
    symbol: str = "NIFTY"
    exchange: str = "NSE"

    def to_dict(self):
        return dict(self.__dict__)


def _universe(*, symbol="NIFTY", exchange="NSE", option_type="CALL", strikes=(25000.0,), captured_at=NOW):
    contracts = tuple(OptionContractV1(f"contract-{strike}", symbol, exchange, f"{symbol}{strike}{option_type}", option_type, strike, date(2026, 7, 30), 50, captured_at, last_price=100.0) for strike in strikes)
    return OptionContractUniverseV1("universe-1", symbol, exchange, captured_at, 25000.0, contracts, "synthetic", True)


def _run(*, decision=None, universe=None, emitter=None, **kwargs):
    return create_canonical_trade_plan(snapshot=Snapshot(), analysis=Analysis(), decision=decision or Decision(), universe=universe or _universe(), clock=lambda: NOW, selection_id_factory=lambda: "selection-id", trade_plan_id_factory=lambda: "plan-id", result_id_factory=lambda: "result-id", audit_emitter=emitter, **kwargs)


def test_nifty_buy_call_semantics_are_deterministic():
    assert _run().semantic_dict() == _run().semantic_dict()


def test_nifty_sell_selects_put():
    assert _run(decision=Decision(action="SELL"), universe=_universe(option_type="PUT")).selected_contract.option_type == "PUT"


def test_sensex_buy_selects_call():
    result = _run(decision=Decision(symbol="SENSEX", exchange="BSE"), universe=_universe(symbol="SENSEX", exchange="BSE"))
    assert result.selected_contract.option_type == "CALL"


def test_sensex_sell_selects_put():
    result = _run(decision=Decision(action="SELL", symbol="SENSEX", exchange="BSE"), universe=_universe(symbol="SENSEX", exchange="BSE", option_type="PUT"))
    assert result.selected_contract.option_type == "PUT"


def test_atm_selection_is_deterministic():
    result = _run(universe=_universe(strikes=(24900.0, 25000.0, 25100.0)))
    assert result.selected_contract.strike == 25000.0


def test_expiry_selection_is_deterministic():
    earlier = OptionContractV1("early", "NIFTY", "NSE", "EARLY", "CALL", 25000, date(2026, 7, 29), 50, NOW, last_price=100)
    later = OptionContractV1("late", "NIFTY", "NSE", "LATE", "CALL", 25000, date(2026, 7, 30), 50, NOW, last_price=100)
    result = _run(universe=OptionContractUniverseV1("u", "NIFTY", "NSE", NOW, 25000, (later, earlier), "synthetic", True))
    assert result.selected_contract.expiry_date == date(2026, 7, 29)


def test_wait_is_no_action():
    assert _run(decision=Decision(action="WAIT")).result_status == "NO_ACTION"


def test_blocked_decision_is_blocked():
    assert _run(decision=Decision(authorization_status="BLOCKED")).result_status == "BLOCKED"


def test_stale_universe_is_blocked():
    assert _run(universe=_universe(captured_at=NOW - timedelta(minutes=10))).result_status == "BLOCKED"


def test_missing_matching_option_type_is_blocked():
    assert _run(universe=_universe(option_type="PUT")).result_status == "BLOCKED"


def test_missing_entry_is_insufficient_data():
    contract = OptionContractV1("no-price", "NIFTY", "NSE", "NOPRICE", "CALL", 25000, date(2026, 7, 30), 50, NOW)
    universe = OptionContractUniverseV1("u", "NIFTY", "NSE", NOW, 25000, (contract,), "synthetic", True)
    assert _run(universe=universe, trade_plan_policy=TradePlanPolicy(require_entry_reference_price=True)).result_status == "INSUFFICIENT_DATA"


def test_session_blocked_is_blocked():
    session = type("Session", (), {"analysis_allowed": False, "blockers": ("session blocked",)})()
    assert _run(session_validation=session).result_status == "BLOCKED"


def test_generated_selection_id_is_excluded_from_semantics():
    result = _run()
    assert "selection_id" not in result.selected_contract.semantic_dict()


def test_generated_plan_id_is_excluded_from_semantics():
    assert "trade_plan_id" not in _run().trade_plan.semantic_dict()


def test_generated_result_id_is_excluded_from_semantics():
    assert "result_id" not in _run().semantic_dict()


def test_generated_timestamps_are_excluded_from_semantics():
    semantic = _run().semantic_dict()
    assert "created_at" not in semantic and "selected_at" not in _run().selected_contract.semantic_dict()


def test_pipeline_does_not_write_files(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("write attempted")))
    assert _run().result_status == "PLAN_CREATED"


def test_pipeline_does_not_import_provider_modules():
    before = set(sys.modules); _run()
    assert not {name for name in set(sys.modules) - before if "provider" in name.lower()}


def test_pipeline_does_not_import_broker_modules():
    before = set(sys.modules); _run()
    assert not {name for name in set(sys.modules) - before if "broker" in name.lower()}


def test_pipeline_does_not_import_database_modules():
    before = set(sys.modules); _run()
    assert not {name for name in set(sys.modules) - before if "database" in name.lower()}


def test_selection_and_plan_audit_events_are_emitted():
    events = []
    _run(emitter=events.append)
    assert [event.event_type for event in events] == ["OPTION_SELECTION_STARTED", "OPTION_SELECTION_COMPLETED", "TRADE_PLAN_STARTED", "TRADE_PLAN_COMPLETED"]


def test_blocked_selection_audit_event_is_emitted():
    events = []
    _run(universe=_universe(option_type="PUT"), emitter=events.append)
    assert events[-1].event_type == "OPTION_SELECTION_BLOCKED"


def test_fail_open_audit_error_preserves_output():
    baseline = _run().semantic_dict()
    assert _run(emitter=lambda event: (_ for _ in ()).throw(RuntimeError("sink failed"))).semantic_dict() == baseline


def test_audit_payload_excludes_full_universe_snapshot_and_decision():
    events = []
    _run(emitter=events.append)
    payload = events[-1].to_dict()
    assert "universe" not in payload["attributes"] and "snapshot" not in payload["attributes"] and "decision" not in payload["attributes"]


def test_audit_payload_contains_only_bounded_selection_fields():
    events = []
    _run(emitter=events.append)
    assert set(events[-1].attributes) <= {"option_type", "expiry_date", "strike", "lot_size", "expiry_policy", "strike_policy", "reference_price_source", "plan_status", "blocker_count", "warning_count"}
