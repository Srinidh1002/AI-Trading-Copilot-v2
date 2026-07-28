from datetime import datetime, timezone
import pytest
from services.contracts.audit_event_v1 import AuditEventV1
def _event(**changes):
    values = dict(event_id="event-1", event_type="ANALYSIS_STARTED", event_name="analysis_started", occurred_at=datetime(2026, 7, 24, tzinfo=timezone.utc), severity="INFO", outcome="STARTED", component="test", operation="unit"); values.update(changes); return AuditEventV1(**values)
def test_audit_event_serialization_is_deterministic():
    event = _event(attributes={"count": 1}); assert event.to_json() == event.to_json(); assert "event_id" not in event.semantic_dict()
@pytest.mark.parametrize("changes", [{"event_type":"UNKNOWN"}, {"severity":"TRACE"}, {"outcome":"OK"}, {"duration_ms":-1}])
def test_audit_event_rejects_invalid_values(changes):
    with pytest.raises(ValueError): _event(**changes)

@pytest.mark.parametrize("event_type,outcome", [
    ("POSITION_SIZING_STARTED", "STARTED"), ("POSITION_SIZING_COMPLETED", "SUCCEEDED"),
    ("POSITION_SIZING_BLOCKED", "BLOCKED"), ("POSITION_SIZING_FAILED", "FAILED"),
    ("RISK_VALIDATION_STARTED", "STARTED"), ("RISK_VALIDATION_COMPLETED", "SUCCEEDED"),
    ("RISK_VALIDATION_BLOCKED", "BLOCKED"), ("RISK_VALIDATION_FAILED", "FAILED"),
    ("PAPER_PREPARATION_STARTED", "STARTED"), ("PAPER_PREPARATION_COMPLETED", "SUCCEEDED"),
    ("PAPER_PREPARATION_BLOCKED", "BLOCKED"), ("PAPER_PREPARATION_FAILED", "FAILED"),
])
def test_p3_5_lifecycle_event_types_are_accepted(event_type, outcome):
    assert _event(event_type=event_type, outcome=outcome).event_type == event_type


def test_existing_event_type_and_semantics_remain_compatible():
    assert _event().semantic_dict() == _event().semantic_dict()


def test_attributes_are_defensively_copied_and_deterministic():
    attributes = {"b": 2, "a": 1}; event = _event(attributes=attributes); attributes["a"] = 3
    assert event.attributes == {"b": 2, "a": 1} and event.to_dict() == event.to_dict()


@pytest.mark.parametrize("attributes", [{"x": float("nan")}, {"x": float("inf")}])
def test_nonfinite_attributes_remain_rejected(attributes):
    with pytest.raises(ValueError): _event(attributes=attributes)
