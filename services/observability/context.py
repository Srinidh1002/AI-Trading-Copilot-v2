from dataclasses import dataclass
from uuid import uuid4

@dataclass(frozen=True, slots=True)
class AuditContext:
    trace_id: str
    correlation_id: str
    parent_event_id: str | None = None

    @classmethod
    def create(cls, correlation_id: str | None = None) -> "AuditContext":
        value = correlation_id or str(uuid4())
        return cls(trace_id=value, correlation_id=value)

    def child(self, parent_event_id: str) -> "AuditContext":
        return AuditContext(self.trace_id, self.correlation_id, parent_event_id)
