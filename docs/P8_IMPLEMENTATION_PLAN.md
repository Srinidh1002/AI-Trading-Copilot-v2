# P8 Implementation plan

## Objective

Implement deterministic PAPER portfolio capital, reservations, admission, aggregation, locks, persistence, recovery, and replay across multiple certified P6 plans and P7 positions. P8 adds one portfolio-wide authority; it does not plan trades, manage position lifecycle, fetch market/broker data, or place orders.

## Authority separation

```text
P6 IntegratedThreeTargetTradePlanResultV1
  owns contract + entry/stop/targets + lots/quantity + cost/risk/capital evidence
                    |
                    v
P8 admission + durable pending hold + portfolio policy
                    |
                    v
P7 entry/position lifecycle + fills + position P&L
                    |
                    v
P8 active deployment + release + portfolio aggregates + locks + persistence
```

P8 reads P6 and P7 exact typed values and returns new immutable values. It never mutates caller mappings or upstream objects.

## P8 work packages

- **P8-WP1 / P8A-C:** audit, policy, snapshot, identity, vocabulary, serialization.
- **P8-WP2 / P8D-E:** reservation state machine and multi-trade admission.
- **P8-WP3 / P8F-G:** aggregation, lifecycle coordination, persistence, recovery, reconciliation, idempotency.
- **P8-WP4 / P8H:** reusable real-contract harness, concurrency/replay/subprocess/corruption/isolation certification.

## Eight-credit execution plan

| Credit | Outcome |
|---|---|
| 1 | This audit, exact architecture, manifests, and test blueprint |
| 2 | All P8 immutable contracts and pure deterministic engines |
| 3 | Lifecycle coordination, atomic persistence, recovery, reconciliation, durable replay |
| 4 | One reusable real-contract portfolio harness and complete test-file foundations |
| 5 | Core contract/reservation/admission/aggregation matrix closure |
| 6 | Concurrency, instruments, locks, restart/subprocess/corruption/replay closure |
| 7 | Scoped P8 plus P6/P7/legacy portfolio/risk/persistence regressions |
| 8 | Full suite, repairs, compilation, documentation, artifact audit, one P8 commit |

## Proposed contracts

All are frozen slotted dataclasses, exact-type validated, defensively detached, canonical-JSON serializable, PAPER-only, schema `1.0`, with caller-supplied IDs/timestamps.

### `PaperPortfolioPolicyV1`

Fields: `portfolio_policy_id`, `policy_timestamp`, `maximum_concurrent_trades`, `maximum_total_deployed_capital`, `maximum_total_portfolio_risk_amount`, `maximum_daily_loss_amount`, `maximum_daily_drawdown_amount`, `maximum_instrument_risk_fraction`, `maximum_direction_risk_fraction`, `maximum_correlated_index_risk_fraction`, `maximum_expiry_risk_fraction`, `minimum_available_cash_reserve`, `profit_lock_enabled`, `minimum_daily_realized_profit_to_lock`, `loss_lock_enabled`, `metadata`, PAPER flags, schema.

Rules: limits are finite/nonnegative, fractions in `(0, 1]`, concurrent count positive, total deployed/risk positive, reserve nonnegative, enabled profit lock requires a positive threshold, disabled profit lock requires `None`, and limit combinations must permit at least a zero-position portfolio. Policy does not contain starting capital.

### `PaperPortfolioAdmissionInputV1`

Fields: `admission_request_id`, `admission_idempotency_key`, `portfolio_event_id`, `portfolio_id`, `requested_reservation_id`, `evaluated_at`, `trading_day_id`, exact `IntegratedThreeTargetTradePlanResultV1`, exact current `PaperPortfolioSnapshotV1`, exact policy, metadata, PAPER flags, schema. It exposes a canonical semantic dictionary/hash excluding only result/runtime identities declared nonsemantic.

### `PaperPortfolioAdmissionResultV1`

Fields: admission/request/key/hash IDs, portfolio/policy/day/integration/plan/reservation IDs, `status`, `approved`, `reservation_amount`, `reserved_risk_amount`, projected capital/count/risk/exposure metrics, optional resulting reservation/snapshot, blockers, reasons, warnings, evaluated timestamp, metadata, PAPER flags, schema.

`APPROVED` requires a PENDING_HOLD and resulting snapshot. `NO_CAPACITY` requires decision reasons and no mutation. `BLOCKED` requires blockers and no mutation.

### `PaperCapitalReservationV1`

Fields: `reservation_id`, portfolio/admission/integration/plan IDs, optional `position_id`, `reservation_status`, `original_capital_amount`, `remaining_capital_amount`, `released_capital_amount`, `original_risk_amount`, `remaining_risk_amount`, initial/remaining quantity, last P7 lifecycle state/transition sequence, sorted processed fill IDs, created/activated/updated/released timestamps, blockers/reasons/warnings/metadata, PAPER flags, schema.

Invariants: original equals remaining plus released; PENDING_HOLD has no position ID and full remaining amounts; ACTIVE has position ID; RELEASED has zero remaining amount/risk and a released timestamp. Identities and originals never change.

### `PaperPortfolioPositionReferenceV1`

Fields: portfolio/reservation/position/plan/integration/contract IDs, underlying, exchange, option symbol/type, economic direction, expiry, lifecycle state and transition sequence, initial/remaining lot and quantity, initial/remaining capital, initial/remaining risk, realized net/unrealized/total P&L, ordered exit fill IDs, last observation ID, updated timestamp, PAPER flags, schema.

This is a detached P8 projection for aggregation/recovery, not a second position lifecycle authority. It must exactly match its source P7 position.

### `PaperPortfolioExposureV1`

Fields: `metric` fixed to `REMAINING_RISK`, sorted `instrument_risk`, `direction_risk`, `expiry_risk`, `correlated_index_direction_risk`, totals, warnings, PAPER flags, schema. Keys are canonical strings; values are finite nonnegative floats.

### `PaperPortfolioLockStateV1`

Fields: `trading_day_id`, `loss_locked`, `profit_locked`, lock reason codes, locked timestamps, `daily_total_pnl`, `daily_realized_net_pnl`, `daily_loss_amount`, `intraday_peak_equity`, `daily_drawdown_amount`, PAPER flags, schema. Locks latch within a trading-day identity.

### `PaperPortfolioSnapshotV1`

Fields: `portfolio_snapshot_id`, `portfolio_id`, `portfolio_policy_id`, `trading_day_id`, `starting_capital`, `available_cash`, `reserved_capital`, `deployed_capital`, `committed_capital`, `realized_net_pnl`, `unrealized_pnl`, `total_pnl`, `total_equity`, `portfolio_return_fraction`, `open_position_count`, `pending_plan_count`, `concurrent_trade_count`, `aggregate_active_risk`, `aggregate_pending_risk`, `aggregate_committed_risk`, sorted reservations, sorted position references, exposure, lock state, blockers/reasons/warnings/provenance metadata, `event_sequence`, `created_at`, `updated_at`, PAPER flags, schema.

Snapshot construction validates every capital, P&L, count, risk, exposure, identity, and lock invariant; it does not trust supplied aggregate fields.

### `PaperPortfolioUpdateInputV1`

Fields: update/request/idempotency/event IDs, sequence, portfolio ID, timestamp/day, exact current P8 snapshot, exact P7 persistence snapshot, optional exact P7 entry or position evaluation result, update type, metadata, PAPER flags, schema. Semantic hash binds the entire economic evidence.

### `PaperPortfolioUpdateResultV1`

Fields: update IDs/key/hash, status, decision, source/result snapshot IDs, source/result event sequences, optional reservation, resulting snapshot, applied P7 transition/fill IDs, blockers/reasons/warnings/timestamp/metadata, PAPER flags, schema. Exact duplicate returns `NO_CHANGE` with the unchanged snapshot.

### `PaperPortfolioPersistenceSnapshotV1`

Fields: `portfolio_id`, full typed snapshot, admission idempotency records, update idempotency records, processed portfolio/P7 event IDs and semantic hashes, `created_at`, `updated_at`, `event_sequence`, PAPER flags, schema. `to_json()` is sorted compact JSON with `allow_nan=False`; `integrity_hash` is SHA-256 of those bytes; `from_dict` rejects empty/wrong/malformed nested payloads.

### `PaperPortfolioRecoveryResultV1`

Fields: `portfolio_id`, `status` (`RECOVERED`, `BLOCKED`, `CORRUPT`), optional persistence snapshot, reconciliation codes, blockers, warnings, recovered timestamp, PAPER flags, schema. CORRUPT never returns an admissible snapshot.

## Proposed services

Pure services created in Credit 2:

- `evaluate_paper_portfolio_admission(input) -> PaperPortfolioAdmissionResultV1`
- `reserve_pending_paper_capital(...)`, `activate_paper_capital_reservation(...)`, and `release_paper_capital_reservation(...)`
- `project_paper_portfolio_position(...) -> PaperPortfolioPositionReferenceV1`
- `aggregate_paper_portfolio(...) -> PaperPortfolioSnapshotV1`
- `evaluate_paper_portfolio_locks(...) -> PaperPortfolioLockStateV1`
- `validate_paper_portfolio_reconciliation(...) -> tuple[str, ...]`

Stateful boundary services created in Credit 3:

- `PaperPortfolioRepository`: portfolio-specific atomic JSON storage using the existing repository technology.
- `PaperPortfolioPersistenceService`: typed envelope, integrity, idempotent save/get/list/history.
- `PaperPortfolioRecoveryService`: decode, corruption checks, P7 reconciliation.
- `PaperPortfolioLifecycleCoordinator`: admission, activation, partial/terminal application, persistence ordering.
- `PaperPortfolioReplayCoordinator`: strict duplicate/order behavior over recovered state.

## Proposed integration

### Flow 1: admission

Input is P6 final result + current snapshot + policy + caller IDs/time. The pure evaluator validates P6 READY/PAPER/coherence, current snapshot/policy identity, locks, and projected count/capital/risk/exposure. APPROVED creates a PENDING_HOLD and a next snapshot at `event_sequence + 1`; the coordinator atomically persists it. NO_CAPACITY/BLOCKED writes nothing unless a future explicit audit-log feature is added.

### Flow 2: entry activation

Capacity must already be durably held. The caller/P7 adapter produces a real P7 OPEN result. The coordinator validates identity, converts the matching hold to ACTIVE, projects the P7 position, recomputes aggregates, and atomically persists P8.

Failure rules:

- P8 hold write fails: do not activate P7; return BLOCKED.
- P7 activation fails after a durable hold: retain the hold; retry with the same evidence is deterministic, or a typed cancellation releases it.
- P7 activates but the P8 activation write fails: return BLOCKED and block new admission; restart reconciliation observes the authoritative P7 OPEN position and pending hold and performs the one authorized deterministic PENDING_HOLD-to-ACTIVE transition.
- Duplicate retry: key/hash and P7 transition/fill evidence yield the persisted result with no second reservation or sequence increment.

This is ordered local orchestration, not a distributed transaction.

### Flow 3: partial exit

`PaperTradePositionEvaluationResultV1` with `PARTIALLY_EXITED` and its real resulting position/P&L/fills enters the coordinator. It calculates target remaining capital/risk directly from originals and P7 remaining quantity, updates the projection, aggregates, increments once, and atomically persists. All new fill IDs are recorded in sorted canonical form.

### Flow 4: terminal exit

Any certified terminal P7 result sets reservation remaining capital/risk to exact zero and status RELEASED, retains terminal position realized net P&L history, removes its unrealized/exposure contribution, recomputes locks, and atomically persists.

### Flow 5: restart

Recover typed P7 snapshots and the P8 persistence snapshot. Verify both integrity envelopes, identities, uniqueness, sequences, arithmetic, and PAPER flags. Reconciliation may only perform these deterministic operations: pending hold + matching OPEN P7 position becomes ACTIVE; ACTIVE + matching terminal P7 becomes RELEASED; an exact stale projection is refreshed from a newer unique P7 snapshot. Missing/ambiguous/conflicting evidence is CORRUPT/BLOCKED, not silently repaired.

### Flow 6: duplicate event

Same idempotency key/hash or already-applied identical P7 transition/fill IDs returns `NO_CHANGE`, the same snapshot bytes/hash, and no repository write. Same key/different hash or same event ID/different evidence is BLOCKED.

### Flow 7: daily lock

After every economic update, recompute daily totals, peak, drawdown, and latches. Locks block only new admission. P7 management, releases, persistence, and recovery continue. A new caller-supplied day ID produces a new day baseline/lock state under explicit coordinator rollover; runtime local date never resets it.

## Proposed persistence

Default path: `data/paper_trading/paper_portfolio_state.json`. Document shape:

```json
{"version":1,"portfolios":{"portfolio-id":{"portfolio_id":"portfolio-id","typed_p8_snapshot":{},"typed_p8_integrity_hash":"..."}}}
```

The exact record also includes current trading-day ID and status for indexed filtering, but typed state remains authoritative. Writes validate/deep-copy the complete document, create a sibling temporary file, flush and fsync, then `os.replace`. Orphan temporary files are never read as authority. A failed replace preserves the prior coherent snapshot; deterministic retry succeeds with the same bytes.

Operations:

- `save_portfolio(persistence_snapshot)` and batch `save_portfolios(...)`;
- `get_portfolio(portfolio_id)`;
- `get_by_trading_day(portfolio_id, trading_day_id)` from persisted current/history envelopes;
- `get_by_admission_idempotency_key(portfolio_id, key)` through typed records;
- `list_active_portfolios()` when current records are not blocked/corrupt;
- `load_history(portfolio_id)` for retained prior day/event snapshots if implemented by the manifest;
- recovery of reservations, processed events, sequences, and hashes from the one typed envelope.

One whole-document replace is the available transaction boundary. Concurrent OS-process compare-and-swap/locking is not supplied by the current repository; P8 serializes through one coordinator per repository and detects stale source snapshot IDs/sequences. Document this limitation rather than introducing a database framework.

## Proposed recovery and reconciliation

Validation codes are stable strings and include:

`UNSUPPORTED_SCHEMA`, `NON_PAPER_STATE`, `INTEGRITY_MISMATCH`, `PORTFOLIO_IDENTITY_MISMATCH`, `POLICY_IDENTITY_MISMATCH`, `TRADING_DAY_MISMATCH`, `STARTING_CAPITAL_INVALID`, `CAPITAL_EQUATION_MISMATCH`, `NEGATIVE_CAPITAL_COMPONENT`, `PNL_EQUATION_MISMATCH`, `EQUITY_EQUATION_MISMATCH`, `RETURN_EQUATION_MISMATCH`, `COUNT_MISMATCH`, `DUPLICATE_RESERVATION_ID`, `DUPLICATE_PLAN_ID`, `DUPLICATE_POSITION_ID`, `DUPLICATE_EVENT_ID`, `DUPLICATE_FILL_ID`, `IDEMPOTENCY_PAYLOAD_CONFLICT`, `RESERVATION_ARITHMETIC_MISMATCH`, `RESERVATION_POSITION_MISMATCH`, `ACTIVE_RESERVATION_MISSING_POSITION`, `TERMINAL_RESERVATION_ACTIVE`, `UNKNOWN_POSITION`, `P7_IDENTITY_MISMATCH`, `P7_QUANTITY_MISMATCH`, `P7_TRANSITION_REGRESSION`, `P8_EVENT_SEQUENCE_REGRESSION`, `TIMESTAMP_REGRESSION`, `RISK_AGGREGATE_MISMATCH`, `PNL_AGGREGATE_MISMATCH`, `EXPOSURE_AGGREGATE_MISMATCH`, `LOCK_STATE_MISMATCH`, `DAILY_DRAWDOWN_MISMATCH`.

Structural decoder errors raise `TypeError`/`ValueError`, following P7. Recovery converts them to CORRUPT with codes at its public boundary. Corrupt records remain on disk for diagnosis; they are not returned as active and are never overwritten by a guessed repair.

## Capital invariants

For stable-identity-sorted values and tolerance `1e-9`:

```text
reservation.original_capital = reservation.remaining_capital + reservation.released_capital
reserved_capital = fsum(PENDING_HOLD remaining_capital)
deployed_capital = fsum(ACTIVE remaining_capital)
committed_capital = reserved_capital + deployed_capital
realized_net_pnl = fsum(latest unique P7 position realized_net_pnl)
unrealized_pnl = fsum(nonterminal latest unique P7 position unrealized_pnl)
total_pnl = realized_net_pnl + unrealized_pnl
total_equity = starting_capital + total_pnl
available_cash = total_equity - committed_capital
portfolio_return_fraction = total_pnl / starting_capital
capital_utilization = committed_capital / starting_capital
aggregate_committed_risk = aggregate_pending_risk + aggregate_active_risk
```

`starting_capital > 0`; all capital/risk buckets are finite/nonnegative; `available_cash >= minimum_available_cash_reserve`. Reserved/deployed values never also subtract from equity.

Use float because certified P6/P7 do. Use `math.fsum` over sorted stable IDs and compare with `math.isclose`. Preserve upstream values; do not introduce new two-decimal rounding. Terminal remaining amounts are exactly `0.0`.

## Admission model

Evaluation order is deterministic and diagnostics preserve first occurrence:

1. exact types, schema, PAPER flags, identity/day/policy coherence;
2. P6 READY, cost-feasible, complete capital/risk/contract evidence;
3. current snapshot/reconciliation health and portfolio locks;
4. duplicate request/key semantics;
5. concurrent capacity;
6. minimum reserve and available cash;
7. maximum deployed/committed capital;
8. total risk;
9. instrument risk;
10. economic direction risk;
11. same-direction NIFTY/SENSEX correlated risk;
12. exact-expiry risk.

Malformed/incoherent/locked/corrupt inputs are BLOCKED. Valid projections exceeding capacity are NO_CAPACITY. Only an APPROVED result may create a pending hold.

## Reservation and release model

State machine:

```text
APPROVED -> PENDING_HOLD -> ACTIVE -> RELEASED
                    \----------------> RELEASED (typed cancellation/terminal-before-entry)
```

For initial capital `C`, initial risk `R`, initial quantity `Q`, and P7 remaining quantity `q`:

```text
target_remaining_capital = C * q / Q
target_remaining_risk = R * q / Q
release_delta = previous_remaining_capital - target_remaining_capital
```

Compute from originals every time. A terminal P7 state forces both targets to zero. Reject quantity growth, lot incoherence, identity mismatch, missing reservation, and negative release. Entry OPEN changes bucket classification without changing committed total. A mere WAITING result creates neither a second hold nor deployed capital.

## P&L and risk aggregation

Deduplicate by P7 position ID, choose only the uniquely newest coherent transition, and reject two payloads at the same identity/sequence with different semantics. Include terminal position realized net P&L in cumulative realized P&L; exclude terminal unrealized P&L and risk. Include active/partial realized net plus unrealized. Never aggregate `PaperTradePnlEvidenceV1` deltas in addition to position after-values.

Remaining active risk scales original P6 risk by remaining quantity. Pending risk uses full P6 risk. No stop-distance/Greeks/option analytics recomputation occurs.

## Exposure model

All policy exposure metrics use remaining risk:

- instrument key: `UNDERLYING|EXCHANGE` (for example `NIFTY|NSE`);
- direction key: exact `BULLISH` or `BEARISH`;
- expiry key: exact ISO date from the typed contract;
- correlated key: `NIFTY+SENSEX|DIRECTION`.

For each bucket, fraction is bucket remaining risk divided by `maximum_total_portfolio_risk_amount`. PENDING_HOLD projections participate in admission checks using P6 evidence but appear separately from active exposures in snapshot provenance. CALL/PUT remains descriptive, never economic direction. No statistical correlation, delta weighting, capital netting, or opposite-direction offset.

## Daily drawdown and locks

The caller supplies `trading_day_id`; timestamps are aware and policy/snapshot default timezone metadata is `Asia/Kolkata`. Day rollover is an explicit coordinator operation.

```text
daily_total_pnl = daily_realized_net_pnl + current_unrealized_pnl
daily_loss_amount = max(0, -daily_total_pnl)
intraday_peak_equity = max(previous_peak, total_equity)
daily_drawdown_amount = max(0, intraday_peak_equity - total_equity)
```

Loss lock latches at `daily_loss_amount >= maximum_daily_loss_amount` or `daily_drawdown_amount >= maximum_daily_drawdown_amount` when enabled. Profit lock latches when enabled and daily realized net P&L reaches its threshold. Either blocks new admissions only. Existing positions may always close and P8 must process their releases.

## Controlled vocabularies

| Domain | Values |
|---|---|
| Admission status | `APPROVED`, `NO_CAPACITY`, `BLOCKED` |
| Reservation status | `PENDING_HOLD`, `ACTIVE`, `RELEASED`, `BLOCKED` |
| Update status | `APPLIED`, `NO_CHANGE`, `BLOCKED` |
| Update type | `ENTRY_ACTIVATION`, `POSITION_UPDATE`, `TERMINAL_RELEASE`, `PENDING_RELEASE`, `DAY_ROLLOVER`, `RECONCILIATION` |
| Recovery status | `RECOVERED`, `BLOCKED`, `CORRUPT` |
| Exposure metric | `REMAINING_RISK` |
| Economic direction | certified `BULLISH`, `BEARISH` |
| Execution | `PAPER`; live eligible always false |

Admission capacity reasons include `CONCURRENT_TRADE_LIMIT`, `AVAILABLE_CASH_INSUFFICIENT`, `MINIMUM_RESERVE_BREACH`, `DEPLOYED_CAPITAL_LIMIT`, `TOTAL_RISK_LIMIT`, `INSTRUMENT_RISK_LIMIT`, `DIRECTION_RISK_LIMIT`, `CORRELATED_INDEX_RISK_LIMIT`, and `EXPIRY_RISK_LIMIT`. Blocking codes include `PLAN_NOT_READY`, `CAPITAL_EVIDENCE_INCOMPLETE`, `PORTFOLIO_LOCKED`, `PORTFOLIO_CORRUPT`, `PAPER_MODE_REQUIRED`, `IDENTITY_MISMATCH`, `EVENT_OUT_OF_ORDER`, and `IDEMPOTENCY_PAYLOAD_CONFLICT`.

## Production file manifest

### Credit 2 creates

- `services/contracts/paper_portfolio_policy_v1.py`
- `services/contracts/paper_portfolio_admission_input_v1.py`
- `services/contracts/paper_portfolio_admission_result_v1.py`
- `services/contracts/paper_capital_reservation_v1.py`
- `services/contracts/paper_portfolio_position_reference_v1.py`
- `services/contracts/paper_portfolio_exposure_v1.py`
- `services/contracts/paper_portfolio_lock_state_v1.py`
- `services/contracts/paper_portfolio_snapshot_v1.py`
- `services/contracts/paper_portfolio_update_input_v1.py`
- `services/contracts/paper_portfolio_update_result_v1.py`
- `services/contracts/paper_portfolio_persistence_snapshot_v1.py`
- `services/contracts/paper_portfolio_recovery_result_v1.py`
- `services/paper_portfolio/__init__.py`
- `services/paper_portfolio/paper_capital_reservation_manager.py`
- `services/paper_portfolio/paper_portfolio_admission_evaluator.py`
- `services/paper_portfolio/paper_portfolio_aggregation.py`
- `services/paper_portfolio/paper_portfolio_lock_evaluator.py`
- `services/paper_portfolio/paper_portfolio_reconciliation.py`

### Credit 3 creates

- `services/paper_portfolio_repository.py`
- `services/paper_portfolio/paper_portfolio_persistence_service.py`
- `services/paper_portfolio/paper_portfolio_recovery_service.py`
- `services/paper_portfolio/paper_portfolio_lifecycle_coordinator.py`
- `services/paper_portfolio/paper_portfolio_replay_coordinator.py`

### Expected modifications

- Credit 2 updates `services/contracts/__init__.py` lazy exports only.
- Credits 2/3 update `services/paper_portfolio/__init__.py` exports.
- Credits 4-6 add tests/helper files only.
- Credit 8 updates these two P8 documents only if implementation facts/counts require final reconciliation.
- Certified P6 and P7 production files, `PaperTradingEngine`, legacy portfolio utilities, database schemas, broker/provider/runtime/order modules remain unchanged.

## Test harness design

Credit 4 creates one shared `tests/p8_portfolio_harness.py`. No competing harness.

It provides:

- fixed aware timestamps and caller ID bundles for portfolio/policy/admission/reservation/P7/P8 events;
- deterministic starting-capital portfolios and permissive/tight/loss-lock/profit-lock policy profiles;
- real canonical P6 READY NIFTY CALL, NIFTY PUT, SENSEX CALL plans, plus BLOCKED/NO_SIZE variants;
- real P7 WAITING, OPEN, PARTIALLY_EXITED, each terminal state, fill, P&L evidence, and persistence snapshots;
- repository-backed admission, activation, release, aggregation, persistence, recovery, reconciliation, and replay helpers;
- a frozen scenario-step representation: step ID, action, input evidence, expected status, expected balances/exposures/sequence/hash;
- `assert_portfolio_balanced(snapshot)`, `assert_exposures_match(snapshot)`, `assert_lock_state(...)`, and `assert_economic_no_change(before, after)` helpers;
- canonical JSON/hash comparisons and caller-object detachment assertions.

Fresh-subprocess protocol passes only repository path and scenario name as process arguments. The child imports real production contracts/services, recovers JSON from disk, performs one deterministic action, and prints one canonical JSON object. Parent checks exit code, stderr, exact output, persisted bytes/hash, and duplicate no-op. No runtime UUID, current clock, arbitrary object, network, broker, or in-memory-only repository is allowed.

## Test file manifest

| Exact path | WP / credit | Minimum meaningful tests | Behavioral scope / certification group |
|---|---:|---:|---|
| `tests/test_paper_portfolio_policy_v1.py` | WP1 / C4 | 16 | valid/boundary/invalid/conflicting controls, PAPER; WP1 |
| `tests/test_paper_portfolio_policy_v1_isolation.py` | WP1 / C4 | 6 | serialization, detachment, import isolation; WP1 |
| `tests/test_paper_portfolio_snapshot_v1.py` | WP1 / C4 | 20 | empty/pending/active/partial/terminal, equations, duplicates, locks; WP1 |
| `tests/test_paper_portfolio_snapshot_v1_isolation.py` | WP1 / C4 | 8 | nested detachment, canonical JSON/hash; WP1 |
| `tests/test_paper_capital_reservation_manager.py` | WP2 / C4 | 22 | hold/activate/partial/terminal/reasons/remainder; WP2 |
| `tests/test_paper_capital_reservation_idempotency.py` | WP2 / C4 | 12 | duplicate key/event/fill and conflicts; WP2 |
| `tests/test_paper_portfolio_admission_evaluator.py` | WP2 / C4 | 20 | APPROVED/NO_CAPACITY/BLOCKED and core limits; WP2 |
| `tests/test_paper_portfolio_admission_matrix.py` | WP2 / C4 | 18 | capital/risk/instrument/direction/correlation/expiry/locks; WP2 |
| `tests/test_paper_portfolio_admission_isolation.py` | WP2 / C4 | 6 | no mutation/dependencies/runtime values; WP2 |
| `tests/test_paper_portfolio_aggregation.py` | WP3 / C4 | 18 | realized/unrealized/risk/capital/order independence; WP3 |
| `tests/test_paper_portfolio_exposure_and_locks.py` | WP3 / C4 | 18 | buckets, peak/drawdown/day reset/profit/loss locks; WP3 |
| `tests/test_paper_portfolio_lifecycle_integration.py` | WP3 / C4 | 20 | P6→P8→P7, partial/terminal/failure/duplicates; WP3 |
| `tests/test_paper_portfolio_persistence.py` | WP3 / C4 | 16 | atomic replacement/failures/history/detachment/retry; WP3 |
| `tests/test_paper_portfolio_recovery_reconciliation.py` | WP3 / C4 | 20 | restart, exact authorized reconciliation, ambiguity; WP3 |
| `tests/test_paper_portfolio_concurrent_positions.py` | WP4 / C4 | 18 | multi-index/direction/expiry/contention; WP4 |
| `tests/test_paper_portfolio_restart_replay.py` | WP4 / C4 | 18 | active/partial/terminal/duplicate deterministic replay; WP4 |
| `tests/test_paper_portfolio_fresh_subprocess.py` | WP4 / C4 | 12 | durable cross-process scenarios/canonical output; WP4 |
| `tests/test_paper_portfolio_corruption.py` | WP4 / C4 | 22 | schema/integrity/arithmetic/identity/order/flags; WP4 |
| `tests/test_paper_portfolio_isolation.py` | WP4 / C4 | 10 | PAPER-only/no broker/provider/order/P6/P7 mutation; WP4 |

The helper contains no tests. Parametrization counts only materially distinct behavioral cases; import-only assertions do not satisfy floors.

### Test matrix blueprint

The files above must collectively include these distinct cases:

- **Policy:** every control valid; exact lower/upper boundaries; bool-as-number, NaN/infinity, zero/negative, fraction-over-one, missing profit threshold, threshold while disabled, impossible reserve/deployed combinations; canonical repeated serialization; detached metadata; PAPER/live rejection.
- **Snapshot:** empty portfolio; pending holds only; one OPEN; multiple OPEN; PARTIALLY_EXITED; active plus terminal history; all capital/P&L/equity/return/count/risk equations; negative or unbalanced buckets; duplicate reservation/plan/position/event/fill IDs; exposure mismatch; lock mismatch; stable ordering/JSON/hash; nested caller detachment.
- **Reservation:** admission hold; WAITING no second hold; OPEN activation; duplicate reserve; same key/same payload no-op; same key/different payload block; T1 and T2 proportional releases; T3/full target, stop, cancellation, invalidation, session, expiry, and BLOCKED releases; direct-from-original remainder behavior; restart restoration; exact authorized reconciliation; identity/quantity regressions.
- **Admission:** APPROVED; insufficient available cash; exact/beyond concurrent limit; deployed/committed capital limit; aggregate risk limit; instrument, direction, correlated NIFTY/SENSEX, and expiry limits; minimum reserve; loss/profit lock; malformed/non-READY/live plan; blocked/corrupt snapshot; duplicate request semantics; no caller mutation.
- **Aggregation:** active and terminal realized net P&L; active-only unrealized; no duplicate position or fill; no cost double count; pending and active risk separation; proportional risk; terminal zero; utilization/return; instrument/direction/expiry/correlation buckets; stable `math.fsum` order independence.
- **Lifecycle:** P6 approval to durable hold; P7 WAITING; P7 OPEN activation; T1/T2 partial; T3, stop, invalidation, cancellation, session, expiry terminal; duplicate P7 result; out-of-order transition/fill; hold-persistence failure; P7 activation failure after hold; P8 write failure after P7 OPEN; deterministic restart reconciliation.
- **Concurrency:** two NIFTY positions, NIFTY plus SENSEX, multiple CALL, multiple PUT, opposing economic directions, same/different expiry, supported BANKNIFTY/FINNIFTY grouping, deterministic sequential contention, and last-capacity winner.
- **Daily locks:** below, exactly at, and beyond loss/drawdown threshold; realized plus unrealized basis; intraday peak preservation; profit lock disabled/enabled; new-day explicit reset; new admissions blocked; existing terminal processing allowed; lock replay deterministic.
- **Fresh subprocess:** recover active holds/positions, partial release, terminal release, duplicate event/key, same-key conflict, corruption rejection, canonical stdout, byte-identical persisted retry.
- **Corruption:** capital/P&L/equity/return equation mismatch; negative/nonfinite amount; duplicate identities; missing active reservation; terminal active reservation; unknown P7 position; P6/P7/P8 identity mismatch; quantity/risk/exposure/lock mismatch; sequence/timestamp regression; semantic-key conflict; integrity mismatch; unsupported schema; malformed nested mapping/list/scalar; live flags.
- **Isolation:** no broker/provider/network/order/dashboard/database dependency; no live margin; P6/P7 inputs unchanged; recovered data detached; no runtime IDs/timestamps/random; only repository-backed durable scenarios; no new persistence technology.

## Certification groups

- **WP1:** four policy/snapshot files; floor 50 collected.
- **WP2:** five reservation/admission files; floor 70 collected.
- **WP3:** five aggregation/integration/persistence/recovery files; floor 80 collected.
- **WP4:** five concurrency/replay/subprocess/corruption/isolation files; floor 70 collected.
- **Combined P8:** all 19 P8 test files; floor 270 collected.
- **P6 regression boundary:** all `test_p6*`, integrated-three-target, capital-quantity, cost evidence, option selection, entry/stop/three-target tests used by P8.
- **Full P7 regression boundary:** all certified P7 WP1-WP4, paper-trading adapter/idempotency, persistence/corruption, recovery/subprocess/replay groups.
- **Existing portfolio/account/risk/persistence:** legacy portfolio manager/P&L/performance tests, risk guard, risk engines, repository/journal/database tests.
- **Existing paper engine:** current complete paper-engine/persistence regression group.
- **Compilation/checks:** changed-file `py_compile` during Credits 2-7; repository-wide `compileall` only in Credit 8; `git diff --check` and artifact/status audit every credit.

Do not hard-code expected pass totals before collection exists. Record actual collected and passed counts in each completion report.

## Collection-floor rationale

The floors derive from the manifest's minimum cases: WP1 50 covers two contracts plus invalid/isolation matrices; WP2 70 covers a state machine, durable idempotency semantics, and nine independent admission limits; WP3 80 covers numeric aggregates, locks, seven lifecycle flows, atomic failure boundaries, and reconciliation; WP4 70 covers the combinatorial and corruption/replay boundary. Combined 270 is the sum of group floors, not a separate test-count target. It is high enough to prevent superficial coverage but compact enough to avoid duplicate assertion tests.

## Credit 2 instructions

Create exactly the 12 contract and six pure-service/package files listed above; update only contract/package exports. Implement exact schemas, canonical serialization, detachment, validators, formulas, status vocabulary, pure admission, reservation, aggregation, locks, and reconciliation validation. Use real P6/P7 types and no persistence/runtime/broker/provider imports.

Run changed-module `py_compile` and narrow existing P6/P7 contract import/serialization smoke checks only. Do not create Credit 3 services, tests, run large regressions, commit, or change certified production. Stop only for an actual P6/P7 contract contradiction. Report files, schemas, formulas, smoke results, diff check, and status.

## Credit 3 instructions

Create the repository and five stateful services listed above. Reuse atomic JSON semantics, canonical typed envelope/integrity, strict sequence/idempotency, ordered coordination, restart recovery, and only authorized deterministic reconciliation. Do not modify `PaperTradingEngine`, P6/P7 semantics, legacy databases, or add dependencies.

Run targeted hand-built smoke scenarios with real contracts, changed-file `py_compile`, existing `PaperTradeRepository` atomic tests if shared mechanics were factored (prefer no refactor), diff/status. Do not create the full harness/tests, run full P7/full repository, or commit. Report durable operation and failure/idempotency evidence.

## Credit 4 instructions

Create `tests/p8_portfolio_harness.py` and all 19 exact test files. The replay harness owns all shared fixtures and lifecycle scenarios. Populate meaningful foundations using real contracts/repository, fixed caller IDs/timestamps, balance/exposure/no-change helpers, and subprocess protocol. Do not repair production beyond obvious fixture-discovered defects needed to collect; do not add a second harness.

Run collection per WP and combined P8. Floors need not yet all pass, but collection must reach the manifest floors with no collection errors. Do not run P6/P7/full repository or commit. Report collected counts and known failures by authority area.

## Credit 5 instructions

Close production/fixture defects for policy, snapshot, reservation, admission, aggregation, exposure, reconciliation, determinism, and isolation. Run WP1, WP2, core WP3 aggregation/exposure/reconciliation, then combined relevant tests. Require WP1 >=50, WP2 >=70, selected WP3 collection consistent with manifest, all selected passing. Run changed-file compilation and diff/status. Do not begin subprocess/concurrency expansion, broad regressions, or commit.

## Credit 6 instructions

Close concurrent positions, capacity contention, NIFTY/SENSEX and other supported instruments, same/opposing direction, expiry concentration, partial/all terminal release paths, daily profit/loss locks, restart, fresh subprocess, BLOCKED, corruption, and replay. Reuse the shared harness. Require WP3 >=80 and WP4 >=70, all passing; then combined P8 >=270 passing. Run changed-file compilation and diff/status. Do not run full P6/P7/full repository or commit.

## Credit 7 instructions

Run and repair, in order: WP1, WP2, WP3, WP4; combined P8; P6 regression boundary; full P7 regression boundary; existing portfolio/account/risk/persistence; complete existing paper-engine/persistence. Repair ordinary defects without redesigning certified P6/P7. Re-run affected earlier groups after every production repair. Require all scoped groups green, changed-file compilation, diff check, and no unintended artifacts. Do not run the full repository, repository-wide compilation, commit, or push.

## Credit 8 instructions

Start from all Credit 7 gates green. Run the full repository suite, repair regressions and rerun affected scoped groups plus full suite until green. Run repository-wide Python compilation, documentation/path validation, `git diff --check`, and worktree artifact audit. Update these documents only for factual final manifests/counts. Confirm no broker/provider/order/live behavior and no database technology/dependency was added. Review the exact diff, then create one intentional P8 commit with message `Complete P8 portfolio capital and multi-trade risk`. Do not push. Report commit hash and post-commit clean status.

## Stop conditions

Stop only if certified P6 lacks a unique capital/risk/identity authority, certified P7 cannot yield unique position/P&L/release evidence, atomic repository semantics cannot represent one P8 envelope, safe integration would require changing P6/P7/PaperTradingEngine, or broker/live margin becomes unavoidable. Numeric policy values, naming refinements consistent with this manifest, ordinary code/test defects, and legacy utilities are not blockers.

Every credit must stop before out-of-scope later-credit work. Any same-key/different-payload, corrupt recovery, ambiguous P7 identity, stale sequence, or live flag fails closed and preserves the last coherent persisted snapshot.

## Completion criteria

P8 is complete only when the exact authority separation is preserved; all listed contracts/services exist; capital equations, reservations, admission, exposures, locks, persistence, recovery, reconciliation, replay, detachment, determinism, and PAPER isolation are covered; combined P8 meets its meaningful floor and passes; P6/P7/legacy paper/portfolio/risk/persistence regressions pass; full repository and compilation pass; diff checks and artifact audit pass; documentation matches implementation; one final P8 commit exists; and nothing is pushed.

Credit 1 itself is complete when these two documents are the only changes, `git diff --check` passes, no P8 production implementation exists, P6/P7 are unchanged, no new storage technology/live behavior exists, and no commit/push occurred.
