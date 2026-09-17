# Option Contract and Trade-Plan Pipeline

The P3-4 pipeline selects only from caller-supplied contracts after a directional decision. It performs no expiry-weekday inference, provider access, risk sizing, broker submission, or live execution.

Its optional audit emitter records bounded start, completion, blocked, and
unexpected-failure events for option selection and trade-plan construction. Audit
failures are fail-open and cannot change the canonical result.
