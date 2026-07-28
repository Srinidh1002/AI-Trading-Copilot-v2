from services.observability import AuditContext, create_audit_event
def test_audit_context_keeps_explicit_correlation():
    event=create_audit_event("REPLAY_STARTED",component="replay",operation="fixture",outcome="STARTED",context=AuditContext("trace","correlation")); assert event.trace_id == "trace" and event.correlation_id == "correlation"
