# P10 — Dashboard Read-Model Design

## Objective

Create a deterministic, immutable, PAPER-only projection layer between the
certified P5–P9 authorities and Streamlit.

The read-model layer is not a trading authority. It does not fetch data,
execute analysis, plan trades, admit trades, mutate positions, update
portfolios, or control broker execution.

## Package boundary

Proposed package:

`services/dashboard_read_models/`

The package must not import:

- `streamlit`
- provider or network clients
- broker clients
- order executors or order managers
- legacy trade engines
- mutable PAPER trade managers
- `sqlite3`
- random or UUID generation
- current wall-clock functions

All timestamps and identities must come from caller-supplied typed state.

## Proposed contracts

### `DashboardMarketStateV1`

Fields:

- market
- exchange
- symbol
- observed_at
- received_at
- market_status
- data_status
- freshness_status
- ltp
- open
- high
- low
- close
- volume
- warnings
- blockers
- provenance
- execution_mode
- live_execution_eligible

### `DashboardCycleViewV1`

Fields:

- cycle_result_id
- cycle_id
- cycle_status
- terminal_stage
- started_at
- completed_at
- stage_statuses
- paper_actions
- blockers
- warnings
- errors
- duplicate_of_cycle_result_id
- execution_mode
- live_execution_eligible

### `DashboardOpportunityViewV1`

Fields:

- opportunity_id
- market
- direction
- eligibility
- confidence
- regime
- selected
- blockers
- warnings
- source_timestamp

This contract must be projected from typed opportunity state. It must not be
reconstructed from legacy dashboard dictionaries.

### `DashboardTradePlanViewV1`

Fields:

- trade_plan_id
- opportunity_id
- market
- instrument
- option_type
- strike
- expiry
- direction
- entry_lower
- entry_upper
- stop_loss
- target_1
- target_2
- target_3
- lots
- quantity
- capital_required
- maximum_loss
- reward_risk_by_target
- status
- blockers
- warnings
- execution_mode
- live_execution_eligible

### `DashboardPaperPositionViewV1`

Fields:

- paper_trade_id
- trade_plan_id
- position_id
- market
- instrument
- lifecycle_state
- entry_price
- entry_timestamp
- initial_lots
- remaining_lots
- initial_quantity
- remaining_quantity
- stop_loss
- target_1
- target_2
- target_3
- completed_targets
- realized_net_pnl
- unrealized_pnl
- total_pnl
- latest_observation_at
- exit_records
- blockers
- warnings
- event_sequence
- execution_mode
- live_execution_eligible

### `DashboardPortfolioViewV1`

Fields:

- portfolio_id
- trading_day_id
- starting_capital
- available_cash
- reserved_capital
- deployed_capital
- committed_capital
- realized_net_pnl
- unrealized_pnl
- total_pnl
- total_equity
- capital_utilization_fraction
- open_position_count
- pending_plan_count
- concurrent_trade_count
- aggregate_active_risk
- aggregate_pending_risk
- aggregate_committed_risk
- directional_exposure
- instrument_exposure
- expiry_exposure
- lock_state
- blockers
- warnings
- updated_at
- event_sequence
- execution_mode
- live_execution_eligible

### `DashboardRunnerHealthV1`

Fields:

- running
- stop_requested
- interrupted
- startup_status
- startup_error
- cycles_started
- cycles_completed
- cycles_with_errors
- opportunity_successes
- opportunity_failures
- monitoring_successes
- monitoring_failures
- last_cycle_status
- last_cycle_number
- last_cycle_duration_seconds
- warnings
- errors
- execution_mode
- live_execution_eligible

### `DashboardValidationSummaryV1`

Fields:

- completed_trade_count
- winning_trade_count
- losing_trade_count
- breakeven_trade_count
- gross_pnl
- net_pnl
- win_rate_fraction
- average_win
- average_loss
- profit_factor
- maximum_win
- maximum_loss
- data_status
- warnings

This must be calculated deterministically from typed P7 snapshots, never from
the legacy mutable trade manager.

### `DashboardSystemSnapshotV1`

Fields:

- snapshot_id
- generated_at
- market_states
- latest_cycle
- opportunity
- trade_plan
- positions
- portfolio
- runner_health
- validation_summary
- system_status
- blockers
- warnings
- errors
- execution_mode
- live_execution_eligible
- schema_version

`snapshot_id` and `generated_at` must be supplied by the caller.

## Assembly service

Proposed service:

`DashboardReadModelAssembler`

Injected inputs:

- market-state source
- latest-cycle source
- opportunity source
- P6 plan source
- P7 persistence reader
- P8 persistence reader
- runtime-stats source

Responsibilities:

1. validate exact input types
2. project each typed source exactly once
3. preserve source timestamps and identities
4. aggregate warnings, blockers, and errors deterministically
5. preserve missing state explicitly
6. return one immutable `DashboardSystemSnapshotV1`

It must not:

- call providers
- call canonical analysis
- calculate trade decisions
- mutate persistence
- invoke runtime operations
- infer live eligibility
- create trading timestamps

## Status precedence

Recommended system status precedence:

`ERROR`
→ `BLOCKED`
→ `DEGRADED`
→ `READY`
→ `NO_DATA`

The exact constants will be finalized in the contract batch.

## Determinism requirements

- exact dataclass types
- frozen and slotted contracts
- tuple-based collections
- JSON-safe metadata
- stable ordering
- no input mutation
- stable serialization
- caller-supplied time
- caller-supplied identity
- PAPER-only flags enforced
- no hidden provider access

## Streamlit integration target

After P10 integration, `dashboard/dashboard_v2.py` should:

1. request one `DashboardSystemSnapshotV1`
2. render its sections
3. issue explicit operator commands through a separate control boundary
4. never invoke analysis or persistence mutation directly

## P10-WP1 next implementation sequence

1. immutable read-model contracts
2. pure projection functions
3. read-model assembler
4. persistence/runtime adapters
5. active dashboard migration
6. headless import and PAPER-safety certification
