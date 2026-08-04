"""Deterministic, PAPER-only replay certification for the P6E boundary."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from services.contracts import EntryZoneEvaluationInputV1, EntryZoneEvaluationResultV1
from services.trade_planning.entry_zone_evaluator import evaluate_entry_zone
from tests.test_trade_planning_policy_v1 import _p


EVALUATED_AT = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
QUOTE_AT = datetime(2026, 1, 2, 9, 14, tzinfo=timezone.utc)
SOURCE_AT = datetime(2026, 1, 2, 9, 13, tzinfo=timezone.utc)


def _input(case_id: str, symbol: str, direction: str, method: str, **overrides: object) -> EntryZoneEvaluationInputV1:
    exchange = "BSE" if symbol == "SENSEX" else "NSE"
    values: dict[str, object] = {
        "evaluation_id": f"p6e-replay-{case_id}", "evaluation_result_id": f"p6e-result-{case_id}",
        "evaluated_at": EVALUATED_AT, "underlying_symbol": symbol, "exchange": exchange,
        "trade_plan_input_id": f"plan-{case_id}", "policy_id": "P", "direction": direction,
        "option_right": "CALL" if direction == "BULLISH" else "PUT", "entry_reference_method": method,
        "last_traded_price": 100.0, "bid_price": 99.0, "ask_price": 101.0,
        "signal_reference_price": 100.0, "option_mid_price": 100.0, "option_quote_timestamp": QUOTE_AT,
        "maximum_entry_premium": None, "maximum_spread_fraction": None, "planning_allowed": True,
        "blockers": (), "warnings": (), "source_timestamps": {"analysis": SOURCE_AT, "quote": QUOTE_AT},
        "metadata": {"nested": {"case": case_id}, "labels": ["replay", symbol]},
        "execution_mode": "PAPER", "live_execution_eligible": False, "schema_version": "1.0",
    }
    values.update(overrides)
    return EntryZoneEvaluationInputV1(**values)


CASES = (
    ("mid-ready", "NIFTY", "BULLISH", "OPTION_MID", {}, {}, "READY", "OPTION_MID", ()),
    ("ask-ready", "BANKNIFTY", "BEARISH", "OPTION_ASK", {}, {}, "READY", "OPTION_ASK", ()),
    ("ltp-ready", "FINNIFTY", "BULLISH", "LAST_TRADED_PRICE", {}, {}, "READY", "LAST_TRADED_PRICE", ()),
    ("signal-ready", "SENSEX", "BEARISH", "SIGNAL_REFERENCE", {}, {}, "READY", "SIGNAL_REFERENCE", ()),
    ("hybrid-fallback", "NIFTY", "BULLISH", "HYBRID", {"option_mid_price": None}, {}, "READY", "OPTION_ASK", ()),
    ("planning", "BANKNIFTY", "BULLISH", "OPTION_MID", {"planning_allowed": False}, {}, "BLOCKED", None, ("ENTRY_PLANNING_NOT_ALLOWED",)),
    ("input", "FINNIFTY", "BEARISH", "OPTION_MID", {"blockers": ("INPUT_BLOCK",)}, {}, "BLOCKED", None, ("INPUT_BLOCK",)),
    ("mismatch", "SENSEX", "BULLISH", "OPTION_MID", {"policy_id": "other"}, {}, "BLOCKED", None, ("ENTRY_POLICY_MISMATCH",)),
    ("missing", "NIFTY", "BEARISH", "OPTION_MID", {"option_mid_price": None}, {}, "BLOCKED", None, ("ENTRY_REFERENCE_UNAVAILABLE",)),
    ("premium", "BANKNIFTY", "BULLISH", "OPTION_MID", {"maximum_entry_premium": 100.0}, {}, "BLOCKED", "OPTION_MID", ("ENTRY_PREMIUM_LIMIT_EXCEEDED",)),
    ("spread", "FINNIFTY", "BEARISH", "OPTION_MID", {"maximum_spread_fraction": 0.01}, {}, "BLOCKED", "OPTION_MID", ("ENTRY_SPREAD_LIMIT_EXCEEDED",)),
    ("both", "SENSEX", "BULLISH", "OPTION_MID", {"maximum_entry_premium": 100.0, "maximum_spread_fraction": 0.01}, {}, "BLOCKED", "OPTION_MID", ("ENTRY_PREMIUM_LIMIT_EXCEEDED", "ENTRY_SPREAD_LIMIT_EXCEEDED")),
)


@pytest.mark.parametrize("case_id,symbol,direction,method,input_overrides,policy_overrides,status,source,blockers", CASES)
def test_p6e_replay_matrix(case_id, symbol, direction, method, input_overrides, policy_overrides, status, source, blockers) -> None:
    evaluation_input = _input(case_id, symbol, direction, method, **input_overrides)
    policy = _p(entry_reference_method=method, **policy_overrides)
    input_before, policy_before = evaluation_input.to_json(), policy.to_json()
    first, second = evaluate_entry_zone(evaluation_input, policy), evaluate_entry_zone(evaluation_input, policy)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert first.to_json() == second.to_json()
    assert first.semantic_dict() == second.semantic_dict()
    assert (first.status, first.selected_reference_source, first.blockers) == (status, source, blockers)
    assert first.evaluation_result_id == evaluation_input.evaluation_result_id
    assert first.evaluated_at == EVALUATED_AT
    assert dict(first.source_timestamps) == dict(evaluation_input.source_timestamps)
    assert evaluation_input.to_json() == input_before and policy.to_json() == policy_before
    assert (first.execution_mode, first.live_execution_eligible) == ("PAPER", False)
    assert first.status in {"READY", "BLOCKED"}
    if method == "HYBRID":
        assert first.warnings.count("ENTRY_HYBRID_FALLBACK_USED") == 1
    if source is None:
        assert first.entry_zone_lower is first.entry_zone_upper is first.maximum_chase_price is None
    else:
        assert first.entry_zone_lower == first.entry_reference_price * (1 - policy.entry_tolerance_below_fraction)
        assert first.entry_zone_upper == first.entry_reference_price * (1 + policy.entry_tolerance_above_fraction)
        assert first.maximum_chase_price == first.entry_reference_price * (1 + policy.maximum_chase_fraction)
        assert first.entry_tolerance_fraction == max(policy.entry_tolerance_below_fraction, policy.entry_tolerance_above_fraction)


def test_serialization_is_detached_and_semantic_exclusions_are_exact() -> None:
    evaluation_input = _input("serialization", "NIFTY", "BULLISH", "OPTION_MID")
    result = evaluate_entry_zone(evaluation_input, _p())
    for value, excluded in ((evaluation_input, {"evaluation_id", "evaluation_result_id", "evaluated_at", "source_timestamps"}), (result, {"evaluation_result_id", "evaluation_id", "evaluated_at", "source_timestamps"})):
        serialized = value.to_dict()
        metadata = serialized["metadata"]
        if "input_metadata" in metadata:
            metadata = metadata["input_metadata"]
        metadata["nested"]["case"] = "mutated"
        serialized["source_timestamps"]["quote"] = "mutated"
        typed_metadata = value.to_dict()["metadata"]
        if "input_metadata" in typed_metadata:
            typed_metadata = typed_metadata["input_metadata"]
        assert typed_metadata["nested"]["case"] == "serialization"
        assert value.to_dict()["source_timestamps"]["quote"] == QUOTE_AT.isoformat()
        assert set(value.to_dict()) - set(value.semantic_dict()) == excluded
        assert value.to_json() == value.to_json()
    assert result.zone_width == 2.0
    assert result.lower_distance_fraction == result.upper_distance_fraction == 0.01


def test_formula_limits_and_spread_basis_are_exact() -> None:
    premium = evaluate_entry_zone(_input("cap", "NIFTY", "BULLISH", "OPTION_MID", maximum_entry_premium=120.0), _p(maximum_entry_premium=110.0))
    assert premium.maximum_entry_premium == 110.0 and premium.status == "READY"
    fallback_spread = evaluate_entry_zone(_input("basis", "NIFTY", "BULLISH", "OPTION_ASK", option_mid_price=None), _p(entry_reference_method="OPTION_ASK", maximum_spread_fraction=0.1))
    assert fallback_spread.effective_spread_fraction == 2 / 101
    absent_spread = evaluate_entry_zone(_input("absent", "NIFTY", "BULLISH", "OPTION_MID", bid_price=None, ask_price=None), _p())
    assert absent_spread.effective_spread_fraction is None


def test_fresh_import_is_side_effect_free_and_dependency_sources_are_clean() -> None:
    code = "from services.contracts import EntryZoneEvaluationInputV1, EntryZoneEvaluationResultV1, TradePlanningPolicyV1; from services.trade_planning.entry_zone_evaluator import evaluate_entry_zone; print('ok')"
    completed = subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)
    assert completed.stdout.strip() == "ok"
    source = Path("services/trade_planning/entry_zone_evaluator.py").read_text(encoding="utf-8")
    banned = ("services.providers", "services.broker", "paper_executor", "order_manager", "portfolio", "database", "streamlit", "pandas", "numpy", "scipy", "yfinance", "SmartApi", "random", "uuid", "datetime.now", "utcnow", "date.today", "time.time")
    assert not any(token in source for token in banned)
    assert EntryZoneEvaluationResultV1.__name__ == "EntryZoneEvaluationResultV1"
