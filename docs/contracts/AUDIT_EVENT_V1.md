# Audit Event v1

`AuditEventV1` is an immutable structured diagnostic event with controlled taxonomy, aware timestamps, finite values, deterministic serialization, and semantic serialization that excludes generated event identity/time. It carries explicit correlation plus snapshot, analysis, decision, candidate, replay, fixture, and suite identities.

Attributes are redacted and bounded before construction. Credentials, tokens, cookies, tracebacks, full market payloads, environment dumps, and executable content are excluded.

P3-5 adds controlled lifecycle event types for position sizing, risk validation,
and paper preparation. The event payload schema remains unchanged.
