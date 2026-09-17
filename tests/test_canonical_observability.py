from services.observability import AuditEmitter, InMemoryAuditSink
def test_canonical_observability_is_injected_and_noop_by_default():
    sink=InMemoryAuditSink(); emitter=AuditEmitter(sink); assert sink.events == () and emitter.failure_mode == "FAIL_OPEN"
