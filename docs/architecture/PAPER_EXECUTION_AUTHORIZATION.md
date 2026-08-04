# Paper execution authorization

P4-2 adds a manual paper-authorization artifact and a pure validator. It does not execute, submit, persist, consume, or automatically approve an order.

`PaperExecutionAuthorizationV1` binds one manual approval to request, candidate, canonical-risk, sizing, trade-plan, decision, snapshot, market/contract/sizing, session, validity, and idempotency identity. It supports `APPROVED`, `REVOKED`, `EXPIRED`, and `BLOCKED`; it is always `MANUAL`, `PAPER`, and non-live.

`PaperAuthorizationResultV1` returns `AUTHORIZED`, `NOT_APPROVED`, `EXPIRED`, `REVOKED`, `SESSION_INVALID`, `IDENTITY_MISMATCH`, `IDEMPOTENCY_MISMATCH`, `BLOCKED`, or `FAILED`. Only `AUTHORIZED` has manual authorization validity and paper-execution eligibility. Live eligibility is always false.

Validation order: request type; authorization type/current time; existence; declared status; authorization window; request ID; idempotency key; canonical linkage; trading identity; session evidence. Session is mandatory in P4-2: absent evidence yields `SESSION_INVALID`. Supported session evidence is `MarketSessionValidationV1`/compatible fields: validation ID, trading date, symbol, exchange, `paper_execution_allowed`, blockers, stale, and future flags.

Preparation eligibility is not authorization. Authorization validity is not paper execution. Paper execution eligibility is only a validator result for a future explicit executor; it must not alter P3 `execution_eligible`. Live eligibility is not part of P4.

Single-use cannot be enforced without state. P4-2 validates scope/idempotency but does not consume authorization; P4-3/P4-5 own executor/repository exactly-once enforcement.

No executor, broker/provider, credentials, network, persistence, database/filesystem access, short option, margin, fees, taxes, brokerage, or slippage behavior is included.
