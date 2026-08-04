# P8A Portfolio and capital audit

## Purpose

Define the authoritative, deterministic, PAPER-only boundary for P8 portfolio capital and multi-trade risk. This audit resolves the decisions needed by Credits 2 and 3 without changing certified P6 or P7 behavior.

The audited baseline is branch `p5-8-broader-market-intelligence`, commit `f199c988549dd5637cea1904c132b2b7c6053068` (`Complete P7 paper trade lifecycle and recovery`). The worktree was clean before these documents were created.

## Audit scope

The audit searched definitions, callers, tests, documentation, and persistence paths for portfolio, account, balance, capital, cash, equity, buying power, reservations, deployment, margin, exposure, concentration, P&L, daily loss, drawdown, locks, position tracking, journals, snapshots, recovery, idempotency, event ordering, supported index identities, option direction, expiry, PAPER, and live execution.

The principal inspected paths were:

- P6 final integration and capital contracts under `services/contracts/` and planners under `services/trade_planning/`.
- P7 typed contracts under `services/contracts/paper_*`, lifecycle services under `services/paper_trading/`, and P7 persistence/replay tests.
- `services/portfolio/portfolio_manager.py`, `pnl_tracker.py`, and `performance_analytics.py`.
- `services/analysis/portfolio_risk_engine.py`, `services/paper_trading_risk_guard.py`, `services/risk_engine.py`, `services/options_risk_engine.py`, `services/risk/**`, and their tests.
- `services/paper_trade.py`, `services/paper_pnl_engine.py`, `services/paper_trade_repository.py`, `services/paper_trade_journal.py`, database modules, and paper repositories.
- Runtime configuration, market identity, reporting/export, runner, broker-facing, provider-facing, and archived paths.

No active persisted portfolio-account authority exists. Existing portfolio utilities overlap in name but are not typed, durable P8 authorities.

## Certified P6 authority

The only P6 admission input is `services.contracts.IntegratedThreeTargetTradePlanResultV1`. P8 accepts it only when `status == "READY"`, `execution_mode == "PAPER"`, `live_execution_eligible is False`, and its nested results are coherent. `BLOCKED` and `NO_SIZE` are admission blockers, not plans P8 may resize.

Authoritative mappings are:

| P8 need | Exact P6 authority |
|---|---|
| Integrated identity | `integration_id` |
| Plan identity | `capital_quantity_result.trade_plan_id`; must agree with the canonical/nested plan identities |
| Selected contract identity | `option_contract_selection_result.selection_result_id`; it must equal `capital_quantity_result.option_selection_result_id` |
| Underlying/exchange | `option_contract_selection_result.underlying_symbol`, `exchange` |
| Economic direction | `option_contract_selection_result.direction` (`BULLISH` or `BEARISH`), coherent with the entry/stop/target nested results |
| Option right | selection/result `option_right` or `option_type`, normalized only by the certified P6 contract vocabulary |
| Contract symbol | `option_contract_selection_result.selected_contract.contract.trading_symbol` (also exposed as `selected_trading_symbol`) |
| Strike/expiry/lot | selected contract strike/expiry/lot size (also exposed as `selected_strike`, `selected_expiry`, `selected_lot_size`) |
| Entry | `entry_zone_result.entry_reference_price`, lower/upper zone, chase/limit evidence |
| Stop | `stop_loss_result.stop_loss_price` and typed stop evidence |
| Targets | `three_target_result.target_1`, `target_2`, `target_3` and typed target evidence |
| Lots/quantity | `capital_quantity_result.planned_lot_count`, `lot_size`, `planned_quantity` |
| Target allocation | `target_1_lot_count`, `target_2_lot_count`, `target_3_lot_count`, `runner_lot_count` |
| Premium outlay | `estimated_premium_outlay` |
| Initial risk | `estimated_risk_amount` |
| Trading costs | policy/evidence IDs, calculation mode, component estimates, and `estimated_total_trading_cost` |
| Capital requirement | `estimated_total_capital_requirement` |
| Feasibility | integrated `status`, nested blockers/reasons, and `cost_adjusted_capital_feasible` |

The reservation amount authority is exactly `capital_quantity_result.estimated_total_capital_requirement`. P8 must not rebuild it from premium and costs, substitute legacy `required_capital`, ask a broker for margin, or rerun P6 sizing. READY admission requires this field to be finite, positive, cost-feasible, and at least the certified premium outlay plus certified cost total.

P6 `available_capital`, `deployable_capital`, and `reserved_capital` are per-plan planning inputs/evidence. They are not a shared portfolio balance and do not become P8 state.

## Certified P7 authority

P7 lifecycle authority is `PaperTradeLifecycleStateV1`; position authority is `PaperTradePositionV1`; transition authority is `PaperTradeEntryEvaluationResultV1` or `PaperTradePositionEvaluationResultV1`; P&L delta authority is `PaperTradePnlEvidenceV1`; durable authority is `PaperTradePersistenceSnapshotV1` recovered by `PaperTradeRecoveryService`.

P8 consumes, without recalculation:

- identity: `position_id`, `trade_plan_id`, `integrated_trade_plan_result_id`, `selected_option_contract_id`, lifecycle policy/state IDs;
- contract: market, exchange, underlying, option symbol, economic direction, option type, strike, expiry;
- lifecycle: canonical current/previous state, terminal flag/reason/target, transition sequence and typed timestamps;
- size: initial and remaining lots/quantity and P6 target/runner allocations;
- fills: the entry fill and ordered exit fills, including stable fill IDs, quantities, costs, timestamps, reasons, and cash effects;
- P&L: position `realized_gross_pnl`, `realized_net_pnl`, `unrealized_pnl`, and `total_pnl`, with `PaperTradePnlEvidenceV1` providing before/delta/after evidence, allocated entry costs, exit costs, and quantity coherence;
- observation ordering: latest observation identity/timestamp and lifecycle last-observation evidence;
- persistence/replay: adapter idempotency key and semantic payload hash, event sequence, schema version, SHA-256 integrity hash, and PAPER flags.

`PaperTradePositionV1.estimated_risk_amount` and `estimated_total_capital_requirement` preserve the P6 initial authorities. P8 derives remaining risk and remaining deployed amount by a direct initial-to-remaining quantity ratio; it does not calculate option risk from stop distance or prices.

P7 net realized P&L already accounts for allocated entry cost and exit cost. P8 sums `realized_net_pnl` and never subtracts those costs again.

## Existing account and balance models

`TradingRuntimeConfig.capital` is a validated runtime input and a suitable caller source for initializing starting capital, but it is not a durable account ledger. `RiskPolicyV1.capital_base`, sizing `available_capital`, and P6 canonical `available_capital` are trade-planning/risk inputs, not mutable shared balances.

`database/db_manager.py`, `services/database/database_manager.py`, and the SQLite trade/snapshot/settings/log stores have no typed PAPER portfolio balance, reservation, or event-sequence schema. The checked-in `database/ai_trading.db` is not adopted as P8 authority.

No deposit, withdrawal, transfer, multi-currency, broker cash, buying-power, or multi-account funding transaction authority exists. P8 therefore uses a caller-supplied positive starting capital at creation, persists it immutably for a portfolio lifecycle, and excludes funding transactions.

## Existing portfolio authorities

`services/portfolio/portfolio_manager.py::PortfolioManager` holds process-local dictionaries keyed by symbol and a mutable realized-P&L value. It cannot represent two positions in the same symbol, typed P6/P7 identity, pending holds, costs, event ordering, recovery, or integrity. It remains a legacy compatibility utility.

`services/portfolio/pnl_tracker.py::PnLTracker` and `performance_analytics.py::PerformanceAnalytics` keep mutable closed-trade lists and reporting statistics. They are reporting helpers, not state authorities.

`services/analysis/portfolio_risk_engine.py::analyze_portfolio_risk` accepts an untyped caller snapshot and calculates heuristic exposure, sector concentration, negative-P&L drawdown, and leverage scores. It is an analytical signal only.

Reporting/export modules consume caller data and create no portfolio state. Test data generators and mock broker account information are fixtures, never authority.

## Existing capital reservation behavior

No shared, durable reservation manager exists. P6 capital planning has a per-plan `minimum_reserve_capital` and reports a per-plan `reserved_capital`; this is capacity planning evidence, not an allocation against other plans. Legacy paper trades carry `required_capital`, but no atomic multi-trade hold ledger exists.

P8 must introduce typed reservation records and pending-plan holds over the established JSON persistence style. That is new P8 authority, not a replacement for an active portfolio authority.

## Existing open-position tracking

`PaperTradingEngine` and `PaperTradeRepository` track legacy OPEN/CLOSED trades and remain compatibility boundaries. The P7 typed persistence envelope is the certified source for P8 position reconciliation. `PaperTradeRecoveryService.recover()`/`recover_active()` detects duplicate typed identities and returns detached snapshots.

P8 counts unique P7 `position_id` values whose lifecycle is nonterminal. It does not use symbol-keyed `PortfolioManager.positions`, paper order state, or legacy OPEN/CLOSED alone.

## Existing risk managers

- `PaperTradingRiskGuard` is a fail-closed legacy pre-open guard for maximum OPEN trades, trades per runtime calendar day, realized daily loss, kill switch, and broad duplicate underlying/symbol/token. Reuse only through compatibility: P8 is more precise and must not call it as portfolio authority.
- `services/risk_engine.py` contains legacy per-trade sizing/risk/reward calculations. P6 has superseded it for P8 inputs.
- `services/options_risk_engine.py` calculates per-option liquidity, premium exposure, and warnings from live-like option inputs. It is not aggregate risk authority.
- `services/risk/**` and `RiskPolicyV1` are canonical pre-P6 trade validation/sizing paths. They remain upstream and unchanged.
- `analysis/portfolio_risk_engine.py` is heuristic/untyped and is not used for admission.

P8 policy owns only portfolio-wide limits. It consumes P6 initial risk and P7 remaining quantity rather than executing any existing risk engine.

## Existing P&L aggregators

`PaperPnLEngine` is a deterministic legacy long-option calculator using `Decimal` and two-decimal `ROUND_HALF_UP`, but P7 typed position/P&L evidence is newer and authoritative. P8 must not rerun it.

`PortfolioManager`, `PnLTracker`, and `PerformanceAnalytics` aggregate mutable legacy trades. `PerformanceAnalytics.max_drawdown` is a closed-trade cumulative-realized reporting metric, not the P8 intraday equity drawdown. P8 leaves these APIs unchanged and may later feed reporting through an adapter, never the reverse.

## Existing exposure logic

No typed aggregate instrument, direction, expiry, or NIFTY/SENSEX correlated concentration authority exists. `analysis/portfolio_risk_engine.py` uses invested-capital and sector mappings supplied in an arbitrary snapshot; that vocabulary does not match P6/P7 typed index option evidence.

Canonical instrument identities are supplied by `services/core/market_identity.py`: NIFTY/NSE, BANKNIFTY/NSE, FINNIFTY/NSE, and SENSEX/BSE. P8 uses canonical `underlying_symbol` plus exchange and does not invent aliases.

## Existing daily-loss and drawdown logic

The risk guard compares closed legacy realized P&L with a threshold using the calendar date of a caller/runtime datetime. The legacy risk engine uses caller `daily_pnl`; performance analytics calculates historical closed-trade drawdown. None persists an India trading-day identity or portfolio lock.

P8 therefore requires caller-supplied `trading_day_id` and aware event timestamps. It never derives reset from machine local time. The proposed default timezone label is `Asia/Kolkata`, matching established contracts; the trading-day ID, not timezone calculation, is reset authority.

Daily total P&L is the current trading-day sum of unique P7 position realized net plus unrealized P&L. Daily loss is `max(0, -daily_total_pnl)`. Daily drawdown is `max(0, intraday_peak_equity - total_equity)`, where the peak is persisted and updated monotonically within that trading-day ID. Either configured loss/drawdown threshold locks new admission for the remainder of that day. Existing positions always continue through P7 management and P8 release.

## Existing persistence and recovery

`PaperTradeRepository` is the established durable mechanism: schema-versioned JSON, defensive copies, strict document validation, whole-document atomic temporary-file write, flush/fsync, and `os.replace`. `PaperTradePersistenceService` adds a typed JSON envelope and integrity hash; `PaperTradeRecoveryService` restores typed state and rejects corruption; `PaperTradeReplayCoordinator` applies strict event sequencing and economic no-ops.

The legacy journal is append-oriented trade-event compatibility storage and is not suited to an atomic portfolio snapshot plus reservations. SQLite market/trade stores have unrelated schemas and weaker typed recovery alignment.

Decision: Credit 3 adds `PaperPortfolioRepository`, a portfolio-specific repository using the same JSON/atomic-replace technology and behavior as `PaperTradeRepository`, plus a typed persistence service. It must not subclass or store fake trades in `PaperTradeRepository`, because `trade_id`, OPEN/CLOSED filtering, and trade deletion semantics would mislabel portfolio records. It must not add SQLite tables or a new dependency. One repository document contains all portfolios keyed by `portfolio_id`; one atomic replace is the transaction boundary for a portfolio update.

## Existing idempotency and event ordering

P7 establishes the pattern:

- caller-supplied idempotency keys;
- canonical semantic payload hashes;
- same key/same hash is an economic no-op;
- same key/different hash fails closed;
- caller-supplied IDs and aware timestamps;
- monotonic lifecycle transition and persistence event sequences;
- canonical sorted compact JSON and SHA-256 integrity.

P8 adopts that pattern independently at the portfolio boundary. It stores admission idempotency records and processed P7 event records. A P8 portfolio event is accepted only when `event_sequence == prior + 1`; a referenced P7 transition must not regress and each fill ID may be applied once. Ordering the input collection differently must not change canonical output.

## Duplicate and legacy authorities

| Candidate | Classification | Reason |
|---|---|---|
| `PortfolioManager` | legacy, leave compatible | process-local, symbol-keyed, incomplete |
| `PnLTracker` | legacy reporting | closed-trade mutable statistics |
| `PerformanceAnalytics` | legacy reporting | caller-owned history and different drawdown |
| `analysis/portfolio_risk_engine.py` | unrelated analytical signal | untyped heuristic snapshot |
| `PaperTradingRiskGuard` | reusable through compatibility adapter only | fail-closed precedent, but legacy statuses/day/P&L |
| `risk_engine.py`, `options_risk_engine.py` | upstream/legacy, leave | per-trade calculations; P8 must not resize |
| `PaperTrade`, `PaperTradingEngine` | legacy compatibility authority | certified P7 adapter boundary, not portfolio state |
| P7 typed snapshot/recovery/replay | authoritative and reusable as input | exact lifecycle, P&L, identity, ordering |
| `PaperTradeRepository` mechanics | reuse design, not trade schema | established atomic JSON technology |
| journals and SQLite stores | leave | no coherent typed portfolio transaction |

There are no two equally active incompatible portfolio authorities; the absence of one is why P8 can safely introduce its bounded typed authority.

## Live-execution assumptions

Broker account/margin calls, provider market data, live order placement, order authorization, dashboard state, and runtime clock/ID factories are prohibited dependencies. Legacy broker-facing terminology such as margin, account info, or buying power is not imported into P8.

Every P8 contract requires `execution_mode == "PAPER"` and `live_execution_eligible is False`. Services are pure or repository-local and accept complete typed evidence. A live flag, provider, broker, network object, or order/executor object is rejected or absent by construction.

## Indian F&O PAPER capital assumptions

P8 models long-premium PAPER capacity for the typed P6/P7 index-option path. It uses the P6 cost-adjusted total capital requirement. It does not model broker SPAN/exposure margin, short-option margin, collateral, margin offsets, cross-position netting, peak-margin rules, settlement cash, taxes beyond P6 typed cost evidence, or real exchange/broker availability.

Instrument grouping uses the canonical supported market registry. The special NIFTY/SENSEX concentration rule is deterministic policy, not a claim of measured statistical correlation.

## Authority decisions

1. **Portfolio identity:** caller supplies stable `portfolio_id` and unique `portfolio_snapshot_id`. Version 1 permits multiple PAPER portfolios, but each persistence record is one portfolio identity and one active trading-day snapshot. No user/account model is inferred.
2. **Starting capital:** caller supplies a finite positive float at portfolio creation. It is immutable for that `portfolio_id`; a different amount requires a new portfolio identity. A new day rolls the day baseline/peak but does not change starting capital. Deposits/withdrawals are out of scope.
3. **Reservation amount:** exact P6 `estimated_total_capital_requirement`.
4. **Timing:** APPROVED admission atomically creates a `PENDING_HOLD`; P7 WAITING does not create another hold. Successful P7 OPEN activation converts that hold to `ACTIVE` deployed capital. This two-stage rule prevents oversubscription without calling a plan an open position.
5. **Capital buckets:** `reserved_capital` is the sum of PENDING_HOLD remaining amounts; `deployed_capital` is the sum of ACTIVE remaining amounts; `committed_capital = reserved + deployed`; `available_cash = total_equity - committed_capital`; released capital is audit evidence, not a third current bucket.
6. **Partial release:** target remaining amount is calculated from original amount and P7 remaining quantity, never repeated subtraction: `original_amount * remaining_quantity / initial_quantity`. Release delta is prior remaining minus target remaining. Terminal target is exactly zero, absorbing any floating remainder.
7. **Aggregate risk:** `P6 estimated_risk_amount * P7 remaining_quantity / initial_quantity` for ACTIVE positions. PENDING_HOLD uses full P6 estimated risk for admission contention. Terminal risk is zero.
8. **Portfolio P&L:** sum latest unique P7 positions; realized uses `realized_net_pnl` for active and terminal history, unrealized uses nonterminal positions only, total is their sum. Costs are not reapplied.
9. **Equity:** `starting_capital + cumulative_realized_net_pnl + current_unrealized_pnl`. Reserved/deployed capital does not reduce equity.
10. **Available cash:** `total_equity - reserved_capital - deployed_capital`; negative results are corrupt because admission must preserve the minimum reserve and capacity.
11. **Utilization:** `committed_capital / starting_capital`; starting capital is strictly positive. This stable denominator makes replay/day comparisons deterministic.
12. **Daily loss/drawdown:** total-P&L basis, caller day ID, persisted intraday peak, no runtime reset; threshold crossing latches the loss lock for the day.
13. **Profit lock:** configurable policy-only admission latch. When enabled, reaching `minimum_daily_realized_profit_to_lock` blocks new admissions for the day. It does not trail gains, close positions, or promise a protected profit.
14. **Loss lock:** loss or drawdown threshold latches new-entry blocking. Existing P7 positions remain manageable; reset requires a new caller-supplied day ID.
15. **Direction:** exact economic `BULLISH`/`BEARISH` evidence; CALL/PUT is recorded separately and never used to infer direction.
16. **Instrument exposure:** canonical underlying/exchange bucket. Policy uses remaining aggregate risk, not contract count or broker margin.
17. **NIFTY/SENSEX concentration:** for each economic direction, numerator is combined remaining risk for NIFTY and SENSEX; denominator is policy `maximum_total_portfolio_risk_amount`; compare with `maximum_correlated_index_risk_fraction`.
18. **Expiry concentration:** exact ISO expiry date bucket; metric is remaining aggregate risk divided by maximum total portfolio risk.
19. **Concurrent count:** `active_position_count + pending_plan_count`; both consume `maximum_concurrent_trades`. Snapshot reports both counts separately.
20. **Admission status:** `APPROVED`, `NO_CAPACITY`, `BLOCKED`. NO_CAPACITY is coherent portfolio/policy insufficiency; BLOCKED is malformed/incoherent/PAPER/lock/corruption evidence.
21. **Admission idempotency:** caller key plus SHA-256 of canonical semantic input. Same/same returns the persisted result and snapshot unchanged; same/different returns BLOCKED and writes nothing.
22. **Reservation identity:** caller supplies unique `reservation_id`; record binds exactly one portfolio, admission request, integration ID, plan ID, and later at most one position ID. Those identities are immutable.
23. **Release triggers:** P7 OPEN activates; PARTIALLY_EXITED releases the quantity-ratio delta; CLOSED_TARGET_1/2/3, CLOSED_STOP, CLOSED_INVALIDATED, CLOSED_SESSION, CLOSED_EXPIRY, CANCELLED, and BLOCKED release all remaining capital/risk. WAIT/HOLD with no economic transition is a no-op.
24. **Event ordering:** caller supplies P8 event ID, sequence, idempotency key, semantic hash, and aware timestamp. P7 transition/fill evidence must be newer than stored evidence or an exact duplicate.
25. **Corruption:** fail closed. Unsupported schema, bad integrity, incoherent arithmetic/identity/order/PAPER flags returns/raises controlled corruption codes and leaves the repository unchanged. No silent repair and no automatic file quarantine.
26. **Portfolio return:** P8 may expose `portfolio_return_fraction = total_pnl / starting_capital` because starting capital is now authoritative and positive. This is portfolio return, not per-position return.

Floats remain the contract numeric type to preserve P6/P7. Aggregation uses `math.fsum` over values sorted by stable identity and `math.isclose(rel_tol=1e-9, abs_tol=1e-9)` for validation. No new cent-rounding rule is imposed on certified upstream values. Direct-from-original release formulas and exact terminal zero prevent drift.

## Unresolved product decisions

The following are configurable defaults, not blockers:

- Concrete numeric limits for concurrent trades, deployed capital, aggregate risk, exposure, loss/drawdown, and profit lock belong to caller-created `PaperPortfolioPolicyV1`; no repository evidence justifies global values.
- Profit lock defaults disabled. Product owners may later add trailing/protected-profit semantics only through a versioned policy; V1 merely blocks admission at a realized-profit threshold.
- NIFTY/SENSEX deterministic grouping is mandatory when the policy limit is configured; no live/statistical coefficient is introduced.
- One active trading-day snapshot per portfolio is the V1 operational model. Historical snapshots remain loadable; cross-account funding and cross-day performance ledgers remain out of scope.

These decisions do not alter the contracts' architecture or require P6/P7 changes.

## Reuse/adapt/leave/prohibit matrix

| Component | Decision | P8 use |
|---|---|---|
| `IntegratedThreeTargetTradePlanResultV1` | reuse | sole admission plan input |
| `CapitalQuantityPlanningResultV1` | reuse | capital/risk/size/cost authority |
| P7 typed lifecycle, position, fill, P&L, persistence | reuse | release, aggregate, reconcile evidence |
| `market_identity.py` | reuse | canonical instrument/exchange validation |
| P7 canonical JSON/hash/idempotency conventions | adapt | P8 contracts and durable events |
| `PaperTradeRepository` atomic JSON mechanics | adapt | portfolio-specific repository, same technology |
| Legacy portfolio/P&L/performance utilities | leave | compatibility/reporting only |
| Risk guard and legacy risk engines | leave/adapt only at callers | no P8 authority |
| SQLite trade/snapshot databases and journal | leave | unrelated schemas |
| Broker/provider/order/live modules | prohibit | never imported/called by P8 |
| Dashboard/report state | prohibit as authority | optional future read-only consumers |

## P8 architecture boundary

P6 plans one trade. P8 admits it and owns the pending hold/portfolio ledger. P7 owns waiting/open/partial/terminal position behavior. P8 consumes P7 outcomes to convert/release reservations and recompute portfolio aggregates. P8 never mutates P6/P7 objects, never fabricates a P7 transition, and never blocks safe lifecycle management of an existing P7 position.

The durable unit is a typed portfolio persistence snapshot written atomically. P7 and P8 repositories are not a distributed transaction. The coordinator first proves and durably holds capacity, then invokes/accepts P7 activation, then durably reconciles the portfolio. If activation or the second write fails, recovery sees the pending hold and P7 authority and deterministically reconciles; new admissions remain fail-closed meanwhile.

## P8 handoff

Credit 2 can implement the contracts and pure admission/reservation/aggregation engines from the decisions above. Credit 3 can implement orchestration and persistence using the established atomic JSON pattern. Exact files, schemas, flows, tests, controlled vocabularies, collection floors, and credit gates are specified in `docs/P8_IMPLEMENTATION_PLAN.md`. No further repository-wide authority audit is required unless implementation discovers a direct contradiction in certified P6/P7 behavior.
