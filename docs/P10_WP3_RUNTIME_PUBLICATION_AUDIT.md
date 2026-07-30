# P10-WP3 — Runtime Publication Source Audit

## Objective

Determine the authoritative publication boundary for certified P6/P7 dashboard
views.

This batch is audit-only. It does not modify runtime behavior, orchestration,
Streamlit state, persistence, planning, lifecycle transitions, P&L, or
execution.

## Actual repository paths

The real cycle executor is:

- `services/paper_orchestration/complete_cycle_executor.py`

The real cycle input contract is:

- `services/contracts/paper_orchestration_cycle_input_v1.py`

P10-WP3 must not require the previously assumed alternative filenames.

## Current runtime behavior

`ContinuousPaperTradingRuntime` coordinates:

1. optional startup operation
2. opportunity cycle
3. monitoring cycle
4. wait
5. repeat

The runtime owns:

- `_cycle_lock`
- `_stop_event`
- `_running`
- `_stats`

Its `run_cycle()` executes the injected opportunity and monitoring operations,
records their returned values inside a cycle report, and stores a deep-copied
cycle report at:

- `_stats["last_cycle"]`

Its `get_stats()` returns a deep copy of `_stats`.

## Current runtime result retention

The latest opportunity and monitoring results survive inside:

- `_stats["last_cycle"]["opportunity"]["result"]`
- `_stats["last_cycle"]["monitoring"]["result"]`

The runtime does not currently expose a typed dashboard publication envelope.

The runtime also does not currently provide:

- last-known-good dashboard state
- publication version
- publication timestamp
- stale-state marker
- publication status
- typed opportunity/plan/position properties
- a dedicated publication lock

## P9 cycle input source retention

`PaperOrchestrationCycleInputV1` includes optional source fields:

- `trade_opportunity`
- `integrated_trade_plan_result`
- `p7_persistence_snapshot`
- `p8_persistence_snapshot`

These fields are available at cycle-input construction time.

The semantic identity of these optional sources is included through source
identity and semantic hash extraction.

## P9 cycle result limitation

`PaperOrchestrationCycleResultV1` contains:

- cycle identity
- cycle status
- terminal stage
- stage results
- PAPER actions
- blockers
- warnings
- errors
- duplicate identity
- metadata

It does not expose dedicated typed fields for:

- trade opportunity
- integrated P6 plan
- P7 persistence snapshot
- P8 persistence snapshot

Therefore P10-WP3 must not expect the cycle result alone to reconstruct all
dashboard publication state.

## Complete-cycle executor behavior

`CompletePaperOrchestrationCycleExecutor` obtains typed intermediate results
during one cycle:

- opportunity result
- P6 result
- new-entry lifecycle result
- P7 snapshot through the lifecycle result when available
- P8 snapshot through the lifecycle result when available

The executor currently returns `PaperOrchestrationCycleResultV1`.

Typed intermediate results are used to build stage results but are not exposed
as dedicated fields on the final cycle result.

## Current Streamlit behavior

The active dashboard reads only these session-state keys:

- `dashboard_opportunity_view_v1`
- `dashboard_trade_plan_view_v1`
- `dashboard_paper_position_detail_view_v1`

The dashboard state reader accepts exact read-model values or `None`.

The active dashboard does not currently synchronize from the runtime.

## Publication ownership decision

P10-WP3 should introduce a runtime-independent, thread-safe publication store.

Recommended ownership:

- orchestration/runtime producer publishes
- Streamlit reads
- Streamlit never invokes orchestration
- publication store owns locking
- publication envelope is immutable
- dashboard session state receives a copied snapshot

The store must not be embedded directly in Streamlit session state because the
runtime may execute on another thread.

## Recommended publication point

Publish only after an opportunity operation completes successfully enough to
produce a coherent typed publication candidate.

Publication may occur:

- after a completed opportunity cycle
- after a completed monitoring cycle when a newer P7 snapshot exists

Publication must not occur from a partial invalid object graph.

## Last-known-good policy

A transient failure must not clear a previously valid publication.

Rules:

- successful coherent publication replaces the prior value
- failed projection preserves the prior value
- failed cycle preserves the prior value
- blocked/no-action cycle may update status diagnostics without inventing a
  plan or position
- duplicate-no-change cycle does not replace equivalent publication data
- stale state remains readable and is marked stale
- explicit clearing requires an operator-owned reset path, not an exception

## Staleness policy

Staleness must be evaluated from caller-supplied timestamps.

The store or envelope may carry:

- `published_at`
- `source_updated_at`
- `freshness_status`
- `stale_after_seconds`
- `publication_sequence`

No component may call the wall clock implicitly inside an immutable contract.

A caller-owned clock may be injected into a publication service.

## Concurrency policy

`ContinuousPaperTradingRuntime` already prevents overlapping cycles with
`_cycle_lock`.

That lock does not protect concurrent dashboard reads of publication state.

The publication store therefore needs its own lock covering:

- replace
- read
- reset
- sequence increment

Reads must return immutable values or defensive copies.

## Proposed immutable contracts

### DashboardPublicationEnvelopeV1

Fields:

- `publication_id`
- `publication_sequence`
- `published_at`
- `source_updated_at`
- `publication_status`
- `freshness_status`
- `cycle_result`
- `opportunity`
- `trade_plan`
- `paper_position`
- `blockers`
- `warnings`
- `errors`
- `execution_mode == "PAPER"`
- `live_execution_eligible is False`

### DashboardPublicationSnapshotV1

Store-facing read snapshot containing:

- latest envelope or `None`
- last successful publication time
- last attempted publication time
- last attempt status
- last attempt error
- publication count
- failed attempt count

## Proposed service boundaries

### DashboardPublicationService

Pure projection and validation boundary.

Inputs:

- caller-supplied identity and timestamps
- typed opportunity source
- typed P6 plan source
- typed P7 snapshot source
- optional P9 cycle result

Output:

- immutable `DashboardPublicationEnvelopeV1`

Responsibilities:

- exact-type validation
- call existing projection adapters
- verify coherent identities
- preserve PAPER-only flags
- reject partial invalid publication

It must not:

- execute P6/P7/P8/P9
- read persistence
- mutate runtime
- access Streamlit
- generate wall-clock time
- generate random identity

### DashboardPublicationStore

Thread-safe last-known-good store.

Responsibilities:

- publish immutable envelope
- preserve prior value on failure
- expose current snapshot
- maintain monotonic sequence supplied or validated by caller
- expose attempt diagnostics

It must not:

- project source contracts
- call orchestration
- call Streamlit
- recalculate trading values

### DashboardSessionStateSynchronizer

Presentation boundary.

Responsibilities:

- read a publication snapshot
- write exact read models into the three WP2 state keys
- preserve existing state when no newer valid envelope exists
- surface publication metadata through separate state keys

It must not:

- invoke runtime
- invoke orchestration
- read persistence
- project P6/P7 source contracts

## Batch 1 conclusion

The correct architecture is:

typed orchestration/runtime results
→ publication service
→ immutable publication envelope
→ thread-safe last-known-good store
→ Streamlit session-state synchronizer
→ WP2 renderers

The next implementation batch should add immutable publication contracts only.
