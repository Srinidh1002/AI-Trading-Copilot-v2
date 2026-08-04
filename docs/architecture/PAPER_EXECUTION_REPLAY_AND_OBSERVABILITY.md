# Paper execution replay and observability

P4-6 adds immutable, process-local observations and deterministic read-only
replay for already-recorded canonical paper-execution evidence. Public APIs:
`PaperExecutionObservationV1`, `PaperExecutionReplayResultV1`,
`InMemoryPaperExecutionObservationRepository`,
`build_paper_execution_observations`, and `replay_canonical_paper_execution`.

Observations follow the fixed order RISK, CANDIDATE, REQUEST, AUTHORIZATION,
EXECUTION, ORDER_STATE, PIPELINE_RESULT. Outcomes are bounded; stored values
are ordered by `(observed_at, observation_id)` and protected by an `RLock`.
Identity is an exact stored four-index pair, never inferred from trading
symbols.

Replay compares recorded semantic linkage, identity, direction, quantity,
lots, statuses, and fill evidence against a canonical execution result. It
reports MATCHED, MISMATCHED, INCOMPLETE, NOT_REPLAYABLE, or FAILED with sorted
mismatch fields. Generated observation IDs/times are non-semantic.

Neither builder nor replay executes, validates, authorizes, saves, mutates,
claims idempotency, or creates an order/fill. There is no persistence,
background worker, provider, broker, filesystem, network, or live execution.
P4-7 retains final certification responsibility; persistent event storage is
explicitly out of scope.
