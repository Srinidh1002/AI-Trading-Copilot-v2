# Task 9 test coverage matrix

Tests were inspected, not executed. Baseline provided by operator: 16,452
passed, 8 warnings.

| Production invariant | Coverage | Representative tests | Gap |
|---|---|---|---|
| PAPER-only launcher/runtime | COVERED | `test_task916_live_paper_certification_launcher`, Task 9 safety tests | Static legacy submit isolation remains review item. |
| Exact two-market handoff | COVERED | `test_task916_cycle_market_evidence_handoff` | Continue live-shape contract cases. |
| Provider incident retention | COVERED | handoff + `test_task924_runtime_rate_limit_reactivation` | Add real captured Mapping/partial failure regression (added in current work). |
| Historical cache/cooldown/gate | COVERED | Task 9.18–9.20 tests, request-gate tests | Legacy direct historical callers are outside certified coverage. |
| Closed-candle boundaries | COVERED | `test_task920_closed_candle_historical_cache` | Holiday calendar integration remains PARTIAL. |
| Angel Greeks/IV enrichment | COVERED | `test_task918_certified_angel_greeks_enrichment` | Live provider availability remains external. |
| Blocker/recovery | COVERED | Task 9.24 blocker/recovery tests | Real operator procedure remains manual. |
| Dashboard non-authority | COVERED | Task 9.17/9.24 dashboard tests | Keep old-snapshot fixtures. |
| `/100` counting exclusions | COVERED | Task 9 counting evaluator/composition tests | Cross-run replay must receive new non-counting tests. |
| Historical replay | MISSING | None | Do not implement until replay authority is designed. |
| Legacy research isolation | COVERED | `test_task924_legacy_research_isolation` | Static Task 9 import-boundary and explicit dashboard entrypoint checks added in R4. |
| Completed-candle compatibility request safety | COVERED | `test_completed_candle_service`, capture-reuse test | Gate/cooldown/no-provider-on-cooldown coverage added in R3. |
| Legacy engines/CLIs | PARTIAL | scattered root tests | Need per-CLI ownership classification. |
