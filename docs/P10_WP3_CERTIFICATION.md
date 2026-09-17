# P10-WP3 — Runtime Publication Certification

## Scope

P10-WP3 connects authoritative PAPER runtime state to the certified WP2
dashboard read models without allowing Streamlit to execute trading logic.

## Implemented path

P9 opportunity or monitoring cycle
→ runtime publication producer
→ immutable publication envelope
→ thread-safe last-known-good store
→ process-local read-only store registration
→ dashboard session-state synchronizer
→ WP2 plan and position renderers

## Contracts and services

- `DashboardPublicationBuildInputV1`
- `DashboardPublicationEnvelopeV1`
- `DashboardPublicationSnapshotV1`
- `DashboardPublicationService`
- `DashboardPublicationStore`
- `DashboardRuntimePublicationProducer`

## Runtime integration

`ContinuousPaperOrchestrationRuntimeAdapter` optionally accepts a publication
producer and publication store.

They must be configured together.

When configured:

- opportunity results are offered to the producer
- monitoring results are offered to the producer
- the store is registered for read-only dashboard access
- the adapter exposes `get_dashboard_publication_snapshot()`

Existing runtime construction remains valid when publication is not configured.

## Dashboard integration

The active dashboard performs this order:

1. read the registered immutable publication snapshot
2. synchronize only a newer publication sequence into session state
3. read exact WP2 read models from session state
4. render the certified plan and position dashboard

The dashboard does not:

- invoke P6 planning
- invoke P7 lifecycle logic
- invoke P8 portfolio logic
- invoke P9 orchestration
- read persistence
- calculate P&L
- generate trade identities
- enable LIVE execution

## Last-known-good behavior

- failed runtime publication attempts preserve prior state
- failed cycles preserve prior state
- empty publication state does not clear session state
- duplicate-no-change cycles do not replace state
- older publication sequences do not replace state
- explicit reset remains separate from transient failure

## Concurrency

The publication store owns an `RLock`.

The registration boundary owns a separate `RLock`.

The registry exposes only immutable snapshots, never mutable store internals.

## Safety

- PAPER-only
- no broker order placement
- no provider acquisition
- no hidden wall-clock generation
- no hidden UUID generation
- no planning recalculation
- no lifecycle mutation
- no persistence mutation from Streamlit
- no partial invalid publication replacement

## Completion gate

P10-WP3 is complete when:

1. all focused P10 tests pass
2. `git diff --check` passes
3. the changed files compile
4. the full repository suite passes
5. the package is committed
6. the working tree is clean
