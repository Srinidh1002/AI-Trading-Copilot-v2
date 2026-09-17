# FinalDecision v1

`services.contracts.final_decision_v1.FinalDecisionV1` is the future canonical decision-output contract. It is a side-effect-free value model: construction, serialization, and adapters never call providers, decision engines, paper trading, broker APIs, or execution services.

## Vocabularies

Actions are only `BUY`, `SELL`, `WAIT`, and `HOLD`. Authorization is separately `BLOCKED`, `ANALYSIS_ONLY`, `PAPER_READY`, `MANUAL_APPROVAL_REQUIRED`, or `AUTHORIZED`. Execution is separately `NOT_REQUESTED`, `REJECTED`, `PENDING`, `SUBMITTED`, `FILLED`, `PARTIALLY_FILLED`, `CANCELLED`, or `FAILED`.

## Fields and validation

Identity contains `final_decision.v1`, decision/snapshot IDs, instrument identity, and timezone-aware creation/market timestamps. Optional option expiry is ISO `YYYY-MM-DD`; strike is positive finite; option type is `CE`/`PE`. Market state and scores are explicit. Every supplied score is finite and in 0..100; absent scores remain absent rather than being invented.

`TradePlanV1` requires exactly one entry price/zone, positive finite stop loss and at least one target, positive finite risk/reward, and non-negative quantity/lots/loss. `RiskSummary` holds validation results without recalculating them. `DataHealthSummary` carries source-health evidence rather than converting it to a recommendation. Reasons, contradictions, blocks, invalidations and warnings are ordered collections.

## Safety invariants

Invalid identity, score, metadata, data health, or rejected risk forces `BLOCKED`. WAIT cannot be authorized, HOLD cannot open a position, and BLOCKED cannot retain submitted/filled execution. Directional paper/manual/authorized states require a valid plan; direction without a plan is only analysis-only or blocked. JSON serialization is deterministic and rejects non-serializable metadata.

## Legacy adapters

`NO_TRADE`, market closed/holiday, stale data, rejected and unsupported values become blocked WAIT. `BUY CE` maps to BUY/CE and `BUY PE` to SELL/PE. `TRADE_READY` becomes manual approval only with a valid directional plan. `TRADE_ALLOWED` becomes paper-ready only with that plan plus verified legacy approval fields; otherwise it blocks. Missing snapshot IDs are explicitly invalid/blocked. Adapters retain unmapped field names as warnings and do not infer missing evidence.

`to_paper_execution_candidate` returns a payload only for valid BUY/SELL decisions that are PAPER_READY or AUTHORIZED, unexecuted, and have a valid plan. It does not submit it.

Examples: valid WAIT is analysis-only/not-requested; blocked BUY is analysis-only or blocked without a plan; paper-ready BUY has a complete plan; HOLD describes an existing position without new execution; malformed legacy data is blocked; a failed execution remains a separate `FAILED` execution status.
