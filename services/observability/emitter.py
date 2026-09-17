from dataclasses import dataclass
from .sinks import AuditSink, NoOpAuditSink

class AuditEmissionError(RuntimeError): pass
@dataclass(frozen=True, slots=True)
class AuditEmitResult:
    emitted: bool; failure_mode: str; error_type: str | None = None; error_message: str | None = None
class AuditEmitter:
    def __init__(self, sink: AuditSink | None = None, *, failure_mode: str = "FAIL_OPEN") -> None:
        if failure_mode not in {"FAIL_OPEN", "FAIL_CLOSED"}: raise ValueError("Unsupported audit failure mode.")
        self.sink, self.failure_mode = sink or NoOpAuditSink(), failure_mode
    def emit(self, event):
        try: self.sink.emit(event); return AuditEmitResult(True, self.failure_mode)
        except Exception as exc:
            result = AuditEmitResult(False, self.failure_mode, type(exc).__name__, "Audit sink emission failed.")
            if self.failure_mode == "FAIL_CLOSED": raise AuditEmissionError(result.error_message) from exc
            return result
