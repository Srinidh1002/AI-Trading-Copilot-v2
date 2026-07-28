# P4-0 execution-readiness audit

## Scope and conclusion

This is a static architecture audit as of the certified P3-5 baseline. No
runtime behavior was changed and no test was run. The safe P4 direction is a
new, manually authorized, deterministic paper-execution path for Indian F&O
long option-premium positions only: NIFTY/NSE BUY/CALL and SENSEX/BSE BUY/CALL,
or NIFTY/NSE SELL/PUT and SENSEX/BSE SELL/PUT. It must not reuse mutable legacy
execution components as its execution authority.

P3 preparation is not execution. `TradePlanV1` and `PositionSizeResultV1`
prohibit `execution_eligible=True`; `CanonicalRiskResultV1` also rejects a
sizing result with execution eligibility. A prepared `PaperTradeCandidateV1`
therefore remains manually actionable data, not an execution authorization.

## Current architecture and exact evidence

| Boundary | Existing files and symbols | Current behavior |
| --- | --- | --- |
| Canonical preparation | `services/paper/paper_candidate_service.py`: `prepare_paper_candidate`, `_prepare_canonical_risk_candidate`, `PaperCandidatePreparation` | Consumes a supplied `CanonicalRiskResultV1`, gates on `RISK_APPROVED`, identity, sizing, session, expiry and non-execution eligibility; it constructs at most one candidate and never invokes an executor. |
| Explicit canonical submission boundary | `services/paper/paper_candidate_service.py`: `execute_paper_candidate`, `PaperExecutionResult` | An explicit caller can supply approval, time, and optional executor. It rechecks candidate/decision/session/plan identity and imports `services.trade.trade_engine.execute_paper_trade` only when no executor is supplied. This is not a P4-ready authorization or receipt model. |
| Legacy paper executor | `services/trade/trade_engine.py`: `execute_paper_trade`; `services/trade/paper_trade_engine.py`: `process_trade` | Explicit mutable legacy submission accepts an untyped mapping, validates legacy approval fields, and calls `process_trade`. It has no canonical request contract, idempotency key, authorization artifact, or execution receipt contract. |
| Legacy paper simulation | `services/paper_trading/paper_broker.py`: `PaperBroker.place_order`, `cancel_order`, `get_order`; `services/paper_trading/paper_trade_engine.py`: `execute_paper_trade` | In-memory mutable simulated orders/positions with UUIDs and wall-clock timestamps. It fills immediately and supports cancellation, but has no deterministic IDs, canonical identity binding, or controlled lifecycle contract. |
| Other order abstractions | `services/execution/order_executor.py`: `OrderExecutor`; `services/execution/order_manager.py`: `OrderManager.submit_order`; `services/execution/order_tracker.py`: `OrderTracker`; `services/decision/trade_executor.py`: `execute_trade` | Separate legacy order/executor abstractions. They are competing concepts, not dependencies approved for a new canonical P4 path. |
| Candidate contract | `services/contracts/paper_trade_candidate_v1.py`: `PaperTradeCandidateV1`; `docs/contracts/PAPER_TRADE_CANDIDATE_V1.md` | Immutable candidate with market and trade identity, sizing, `position_side`, authorization/execution status fields, serialization, and expiry. It is reusable as an input, but has no candidate ID or idempotency key. |
| Risk/plan contracts | `services/contracts/trade_plan_v1.py`, `position_size_result_v1.py`, `canonical_risk_result_v1.py` | Ready plan, approved sizing, and `RISK_APPROVED` risk result are typed, deterministic, non-executable prerequisites. |
| Authorization | `services/contracts/final_decision_v1.py`: `AuthorizationStatus`; `services/security/authorization.py`: `Authorization.authorize`, `require`, `can_trade`; `services/security/access_control.py` | Final decisions distinguish `ANALYSIS_ONLY`, `PAPER_READY`, and `BLOCKED`; security authorization is role/permission based. Neither is a signed/manual approval bound to candidate, identity, session, expiry, or single use. |
| Session | `services/market_session/validator.py`: `validate_session_timestamp`, `validate_market_session`; `services/contracts/market_session_validation_v1.py`; `services/market_session/policies.py` | Typed NIFTY/NSE and SENSEX/BSE session validation, market/open/stale/future/date/identity gates and strict execution mode. Reusable as an injected execution prerequisite. |
| Broker/provider | `services/broker/base_broker.py`; `services/broker/angel_client.py`; `services/broker/session_manager.py`; `services/options/angel_option_client.py` | Broker/SmartAPI and market-data integrations exist. These are unsafe direct dependencies for P4: paper execution must neither import nor call them. |
| Persistence | `services/database/database_manager.py`: `DatabaseManager`; `services/paper_trade_repository.py`: `PaperTradeRepository`; `services/paper_trade_journal.py`: `PaperTradeJournal`; `services/database/trade_database.py` | SQLite and JSONL/file-backed persistence exist and can write. They are explicitly out of scope for initial P4 state; do not bind them to the new paper executor. |
| Observability | `services/contracts/audit_event_v1.py`: `AuditEventV1`, `EVENT_TYPES`; `services/observability/{emitter,events,redaction,sinks}.py` | Typed audit events already reserve `PAPER_EXECUTION_REQUESTED`, `REJECTED`, `SUBMITTED`, and `FAILED`. `AuditEmitter` is fail-open by default. `InMemoryAuditSink` is reusable; `JsonLinesAuditSink` writes files and must not be default P4 runtime behavior. |
| Replay | `services/replay/runner.py`: `run_replay_fixture`, `run_replay_directory` | Deterministic snapshot-to-decision replay with audit events. It explicitly does not prepare, persist, or execute trades; it is reusable only as the model for isolated execution replay fixtures. |

## Current safety boundary

The canonical preparation route validates supplied data and does not call the
executor. `execute_paper_candidate` is a separately callable boundary and is
not invoked by preparation. Its default fallback to the legacy
`execute_paper_trade` means P4 must not expose it automatically or treat it as
the future canonical executor. No inspected P3 pipeline auto-calls this method.

Eligibility states must remain distinct:

| State | Meaning | Must not imply |
| --- | --- | --- |
| Preparation eligibility | The typed plan/risk result may produce a candidate. | Authorization or any order submission. |
| Authorization eligibility | A valid, explicit human approval artifact exists for this exact request. | A fill or live execution. |
| Paper execution eligibility | A P4 executor has freshly accepted every prerequisite and idempotency check. | `execution_eligible=True` on P3 contracts, or live execution. |
| Live execution eligibility | Reserved for a post-P4 live broker phase. | Any P4 status or approval. |

## Existing relevant tests

- `tests/test_p0_4_paper_execution_boundary.py` — legacy explicit paper
  submission rejection behavior.
- `tests/test_paper_candidate_execution_boundary_v2.py` and
  `tests/test_paper_candidate_service.py` — candidate preparation boundary.
- `tests/test_paper_trade_plan_boundary.py`, `tests/test_paper_risk_integration.py`,
  and `tests/test_paper_session_boundary.py` — canonical plan/risk/session and
  executor-separation coverage.
- `tests/test_paper_trade_candidate_v1.py`, `tests/test_trade_plan_v1.py`,
  `tests/test_position_size_result_v1.py`, and `tests/test_canonical_risk_result_v1.py`
  — P3 contract invariants.
- `tests/test_market_session_validation_v1.py`, `tests/test_nifty_session_validation.py`,
  and `tests/test_sensex_session_validation.py` — session behavior.
- `tests/test_replay_harness.py`, `tests/test_replay_option_trade_plan_scenarios.py`,
  and `tests/test_replay_risk_sizing_scenarios.py` — deterministic replay.
- `tests/test_audit_event_v1.py`, `tests/test_audit_emitter.py`,
  `tests/test_audit_redaction.py`, `tests/test_audit_sinks.py`, and
  `tests/test_risk_observability.py` — bounded, fail-open observability.
- `tests/test_paper_trade_repository.py`, `tests/test_paper_trade_journal.py`, and
  paper-trading orchestration tests cover legacy persistence/simulation, not
  canonical P4 idempotency.

## Reusable components

- `CanonicalRiskResultV1` and `PaperTradeCandidateV1` as validated immutable
  input evidence.
- `validate_session_timestamp` and `MarketSessionValidationV1` for injected
  strict execution-time session checks.
- `AuditEventV1`, `AuditEmitter`, `AuditContext`, redaction, and
  `InMemoryAuditSink` for bounded, fail-open P4 diagnostics.
- Canonical identity fields: snapshot, analysis, decision, trade-plan result,
  trade plan, sizing result, symbol/exchange/action, contract identity, expiry,
  lot size, and quantity.
- The existing no-executor candidate-preparation test pattern and deterministic
  replay methodology.

## Gaps, conflicts, and safety concerns

1. No immutable paper-order request/result, receipt, fill, cancellation, or
   state-transition contract exists for the canonical path.
2. No manual authorization artifact binds a human approval to candidate,
   snapshot/decision/plan/risk identity, session, expiry, and an idempotency
   key. Role permission is not transaction authorization.
3. No deterministic idempotency store or exactly-once paper-execution behavior
   exists. Legacy `PaperBroker` uses UUIDs and immediate fills.
4. There is no canonical in-memory order repository or query interface;
   existing SQLite, JSONL journal, and paper repositories are persistence
   systems and must not become implicit P4 dependencies.
5. The candidate has no first-class `candidate_id`; P4 must define a stable
   request identity/idempotency derivation rather than mutate P3 contracts.
6. Audit vocabulary has no explicit filled/cancelled execution events. P4 must
   either use the existing vocabulary only for the accepted initial lifecycle
   or extend vocabulary in a separately reviewed contract change before fill/
   cancellation events are introduced.
7. Multiple legacy execution abstractions (`execute_paper_trade`, `PaperBroker`,
   `OrderExecutor`, `OrderManager`, paper repositories) duplicate order concepts
   and can bypass canonical risk/authorization/session artifacts. They are
   unsafe direct dependencies for P4-1 through P4-4.
8. `execute_paper_candidate` can default-import the legacy executor. This is a
   contained explicit path, but it is the primary pre-P4-1 safety concern: no
   new entry point may wire candidate preparation directly to it.

## Locked P4 implementation sequence

1. P4-1: immutable paper execution contracts with no executor or broker import.
2. P4-2: manual authorization contract/validator, then deterministic
   identity-bound idempotency key derivation.
3. P4-3: isolated deterministic in-memory paper executor that consumes only a
   validated request and has no provider/broker/filesystem/database dependency.
4. P4-4: canonical execution orchestration, invoking exactly once only after
   risk, candidate, authorization, identity, session, and expiry gates pass.
5. P4-5: in-memory order-state repository and deterministic transition/query
   behavior; no durable storage.
6. P4-6: execution replay and bounded observability.
7. P4-7: certification. Live broker work remains a later P5 decision.

## Explicit exclusions

No live integration, broker credentials, SmartAPI placement, provider access,
automatic authorization, automatic capital fetching, short options, margin,
partial fills, fees, taxes, brokerage, slippage, retries, database writes,
JSONL writes, or production persistence belongs to P4-0 through P4-7.

## Proposed manual test gates

Before P4-1: manually review that no P4 file imports `services.broker`, Angel,
database, journal, or legacy executor modules. For each subphase, the user
should run focused new tests followed by P4 regression, canonical regression,
paper regression, safety regression, the P3-focused suite, the full repository
suite, and import checks. Required negative cases include wrong identity,
expired candidate/approval/plan, closed/stale session, reused idempotency key,
double-submit attempt, audit-sink failure, and attempts to inject an executor,
broker, provider, repository, or filesystem dependency.
