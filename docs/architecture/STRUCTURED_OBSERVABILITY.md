# Structured Observability

Observability is dependency injected and defaults to no-op. `FAIL_OPEN` preserves canonical/replay behavior when a sink fails; explicitly requested `FAIL_CLOSED` raises before a caller continues. Sinks are no-op, ordered in-memory, and explicit append-only JSONL. No default sink writes files, calls telemetry, or imports provider/broker/Streamlit/database code.

Canonical and replay hooks emit IDs, status, and counts only. They never include raw candles, option chains, credentials, or external request payloads.
