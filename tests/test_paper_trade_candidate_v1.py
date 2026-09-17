from datetime import datetime, timedelta

import pytest

from services.contracts.paper_trade_candidate_v1 import (
    PaperCandidateValidationError,
    PaperTradeCandidateV1,
)


def _candidate(**overrides):
    now = datetime.fromisoformat("2026-07-10T10:00:00+05:30")
    values = {
        "snapshot_id": "snapshot-1", "decision_id": "decision-1",
        "symbol": "NIFTY", "exchange": "NSE", "action": "BUY",
        "option_type": "CE", "tradingsymbol": "NIFTYCE", "instrument_token": None,
        "entry": 100, "stop_loss": 90, "targets": (110, 120), "quantity": 50,
        "created_at": now, "expires_at": now + timedelta(minutes=5),
        "authorization_status": "PAPER_READY", "execution_status": "NOT_REQUESTED",
    }
    values.update(overrides)
    return PaperTradeCandidateV1(**values)


def test_candidate_serialization_is_deterministic():
    candidate = _candidate()
    assert candidate.to_json() == candidate.to_json()


def test_candidate_rejects_missing_instrument_identity():
    with pytest.raises(PaperCandidateValidationError):
        _candidate(tradingsymbol=None, instrument_token=None)


def test_single_positive_target_above_entry_is_accepted():
    candidate = _candidate(targets=(110,))
    assert candidate.targets == (110.0,)


@pytest.mark.parametrize("targets", [(), (100,), (99,), (110, 110), (120, 110), (110, float("nan")), (110, float("inf")), (0,), (-1,)])
def test_invalid_target_collections_are_rejected(targets):
    with pytest.raises(PaperCandidateValidationError):
        _candidate(targets=targets)


def test_two_and_three_increasing_targets_remain_valid():
    assert _candidate(targets=(110, 120)).targets == (110.0, 120.0)
    assert _candidate(targets=(110, 120, 130)).targets == (110.0, 120.0, 130.0)


def test_single_target_serializes_without_fabrication():
    payload = _candidate(targets=(110,)).to_dict()
    assert payload["targets"] == [110.0]


def test_single_target_semantics_and_json_are_deterministic():
    candidate = _candidate(targets=(110,))
    assert candidate.to_json() == candidate.to_json()


def test_targets_remain_an_immutable_tuple():
    assert isinstance(_candidate(targets=[110]).targets, tuple)


def test_existing_legacy_two_target_fixture_remains_valid():
    assert _candidate().targets == (110.0, 120.0)


def test_candidate_execution_fields_are_not_widened_by_single_target():
    candidate = _candidate(targets=(110,))
    assert candidate.approved is False and candidate.approval_required is True


def test_explicit_long_buy_call_and_legacy_buy_are_valid():
    assert _candidate(position_side="LONG").position_side == "LONG"
    assert _candidate().position_side == "LONG"


def test_long_sell_put_accepts_single_and_multiple_targets():
    single = _candidate(action="SELL", option_type="PE", position_side="LONG", stop_loss=90, targets=(110,))
    multiple = _candidate(action="SELL", option_type="PE", position_side="LONG", stop_loss=90, targets=(110, 120))
    assert single.position_side == multiple.position_side == "LONG"


@pytest.mark.parametrize("stop,targets", [(100, (110,)), (110, (110,)), (90, (100,)), (90, (99,))])
def test_long_sell_put_rejects_invalid_stop_or_target_direction(stop, targets):
    with pytest.raises(PaperCandidateValidationError):
        _candidate(action="SELL", option_type="PE", position_side="LONG", stop_loss=stop, targets=targets)


@pytest.mark.parametrize("position_side", ["SHORT", "UNKNOWN", ""])
def test_invalid_buy_position_side_is_rejected(position_side):
    with pytest.raises(PaperCandidateValidationError): _candidate(position_side=position_side)


def test_sell_long_call_is_rejected():
    with pytest.raises(PaperCandidateValidationError): _candidate(action="SELL", option_type="CE", position_side="LONG", stop_loss=90, targets=(110,))


def test_legacy_and_explicit_short_sell_remain_valid():
    values = dict(action="SELL", option_type="PE", stop_loss=110, targets=(90,))
    assert _candidate(**values).position_side == "SHORT"
    assert _candidate(**values, position_side="SHORT").position_side == "SHORT"


def test_position_side_serializes_and_is_semantically_stable():
    candidate = _candidate(position_side="LONG", targets=(110,))
    assert candidate.to_dict()["position_side"] == "LONG" and candidate.semantic_dict()["position_side"] == "LONG"
