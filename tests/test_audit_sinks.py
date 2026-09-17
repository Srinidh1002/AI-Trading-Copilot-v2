from datetime import datetime, timezone
from services.observability import InMemoryAuditSink, JsonLinesAuditSink, NoOpAuditSink, create_audit_event
def _event(): return create_audit_event("ANALYSIS_STARTED",component="test",operation="sink",outcome="STARTED",id_factory=lambda:"event",clock=lambda:datetime(2026,7,24,tzinfo=timezone.utc))
def test_sinks_are_ordered_and_explicit(tmp_path):
    memory=InMemoryAuditSink(); memory.emit(_event()); memory.emit(_event()); assert len(memory.events)==2
    path=tmp_path / "audit.jsonl"; JsonLinesAuditSink(path).emit(_event()); assert path.read_text(encoding="utf-8").count("\n")==1
    memory.clear(); assert memory.events == (); NoOpAuditSink().emit(_event())
