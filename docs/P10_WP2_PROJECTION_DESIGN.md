# P10-WP2 — Projection Design

## Boundary

Projection adapters are pure functions:

typed certified contract
→ immutable dashboard read model

They may normalize display-safe structure. They must not make trading decisions.

## Planned adapters

- `project_trade_opportunity`
- `project_three_target_trade_plan`
- `project_integrated_trade_plan_result`
- `project_paper_trade_fill`
- `project_paper_trade_position_detail`

## Exact-source rule

Every adapter accepts one exact source contract.

An adapter must reject:

- dictionaries
- `SimpleNamespace`
- legacy dashboard trade dictionaries
- subclasses when exact-type enforcement is required
- partially reconstructed objects

## Missing-data rule

Optional typed source fields remain `None`.

Projection must not substitute:

- zero for missing prices
- zero for missing confidence
- synthetic targets
- synthetic RR
- synthetic contract identity
- current time
- generated UUIDs

## Ordering rule

- targets are always T1, T2, T3
- fills preserve certified source order
- diagnostic tuples preserve source order
- no set-based output ordering
- no sort by profit or status unless the source contract defines it

## P&L rule

Use persisted P7 values.

Priority for detailed position display:

1. latest `PaperTradePnlEvidenceV1`, when present
2. persisted `PaperTradePositionV1` P&L fields
3. `None` when no authoritative evidence exists

The adapter must not sum fill cash effects to recreate P&L.

## Lifecycle rule

Use `PaperTradeLifecycleStateV1.current_state`.

The adapter may classify a state into a display group:

- `PENDING`
- `ACTIVE`
- `TERMINAL`
- `BLOCKED`

This classification is presentation metadata only and must be a fixed mapping
of canonical lifecycle states.

## Safety rule

Every projected plan and position view must carry:

- `execution_mode == "PAPER"`
- `live_execution_eligible is False`

Any source violating these flags must fail closed.

## Streamlit rule

Streamlit components receive read models only.

They must not import:

- P6 evaluators
- P7 evaluators
- P8 admission or portfolio mutation
- P9 orchestration executors
- broker clients
- provider clients
- SQLite
- legacy paper-trade managers
