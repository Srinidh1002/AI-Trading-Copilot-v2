# Phase 4 safe paper-entry architecture

Phase 4 is a bounded, explicit paper-only path: canonical risk evidence →
candidate → request → externally supplied manual authorization → validation →
deterministic executor → canonical result → optional explicit in-memory order
and observation storage → read-only replay.

Public contracts are the P4 request, authorization, authorization-result,
execution-result, order-state, canonical-result, observation, and replay-result
contracts. Runtime APIs are authorization validation, paper execution,
idempotency storage, canonical orchestration, order/observation repositories,
observation construction, and replay.

Supported identities are NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE.
Only BUY/CALL/LONG and SELL/PUT/LONG are supported. All invocation is explicit;
manual authorization and supplied session evidence are authoritative.

Execution is deterministic and at-most-once through process-local idempotency.
Repositories are process-local, locked, and non-persistent. Replay compares
recorded evidence only: it does not execute, fill, validate, save, or mutate.
No P4 path provides live execution, persistence, brokers/providers, networking,
background workers, short options, or upstream intelligence reruns. P5 begins
with the data/intelligence audit boundary.
