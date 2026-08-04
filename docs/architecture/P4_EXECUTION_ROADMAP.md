# P4 execution roadmap

P4 introduces only manually authorized, deterministic paper execution for
NIFTY/SENSEX long option-premium positions: BUY/CALL and SELL/PUT. P4 does not
enable live execution. Every phase must preserve `execution_eligible=False` on
all P3 contracts/results and must not rerun analysis, decision, selection,
trade-plan construction, or sizing.

## Shared invariants

- Execution requires `CanonicalRiskResultV1.risk_status == "RISK_APPROVED"`, a
  fully sized candidate, valid strict session, explicit unexpired authorization,
  exact snapshot/decision/trade-plan/risk/candidate identity, and deterministic
  idempotency.
- Preparation eligibility, authorization eligibility, paper execution
  eligibility, and live execution eligibility are separate states.
- No broker/provider calls, executor fallback, database/filesystem writes,
  automatic approval/capital retrieval, short-option model, margin, fees,
  taxes, brokerage, slippage, hidden retry, or live order placement.
- P4 must use injected clocks and ID factories for deterministic tests.

## Current phase status

- P4-0 is complete.
- P4-6 is certified: read-only deterministic replay and process-local paper
  execution observations are available; P4-7 final certification remains next.
- P4-7 is certified. Phase 4 is complete; P5-0 data/intelligence audit is next.
- P4-1 is certified complete.
- P4-2 is certified complete.
- P4-3 is implemented but uncertified: deterministic paper-only full-fill execution and optional in-memory idempotency exist; manual test gates have not run.
- P4-3A0 is an audit-only four-index identity expansion assessment; P4-3A1 through P4-3A4 remain pending and must precede any BANKNIFTY/FINNIFTY execution support.
- P4-3A1 is implemented but uncertified: a shared immutable four-index registry now backs the existing market-session identity API; contracts and runtime gates remain pending P4-3A2.
- P4-3A2 is implemented but uncertified: P3 contract and sizing identity gates use the shared four-index registry; P4 contract/executor expansion remains P4-3A3.
- P4-3A3 is implemented but uncertified: P4 request, authorization, result, validator, and executor compatibility now accept the shared four-index set; P4-3A4 remains unstarted.
- P4-3A4 is certified: deterministic four-index replay, focused compatibility, P3/P4/canonical/paper-safety regressions, import check, and full repository suite passed. P4-4 remains next.
- P4-4 is certified: explicit canonical paper execution orchestration and its focused tests passed; P4-5 remains next.
- P4-2 through P4-7 remain pending. No P4 phase enables live execution.

## P4-1 — Paper execution contracts

Goal: define immutable request/result/receipt and lifecycle-state contracts with
deterministic serialization, disabled-by-default execution, and no broker
dependency. Likely new files: `services/contracts/paper_execution_request_v1.py`,
`paper_execution_result_v1.py`, `paper_order_state_v1.py`, and matching docs/
tests. Likely modified files: `services/contracts/__init__.py` only. Public API:
request construction and `to_dict`/`semantic_dict`; no submission function.
Statuses are contract-specific: request is fixed to `PAPER`; result supports
`ACCEPTED`, `FILLED`, `REJECTED`, `BLOCKED`, `DUPLICATE`, `FAILED`; order state
supports `CREATED`, `AUTHORIZED`, `SUBMITTED`, `FILLED`, `REJECTED`, `BLOCKED`,
`CANCELLED`, `FAILED`. P4-1 is implemented but remains uncertified.
Invariants: primitive, complete identity and idempotency key; result cannot
claim live execution. Prohibited: importing broker, persistence, or legacy
executor. Focused tests: construction, validation, serialization, identity and
status transition negatives. Regression gates: contracts, canonical, paper,
safety. Completion: contracts are documented and no runtime route calls them.

## P4-2 — Manual authorization contract and validator

Goal: define explicit human authorization, bound to candidate and all canonical
identities, strict session identity/date, expiry, and single-use/idempotency
semantics. Likely new files: `services/contracts/paper_execution_authorization_v1.py`,
`services/paper/authorization_validator.py`, tests and contract documentation.
Likely modified files: P4-1 contract exports only. Public API: pure validator
returning typed accepted/rejected authorization outcome. Statuses: `REQUIRED`,
`AUTHORIZED`, `EXPIRED`, `CONSUMED`, `IDENTITY_MISMATCH`, `SESSION_BLOCKED`,
`REJECTED`. Invariants: no automatic approval; role permission is supplementary,
not an authorization substitute. Prohibited: UI, credentials, persistent token
storage, or mutation. Tests: wrong identity/session, expiry, reuse/idempotency,
BUY/CALL and SELL/PUT. Gates: P4-1 plus canonical/paper/safety. Completion: an
approval alone cannot invoke any executor.

## P4-3 — Deterministic paper executor

Goal: build a simulated executor only, receiving a validated P4 request and
returning a typed submitted/filled/rejected result exactly once. Likely new
files: `services/paper/executor.py`, `services/paper/in_memory_order_store.py`,
and focused tests. Likely modified files: no legacy execution files. Public API:
injected `execute(request)` and read-only result/store query interfaces.
Statuses: P4-1 lifecycle statuses; initial implementation may deterministically
fill or reject but must document the chosen rule. Invariants: no live broker,
provider, clock randomness, hidden retry, or database/filesystem use.
Prohibited: importing `services.trade.trade_engine`, `PaperBroker`, Angel, or
repositories/journals. Tests: exactly-once, deterministic receipt, duplicate
key, rejection, and executor isolation. Gates: P4-1/2, paper, safety. Completion:
no external side effect is possible from the module.

## P4-4 — Canonical paper execution pipeline

Goal: compose approved risk result, prepared candidate, authorization, session,
identity and expiry checks, then invoke the P4-3 executor exactly once. Likely
new file: `services/paper/execution_pipeline.py`; likely modified files:
`services/paper/__init__.py` and tests only. Public API: a single explicit
manually invoked `execute_authorized_paper_candidate(...)`. Statuses:
`REJECTED`, `AUTHORIZED`, `SUBMITTED`, `FILLED`, `FAILED`; rejected results
must name a bounded reason. Invariants: no analysis/decision/selection/planning/
sizing rerun; candidate preparation never calls this pipeline; `execution_eligible`
on P3 data remains false. Prohibited: default legacy executor fallback and
implicit authorization. Tests: each prerequisite, identity cross-product,
single executor call, and no executor call on rejection. Gates: P4 focused,
canonical, paper, safety. Completion: only injected P4 executor can be called.

## P4-5 — Paper order state and in-memory repository

Goal: formalize deterministic order state transitions, duplicate prevention,
and query/read API without production persistence. Likely new files:
`services/paper/order_repository.py`, `services/paper/order_state_machine.py`.
Likely modified files: P4-3 store integration. Public API: append/lookup by
idempotency key and order/receipt identity. Statuses: only P4-1 controlled
states with explicit allowed transitions. Invariants: in-memory only; deep-copy
outputs; no mutable nested leakage. Prohibited: SQLite, JSONL, existing paper
journal/repository, restart recovery, or external cache. Tests: ordering,
duplicates, invalid transitions, query stability. Gates: P4-1–4 plus paper and
safety. Completion: deterministic state can be replayed from supplied events.

## P4-6 — Replay and observability

Goal: add deterministic execution scenarios and bounded fail-open audit hooks.
Likely new files: execution replay fixture/tests and P4 audit documentation;
likely modified files: audit vocabulary only if lifecycle events cannot be
expressed with the reviewed controlled vocabulary. Public API: optional injected
`AuditEmitter`/`AuditContext`. Statuses: existing execution requested/rejected/
submitted/failed events; add filled/cancelled only through explicit contract
review. Invariants: primitive bounded payloads, no credentials/full candidate/
risk/decision, and audit failure cannot change result or executor calls.
Prohibited: `JsonLinesAuditSink` as default, external replay data, or runtime
writes. Tests: ordering, terminal uniqueness, fail-open, idempotency replay,
both supported directions, and isolation. Gates: P4 focused, replay, canonical,
paper, safety. Completion: execution semantics are reproducible offline.

## P4-7 — Paper execution certification

Goal: certify the bounded P4 path. Files likely modified: certification audit
and changelog only. Public API/statuses: none. Invariants/prohibitions: all
prior ones. Focused tests: every P4 test plus contract, authorization, executor,
pipeline, store, replay, and observability suites. Regression gates: P4
focused; canonical; paper; safety; full repository; import checks, all run
manually by the user. Completion: recorded counts, known warnings, and explicit
confirmation that no live execution or P5 feature was enabled.

## Reserved P5, not P4

Only after P4 certification: live broker abstraction, credentials, live order
placement, reconciliation, partial fills, network retries, margin checks, and
fees/taxes/brokerage/slippage. None is a P4 dependency.
# P4-5 — in-memory paper-order repository

P4-4 is certified. P4-5 provides an explicit, process-local `InMemoryPaperOrderRepository` for
immutable order-state snapshots, deterministic retrieval, and controlled
atomic transitions. It has no persistence and no execution side effect.
P4-5 is certified with canonical identity carried by `PaperOrderStateV1`;
P4-6 replay and observability remains next.
