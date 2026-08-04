from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1


NOW = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)


def make(**changes):
    values = dict(
        scheduled_market_event_id="event-1",
        created_at=NOW,
        event_name="India CPI Release",
        event_category="CPI",
        scheduled_start=NOW + timedelta(days=1),
        scheduled_end=None,
        source_id="CALENDAR_FIXTURE",
        source_timestamp=NOW,
        confirmation_state="CONFIRMED",
        event_status="UPCOMING",
        severity="MODERATE",
        affected_market_identities=(),
        affected_exchanges=(),
        analysis_allowed=True,
        new_entries_allowed=True,
        session_override_state="NONE",
    )
    values.update(changes)
    return ScheduledMarketEventV1(**values)


def test_contract_is_frozen_and_serializes_deterministically():
    event = make(metadata={"source": {"kind": "fixture"}})
    with pytest.raises(FrozenInstanceError):
        event.event_name = "changed"
    with pytest.raises(TypeError):
        event.metadata["source"] = "changed"
    with pytest.raises(TypeError):
        event.metadata["source"]["kind"] = "changed"
    assert event.to_json() == event.to_json()
    assert "scheduled_market_event_id" not in event.semantic_dict()
    assert "created_at" not in event.semantic_dict()


@pytest.mark.parametrize("name", ("created_at", "scheduled_start", "source_timestamp"))
def test_required_timestamps_must_be_aware(name):
    with pytest.raises(ValueError):
        make(**{name: NOW.replace(tzinfo=None)})


def test_end_must_be_aware_and_not_before_start():
    with pytest.raises(ValueError):
        make(scheduled_end=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        make(scheduled_end=NOW)
    assert make(scheduled_end=NOW + timedelta(days=1))


def test_past_completed_event_and_source_order_are_valid():
    assert make(
        event_status="COMPLETED",
        scheduled_start=NOW - timedelta(days=2),
        source_timestamp=NOW + timedelta(days=1),
    )


@pytest.mark.parametrize("state", ("CONFIRMED", "TENTATIVE", "UNAVAILABLE"))
def test_confirmation_states(state):
    changes = {"confirmation_state": state}
    if state == "TENTATIVE":
        changes["warnings"] = ("Calendar publication is tentative",)
    if state == "UNAVAILABLE":
        changes.update(event_status="UNAVAILABLE", warnings=("Calendar unavailable",))
    assert make(**changes)


def test_confirmation_and_status_consistency():
    with pytest.raises(ValueError):
        make(confirmation_state="TENTATIVE")
    with pytest.raises(ValueError):
        make(confirmation_state="UNAVAILABLE", event_status="UPCOMING", warnings=("unknown",))
    with pytest.raises(ValueError):
        make(event_status="POSTPONED")
    with pytest.raises(ValueError):
        make(event_status="BLOCKED")
    assert make(event_status="BLOCKED", blockers=("calendar conflict",), new_entries_allowed=False)


def test_flags_and_completed_or_cancelled_restrictions_need_explicit_blocker():
    assert make(new_entries_allowed=False)
    assert make(analysis_allowed=False, new_entries_allowed=False)
    with pytest.raises(ValueError):
        make(analysis_allowed=False, new_entries_allowed=True)
    with pytest.raises(ValueError):
        make(event_status="CANCELLED", new_entries_allowed=False)
    assert make(event_status="CANCELLED", blockers=("separate restriction",), new_entries_allowed=False)


def test_text_metadata_and_execution_safety():
    for changes in (
        {"scheduled_market_event_id": " "}, {"event_name": " "}, {"source_id": " "},
        {"event_name": "<b>CPI</b>"}, {"execution_mode": "LIVE"},
        {"live_execution_eligible": True}, {"metadata": {"value": float("nan")}},
    ):
        with pytest.raises(ValueError):
            make(**changes)


def test_identity_exchange_applicability_is_canonical_unique_and_ordered():
    event = make(
        affected_market_identities=(("BANKNIFTY", "NSE"), ("SENSEX", "BSE")),
        affected_exchanges=("BSE", "NSE"),
    )
    assert event.affected_market_identities == (("BANKNIFTY", "NSE"), ("SENSEX", "BSE"))
    for changes in (
        {"affected_market_identities": (("NIFTY", "BSE"),)},
        {"affected_market_identities": (("NIFTY", "NSE"), ("NIFTY", "NSE")), "affected_exchanges": ("NSE",)},
        {"affected_market_identities": (("NIFTY", "NSE"),), "affected_exchanges": ()},
        {"affected_exchanges": ("NSE", "NSE")},
    ):
        with pytest.raises(ValueError):
            make(**changes)


@pytest.mark.parametrize("severity", ("LOW", "MODERATE", "HIGH", "EXTREME", "UNAVAILABLE"))
def test_all_controlled_severities_are_supported_without_policy_behavior(severity):
    assert make(severity=severity)


@pytest.mark.parametrize(
    "identity",
    (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE")),
)
def test_each_supported_identity_can_be_explicitly_applicable(identity):
    assert make(affected_market_identities=(identity,), affected_exchanges=(identity[1],))
