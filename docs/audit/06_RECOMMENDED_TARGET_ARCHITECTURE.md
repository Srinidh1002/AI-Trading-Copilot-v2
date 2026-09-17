# Recommended Target Architecture

Classification is a recommendation, not an implementation directive.

```text
Providers -> Validation/Normalization -> MarketSnapshot v1
  -> Analysis engines -> Setup & contradiction gates -> Risk + contract selection
  -> FinalDecision v1 -> immutable audit -> UI / research / paper adapter / controlled execution adapter
```

| Module group | Classification | Rationale |
|---|---|---|
| `services/market/*`, provider adapters | KEEP WITH FIXES | keep replaceable I/O, put validation/normalization at its edge |
| `services/live_analysis_pipeline.py` | KEEP WITH FIXES | clearest analysis orchestration, but must consume/emit contracts |
| `services/live_option_decision_pipeline.py` | MIGRATE | clearest safety gates; make canonical only after contract and entry-point integration |
| `services/core/snapshot_schema.py`, `models/*` | MERGE | candidate typed contracts; consolidate into versioned public schemas |
| decision/risk/confidence/trade duplicates | MERGE | one canonical ownership for each concern |
| `dashboard/` | REWRITE | render `FinalDecision` only; remove DB/orchestration/business side effects |
| paper trading services | MIGRATE | explicit adapter after authorized decision, isolated persistence |
| broker/execution services | KEEP WITH FIXES | controlled adapter behind explicit manual authorization and hard guard |
| root archive wrappers and `archive/` imports | RETIRE / MIGRATE | replace with named delegates, then remove archive dependency |
| broad unreferenced AI/backtesting/security/testing trees | UNKNOWN | verify consumer and product approval before retaining |

`FinalDecision v1` should include identity/timestamps, data health, normalized action (`BUY|SELL|WAIT|HOLD`), authorization status, scores/components, trade plan or null, evidence, contradictions/blockers, invalidation, options interpretation, audit ID and execution state. It must be the sole UI and execution input.
