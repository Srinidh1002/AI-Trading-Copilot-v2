from __future__ import annotations
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from uuid import uuid4
from services.contracts.audit_event_v1 import AuditEventV1
from .context import AuditContext
from .redaction import sanitize_audit_value

def create_audit_event(event_type: str, *, component: str, operation: str, outcome: str, severity: str = "INFO", context: AuditContext | None = None, attributes: Mapping[str, object] | None = None, warnings: Iterable[str] = (), errors: Iterable[str] = (), id_factory: Callable[[], str] | None = None, clock: Callable[[], datetime] | None = None, **fields: object) -> AuditEventV1:
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    return AuditEventV1(event_id=(id_factory or (lambda: str(uuid4())))(), event_type=event_type, event_name=event_type.casefold(), occurred_at=now, severity=severity, outcome=outcome, component=component, operation=operation, trace_id=context.trace_id if context else None, correlation_id=context.correlation_id if context else fields.pop("correlation_id", None), parent_event_id=context.parent_event_id if context else None, attributes=sanitize_audit_value(attributes or {}), warnings=tuple(sorted(str(value) for value in warnings)), errors=tuple(sorted(str(value) for value in errors)), **fields)
