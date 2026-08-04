# P7A Paper-trading audit

## Purpose
Establish a contract-only P7 lifecycle foundation while preserving existing PAPER behavior.

## Repository scope inspected
`services/paper_trading_engine.py`, `services/paper_trade.py`, `services/paper_*`, `services/paper/**`, `services/paper_trading/**`, `services/continuous_paper_trading_runtime.py`, runners, `database/**`, `services/contracts/paper_*`, P6J contracts/integrator, configuration, and corresponding `tests/test_*paper*` suites were inspected.

## Existing paper-trading engines
`services/paper_trading_engine.py::PaperTradingEngine` is the compatibility authority: validated in-memory trades, simulated price updates, stop/target/manual close, optional journal/repository persistence and recovery. `services/paper/paper_trade_engine.py::PaperTradeEngine` and `services/paper/executor.py` are deterministic paper-execution-path components; they are not the P7 lifecycle authority.

## Existing contracts and models
`PaperTrade`, `PaperOrderStateV1`, `PaperExecutionRequestV1`, `PaperExecutionResultV1`, observations, authorization, candidate, and canonical execution result remain existing execution-boundary contracts. P7B contracts are typed lifecycle authority only.

## Existing lifecycle states
Engine trade status is OPEN/CLOSED; order state has CREATED/AUTHORIZED/SUBMITTED/FILLED/REJECTED/BLOCKED/CANCELLED/FAILED. These are compatibility vocabularies, not the new lifecycle vocabulary.

## Existing entry behavior
`PaperTradingEngine.open_trade` validates and opens simulated trades. P7-WP1 adds no entry evaluator.

## Existing stop-loss behavior
`update_price(..., auto_close=True)` delegates simulated stop/target decisions to current trade/P&L components.

## Existing target behavior
Current engine supports legacy target close, not typed three-target partial-exit authority.

## Existing partial-exit behavior
No P7 typed partial lifecycle exists; deferred to WP3.

## Existing P&L behavior
`services/paper_pnl_engine.py::PaperPnLEngine` calculates legacy realized/unrealized P&L; it remains isolated pending WP3.

## Existing persistence and recovery
`PaperTradeJournal`, `PaperTradeRepository`, recovery manager, `database/db_manager.py`, and local `database/ai_trading.db` are existing persistence paths. No persistence changed; compatibility requires WP4 adapter assessment.

## Existing runners and integrations
`PaperPositionLifecycleRunner`, continuous runtime, orchestrator, heartbeat/monitor/recovery modules are current callers around the existing engine.

## Existing PAPER/live safety controls
`TradingRuntimeConfig.real_orders_allowed` is always false; `PaperTradingEngine` documents no broker/order behavior. Existing provider-facing price-provider modules are outside the new contracts.

## Public APIs and callers
Existing public engine API includes open/retrieve/update/close/recover operations. P7B exports are lazy `services.contracts` contracts only.

## Duplicate and legacy implementations
`services/paper_trade.py`, `services/paper_trading/paper_trade_engine.py`, `services/trade/paper_trade_engine.py`, root runners, and `archive/**` overlap; archive modules are legacy, while current execution-pipeline modules are compatibility/duplicate paths.

## P6J-to-paper-trading field mapping
`IntegratedThreeTargetTradePlanResultV1` maps by IDs and precomputed nested results: entry-zone, stop, targets, selected contract, lots/quantity/allocation, costs, and status. WP4 adapts READY plans without recalculation; BLOCKED/NO_SIZE map to BLOCKED lifecycle intake.

## Authority decisions
`PaperTradingEngine` remains compatibility authority; `PaperTradeLifecyclePolicyV1` and `PaperTradeLifecycleStateV1` are new typed authority. WP4 owns the adapter. Existing database models are not yet approved to persist typed state. Legacy names need mapping. P&L stays isolated. Existing engine does not place live orders, does not fetch market data internally, and prevents duplicate trade IDs.

## Compatibility risks
Legacy OPEN/CLOSED and paper-order FILLED are not equivalent to typed lifecycle states; database schema/recovery and idempotency adaptation are deferred.

## Reuse decisions
Reuse engine as-is, PAPER controls, repository/journal interfaces, and duplicate-ID guard. Do not reuse legacy status vocabulary as canonical.

## Deferred decisions
Entry observation/fill, valuation, partial exits, P&L, persistence writes, recovery serialization, and adapter behavior.

## P7 implementation boundaries
WP1 is pure contracts; WP2 entry; WP3 position/partial/P&L; WP4 adapter/persistence/replay.

## P7-WP2 handoff
Consume P6J READY plans and P7B policy/state; provide observation/fill/position contracts and an entry evaluator only.
