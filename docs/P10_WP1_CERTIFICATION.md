# P10-WP1 — Audit and Read-Model Boundary Certification

## Scope

P10-WP1 establishes the dashboard authority audit and the immutable,
deterministic, PAPER-only read-model boundary.

It does not migrate the active Streamlit page yet. That work begins in the
later P10 dashboard integration packages.

## Completed deliverables

### Audit

- `docs/P10A_DASHBOARD_AUDIT.md`
- `docs/P10_READ_MODEL_DESIGN.md`

The audit identifies:

- `dashboard/dashboard_v2.py` as the active dashboard
- `dashboard/home.py` as a legacy dashboard
- `dashboard/live_market_test.py` as a diagnostic/legacy dashboard
- direct analysis, market-data, SQLite, health, cache, and legacy PAPER
  dependencies inside the active page
- P7, P8, P9, and runtime statistics as the certified state authorities

### Read-model contracts

The following immutable contracts are public:

- `DashboardMarketStateV1`
- `DashboardCycleViewV1`
- `DashboardPaperPositionViewV1`
- `DashboardPortfolioViewV1`
- `DashboardRunnerHealthV1`
- `DashboardValidationSummaryV1`
- `DashboardSystemSnapshotV1`

### Assembly boundary

The following deterministic assembly types are public:

- `DashboardReadModelAssemblyInputV1`
- `DashboardReadModelAssembler`

The assembler:

- accepts already-projected state only
- preserves caller-supplied identity and time
- sorts markets and positions deterministically
- deduplicates diagnostics deterministically
- applies explicit system-status precedence
- never fetches, analyzes, plans, mutates, or executes

### Projection adapters

The following read-only projections are public:

- `project_cycle_result`
- `project_paper_trade_snapshot`
- `project_portfolio_snapshot`
- `project_runtime_stats`

These adapters consume exact certified P7, P8, P9, and runtime state.

## Locked safety boundary

The `services/dashboard_read_models` package must not import:

- Streamlit
- SQLite
- provider or network clients
- broker clients
- live market engines
- execution managers
- mutable P7/P8/P9 services
- random or UUID generators
- current wall-clock functions

The package may import certified immutable contracts.

## Determinism guarantees

For equivalent semantic input:

- market ordering is stable
- position ordering is stable
- diagnostic ordering is stable
- serialization is stable
- input objects are not mutated
- snapshot identity is caller-supplied
- generated time is caller-supplied
- PAPER-only flags are preserved

## Deferred to later P10 packages

P10-WP1 does not:

- replace `dashboard/dashboard_v2.py`
- remove legacy dashboard pages
- add dashboard operator controls
- add Streamlit position and portfolio pages
- add opportunity or P6 plan UI contracts before their exact source boundary
  is selected
- enable live execution

## Completion gate

P10-WP1 is complete when:

1. all P10-WP1 tests pass
2. the complete P10 focused suite passes
3. `git diff --check` passes
4. the package compiles
5. the full repository suite remains green
6. the completed boundary is committed with a clean working tree
