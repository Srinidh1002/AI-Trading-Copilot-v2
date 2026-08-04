import pytest
from services.observability import AuditEmitter, AuditEmissionError, create_audit_event
class BrokenSink:
    def emit(self,event): raise OSError("no write")
def test_emitter_failure_modes_are_explicit():
    event=create_audit_event("ANALYSIS_STARTED",component="test",operation="emit",outcome="STARTED")
    assert AuditEmitter(BrokenSink()).emit(event).emitted is False
    with pytest.raises(AuditEmissionError): AuditEmitter(BrokenSink(),failure_mode="FAIL_CLOSED").emit(event)
