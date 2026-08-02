# Final Trading Copilot Roadmap

> Historical or superseded planning document. The canonical launch roadmap is docs/FINAL_SMALL_CAPITAL_LIVE_ROADMAP.md.

Frozen order for NIFTY/SENSEX Indian index F&O. Tasks 1-9 remain PAPER-only:
`execution_mode="PAPER"`, `live_execution_eligible=False`, and
`broker_order_submission=False`. Task 10 needs separate approval and cannot
toggle the current PAPER runtime.

| Task | Missing work; authoritative existing files | Legacy files not to use | Likely changes and required contracts | Tests/evidence | Dependency; timing |
| --- | --- | --- | --- | --- | --- |
| 1. Audit and architecture freeze | Freeze this roadmap, `FINAL_TRADING_COPILOT_GAP_AUDIT.md`, `TWO_MARKET_RUNTIME_STATUS.md`, and current composition truth. | `market_ranking_engine.py`; legacy dashboard pages. | Documentation only; no contract. | Approved scope; no unsupported claim. | None; Sunday. |
| 2. Analytical engine completion | Complete typed candidate evidence from `technical_intelligence/*`, `multi_timeframe/*`, `market_regime/*`, `option_chain_intelligence/*`, `external_context/*`. | Loose duplicate `services/analysis/*` and root helpers unless adapted with provenance. | `live_analysis_pipeline.py`, `live_option_decision_pipeline.py`; complete candidate-evidence contract if needed. | Deterministic stale/missing/conflict/provenance/no-network fixtures. | 1; Sunday build, market-hours provider check. |
| 3. True two-market decision engine | Replace one-primary scheduling in `certified_runtime_composition.py`; reuse child readers; collect/rank exact NIFTY/SENSEX pair. | Four-market policy/aggregate; dictionary ranking engine. | Composition/cycle source/readers; two-market parent, candidate and ranking contracts. | Exact-once calls, isolation, skew, tie, all-ineligible, selected/rejected rationale. | 2; Sunday build, Monday verify. |
| 4. Capital-aware recommendation and trade plan | Reuse P6/risk to emit CALL/PUT or WAIT/NO_TRADE with entry, SL, T1-T3, quantity, capital, loss, confidence, rationale, invalidation. | Legacy trade recommendation dictionaries. | `certified_p6_input_factory.py`, `p6_planning_stage_executor.py`, `risk/pipeline.py`; selected-market handoff metadata. | Selected-only P6, affordability/no-size, risk, targets, no-trade replay. | 3; Sunday. |
| 5. PAPER lifecycle and monitoring | Compose selected P6 with P7/P8; replace no-position/empty-recovery stubs with discovery/recovery. | Broker/live executors; in-memory `PaperBroker` as runtime authority. | Composition, monitoring/recovery factories, P7/P8 persistence wiring. | HOLD/caution/target/stop/early exit, duplicates, restart, reservations, no broker. | 4; Sunday build, Monday observation. |
| 6. Stable application | Publish pair results/status to immutable read models and render only. | `dashboard/home.py`, `dashboard/live_market_test.py`, direct provider/SQLite paths. | `dashboard_publication/*`, internal pair view, `dashboard/dashboard_v2.py`; no UI trading contract. | Publication freshness/failure, render, no authority imports. | 5; Sunday. |
| 7. Offline PAPER certification | Certify integrated deterministic pair path and read-only reporting. | Network clients and nondeterministic clocks/IDs. | Tests/fixtures; summary fields only if read-only. | Pair matrix, rate limits, malformed/stale data, lifecycle/recovery/idempotency/report tests. | 2-6; Sunday. |
| 8. Monday live-market certification | Controlled paired live PAPER cycles; inspect inner results, not exit code alone. | Live broker submission or manual winner inference. | Runbook/scripts only if evidence is absent; never safety switch. | Freshness/skew, NFO/BFO, cooldown, selection/rejection, no-trade evidence. | 7; market hours. |
| 9. 100-trade-per-market certification | 60 replay plus 40 live-session PAPER trades per market; count no-trade separately. | Profit claims or forced trades. | Evidence/report schemas only if necessary. | 100 NIFTY and 100 SENSEX lifecycle/reconciliation/restart/duplicate/adverse-exit records. | 8; market hours. |
| 10. Small-capital live pilot | Separately approved live design after PAPER evidence. | Current PAPER launcher as a live execution route. | New reviewed live authorization/order boundary. | Broker integration, kill switch, reconciliation, operator approval, adverse-path certification. | 9; market hours and separate approval. |
| 11. Stable small-capital release | Operationalize approved pilot controls and rollback. | Legacy dashboards and autonomous execution without reviewed authority. | Release/runbook/observability assets after Task 10. | Pilot acceptance, rollback rehearsal, ongoing reconciliation, no-profit-guarantee disclosure. | 10; post-pilot. |

## Task 2 internal execution gate

This is an internal subdivision of **Task 2. Analytical engine completion**;
it is not a new roadmap task or phase.

### Task 2A — analytical-engine examination

Task 2A is examination and documentation only. It must create
`docs/TASK2_ANALYTICAL_ENGINE_EXAMINATION.md`, including an authoritative-path
matrix for every analytical capability in Task 2, its inputs, outputs,
provenance, integration seam, and prohibited legacy alternative. **No
production code may be modified during Task 2A.**

### Task 2B — approved authoritative-path integration

Task 2B may begin only after Task 2A has been reviewed and its
authoritative-path matrix accepted. It may implement only the approved
authoritative paths and integration seams; it must not introduce a competing
analytical path, widen the two-market universe, or alter PAPER safety.

## Recommended implementation order inside Tasks 2-7

1. Task 2: lock complete per-market typed evidence and provenance.
2. Task 3: add immutable pair parent/result, deterministic fan-out/join, then
   two-market eligibility/ranking with rejected-market rationale.
3. Task 4: hand only selected eligible evidence to P6; emit pair `NO_TRADE`
   with both reasons when neither qualifies.
4. Task 5: add selected-market IDs, persisted discovery, monitoring and restart.
5. Task 6: publish immutable views and render without provider, broker, trading
   calculation, persistence, or control authority in Streamlit.
6. Task 7: certify offline end-to-end pair replay before Monday observation.

## Completion rules

- Pair contracts accept only NIFTY/NSE/NFO and SENSEX/BSE/BFO.
- Each parent cycle evaluates both exactly once, ranks eligible candidates,
  selects at most one, and records the rejected market’s rationale.
- WAIT/NO_TRADE is valid; never force trades to meet certification counts.
- Tasks 2-9 never submit, modify, cancel, or square-off broker orders.
