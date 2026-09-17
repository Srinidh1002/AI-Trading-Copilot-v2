# R1–R8 repository readiness audit

Audit date: 2026-08-03. Scope is static repository inspection only; no provider, broker, canary, persistence, or full-suite action was performed. Baseline inspected: `p10-two-market-weekend-readiness`, HEAD `77e10f9` (working tree contains the user’s unstaged Task 2E3 work plus `artifacts/canary/`).

## 1. Executive verdict

R1–R8 foundations are extensive, but the central issue is connection and operational proof, not a shortage of contracts. The repository is **not ready to start official Task 6 counting**: the authoritative two-market certified decision runtime is present, while planning/lifecycle/dashboard/report/prediction paths are spread across compositions and several need an explicit continuously scheduled, persisted, read-model-published connection. Largest blockers: live VIX previous-close/session proof; authoritative external-context sources; a connected automated lifecycle/monitor loop; canonical prediction-to-outcome ledger; and end-to-end reporting/reconciliation proof.

## 2. Repository architecture map

`CertifiedLiveProviderReaders` → `CertifiedLiveAnalysisAuthority` → `run_certified_two_market_parent_runtime` (`services/paper_orchestration/certified_two_market_parent_runtime.py`) → `rank_two_market_candidates` → selected-market bridge/planning contracts → executable PAPER plan/lifecycle handoff → dashboard publication/read models.

Broken/unverified links: real-session VIX and external-context authority; selected-plan-to-continuous lifecycle runtime; prediction/outcome canonical persistence; dashboard visible application wiring; scheduled monitoring/recovery proof.

## 3. R1–R8 readiness matrix

| Requirement ID | Requirement | Status | Production evidence | Test evidence | Current caller/runtime | Missing work | Live proof required | Recommended action |
|---|---|---|---|---|---|---|---|---|
| R1A | VIX market-hours proof | REQUIRES_LIVE_PROOF | `india_vix_normalizer.py`, `india_vix_capture_result_v1.py` | `test_capture_india_vix_provider_contract_cli.py` | capture diagnostics | exchange-session quote proof | yes | bounded live-hours rehearsal |
| R1B | VIX previous close | PARTIAL | `india_vix_normalizer.py`, `india_vix_regime_policy_v1.py` | contract tests | no proven parent runtime authority | prior-session provenance/calendar proof | yes | implement/certify policy |
| R1C | typed VIX path | COMPLETE_BUT_UNCONNECTED | `india_vix_capture_result_v1.py`, `shared_broader_market_context.py` | VIX/capture tests | reader shared context | prove candidate/regime runtime connection | yes | connect/trace once |
| R1D | external context | PARTIAL | `external_market_context_result_v1.py`, flow/global/breadth contracts | fixtures | shared context projection | authoritative feeds/freshness/dashboard | yes | source authority adapter |
| R1E | live candidate evidence | COMPLETE_AND_CONNECTED | `live_market_candidate_evaluator.py`, `live_canonical_evidence_engines.py` | evaluator/seam tests | certified reader/runtime | live proof only | yes | session certification |
| R2A | two-market assembly | COMPLETE_AND_CONNECTED | `certified_two_market_parent_runtime.py` | `test_certified_two_market_parent_runtime.py` | certified runtime composition | production entry-point selection | yes | use as authority |
| R2B | decision quality | COMPLETE_AND_CONNECTED | ranker/action/explanation modules | ranker/action/explanation tests | parent runtime | policy-version consolidation | no | retain authority |
| R2C | decision persistence | PARTIAL | `market_cycle_journal.py`, dashboard publication store | persistence tests | not proven parent-runtime write | immutable parent/children/explanation record | no | narrow journal adapter |
| R3A | selected contract authority | COMPLETE_BUT_UNCONNECTED | option selection/ranking contracts, P6 factories | certified P6 tests | planning bridge candidates | prove current runtime invokes it | yes | connect selected bridge |
| R3B | capital/risk authority | PARTIAL | `capital_risk_authority_v1.py`, capital planning contracts | capital tests | caller-supplied composition | deployed capital/daily-loss authoritative source | no | policy/config adapter |
| R3C | complete planning runtime | COMPLETE_BUT_UNCONNECTED | executable plan contracts, capital-safe runtime | Task 5 tests | not proven two-market runtime caller | one connected orchestration call | yes | integrate after decision |
| R4A | portfolio admission | COMPLETE_BUT_UNCONNECTED | `paper_entry_admission_v1.py`, reservations | lifecycle tests | compatibility handoff | production runtime caller | no | lifecycle composition |
| R4B | simulated entry | PARTIAL | entry observation/evaluation contracts | lifecycle certification | continuous runtime modules | plan-to-open persistence connection | yes | PAPER rehearsal |
| R4C | monitoring | PARTIAL | `continuous_paper_trading_runtime.py` | continuous runtime tests | scheduler not established | durable cadence/loop ownership | yes | scheduled runtime |
| R4D | reconciliation | PARTIAL | active position/reservation/execution contracts | lifecycle tests | repositories unclear | final capital/P&L reconciliation | yes | recovery/reconcile service |
| R4E | restart recovery | REQUIRES_LIVE_PROOF | continuous runtime recovery modules | startup recovery tests | not session-proven | restart/duplicate proof | yes | supervised restart rehearsal |
| R4F | dashboard | COMPLETE_BUT_UNCONNECTED | dashboard publication/read-model modules | dashboard tests | Streamlit visibility not proven | visible composition/refresh safety | no | publish authoritative snapshots |
| R5 | prediction ledger | PARTIAL | `market_cycle_journal.py`, audit contracts | audit/journal tests | no canonical two-child outcome ledger | immutable prediction/outcome linkage | no | canonical ledger contract |
| R6 | outcome evaluator | PARTIAL | lifecycle/replay result contracts | replay/lifecycle tests | no unified prediction evaluator | WAIT/NO_TRADE outcomes, exactly once | yes | outcome authority |
| R7A | daily report | PARTIAL | `daily_research_report.py` | daily report tests | research runner | lifecycle/outcome reconciliation | no | report adapter |
| R7B | weekly report | LEGACY_ONLY | cross-session research modules | cross-session tests | research path | certified journal aggregation | no | reuse metrics selectively |
| R7C | monthly report | MISSING | no canonical monthly outcome report found | — | — | aggregation/calibration | no | build after R5/R6 |
| R7D | dashboard reporting | PARTIAL | dashboard read models/publication | dashboard tests | visible app unproven | official counters/reports | no | dashboard composition |
| R8 | pre-certification gate | PARTIAL | replay/certification runners, `paper_preflight.ps1`, canaries | safety/certification tests | separate utilities | official start marker/isolation/EOD process | yes | one gate runner |

## 4. Detailed R1 findings

The VIX path has typed capture/normalization (`services/contracts/india_vix_capture_result_v1.py`, `services/analysis/india_vix_normalizer.py`) and a capture script (`scripts/capture_india_vix_provider_contract.py`), but static inspection cannot prove market-hours timestamp freshness or previous-close provenance. External context has typed contracts (`external_market_context_result_v1.py`, `institutional_flow_context_result_v1.py`, `global_market_context_result_v1.py`, `market_breadth_evidence_v1.py`) but no inspected authoritative provider composition. Candidate evidence is strongest: `evaluate_live_market_candidate` and `build_live_canonical_evidence` retain typed canonical components, contributions, ledger, blockers and timestamps.

## 5. Detailed R2 findings

`run_certified_two_market_parent_runtime` validates exact NIFTY/SENSEX child cycles, uses `CertifiedLiveDataAuthority`, `CertifiedSessionAuthority`, `CertifiedLiveAnalysisAuthority`, and calls `run_two_market_parent_cycle`. Ranking is authoritative in `services/analysis/two_market_decision_ranker.py`; child/parent explanations are `market_decision_explanation.py` and `two_market_decision_explanation.py`. Persistence is not demonstrated at this runtime boundary.

## 6. Detailed R3 findings

Task 3–5 contracts exist (`option_contract_selection_*`, `capital_risk_authority_v1.py`, `executable_paper_trade_plan_result_v1.py`) and recent commits support planning/handoff. Evidence of a single caller from the certified parent decision through all planning stages was not established by static inspection; treat it as COMPLETE_BUT_UNCONNECTED until composition evidence is traced.

## 7. Detailed R4 findings

Portfolio/lifecycle contracts include `active_paper_position_v1.py`, `paper_capital_reservation_v1.py`, `paper_entry_admission_v1.py`, and execution contracts. `services/continuous_paper_trading_runtime.py` plus `tests/test_continuous_paper_trading_runtime.py` and startup-recovery tests provide capability, but static inspection cannot prove a continuously owned scheduler, restart behavior with real persisted state, or dashboard publication.

## 8. Detailed R5 findings

`services/market_cycle_journal.py` and `audit_event_v1.py` are reusable journal/audit foundations. No inspected immutable canonical record links each NIFTY/SENSEX prediction, parent selection, plan, and eventual normalized outcome exactly once.

## 9. Detailed R6 findings

Replay and lifecycle results (`paper_execution_replay_result_v1.py`, lifecycle certification tests) cover fragments. A single automatic evaluator for all requested classifications, including `NO_TRADE_CORRECT` and `NO_TRADE_MISSED_MOVE`, was not identified.

## 10. Detailed R7 findings

Daily research reports/runners and cross-session research exist, but they are not proven to aggregate the authoritative prediction/outcome/lifecycle ledger. Monthly risk-adjusted/calibration reporting is missing.

## 11. Detailed R8 findings

Certification/replay runners, `scripts/paper_preflight.ps1`, PAPER safety tests and Task 8 canaries exist. An official isolated-count start marker, inclusion/exclusion policy, EOD reconciliation and daily certification record remain partial/requires-live-proof.

## 12. Duplicate and legacy implementation map

Competing areas: `services/canonical/*`, `services/decision/*`, older market engines, and certified `services/paper_orchestration/*`. Retain certified two-market runtime plus typed analysis/ranker/action/explanation as authority. Treat `continuous_paper_trading_runtime.py`, research runners, and legacy canonical trade plans as reusable adapters until explicitly connected.

## 13. Placeholder/fabricated-data findings

**HIGH:** certification factory `services/certification/task2_decision_fixture_factory.py` imports test fixture builders; this is provider-free certification-only and must never be a live runtime dependency. **MEDIUM:** tests/fixtures contain static prices/confidence; exclude from runtime authority. **MEDIUM:** inspect legacy `services/analysis/vix_engine.py`, news/AI engines, and canonical modules before connecting; their presence is not authority. No executed unsafe path was found.

## 14. Unconnected production-capable modules

`capital_safe_recommendation_runtime.py`, lifecycle admission/execution modules, dashboard publication/read models, daily reports, and recovery runtime each need an explicit caller from the selected two-market parent result, persistent audit record, and read-only publication adapter.

## 15. Persistence and reporting inventory

Inventory: `market_cycle_journal.py`; database support (`database.py`); dashboard publication store/registry; paper reservation/execution/position contracts; audit events/sinks; daily/cross-session research report utilities. Authoritative persistence for the new parent decision through outcome is not proven; dashboard publication is not equivalent to durable audit persistence.

## 16. Dashboard readiness inventory

`services/dashboard_read_models/*` and `services/dashboard_publication/*` expose typed views for cycle, two-market runtime, plan, position, fills and system health. Tests exist (`test_certified_dashboard_composition.py`, `test_dashboard_operator_integration.py`). Visible Streamlit wiring and refresh isolation remain unproven.

## 17. PAPER safety audit

PAPER-only controls are widespread in exact contracts (`live_execution_eligible=False`, `broker_order_submission=False`) and safety tests include `test_certified_paper_runtime_safety.py`. Broker-capable code exists in `services/broker/angel_client.py`; `place_order`/`submit_order` search results must remain outside certified runtime. Before official operation, enforce import/caller graph guard from all official entry points.

## 18. What static inspection cannot prove

Live VIX freshness/previous close, provider schema behavior, market session, monitoring continuity, restart recovery against real stores, dashboard refresh behavior, EOD reconciliation, and full-session duplicate prevention require controlled PAPER market-hours proof.

## 19. Corrected remaining implementation plan

| Task | Purpose | Reuse / likely changes | Tests / exit | Size / live hours |
|---|---|---|---|---|
| A | R1 evidence authority | VIX/external context contracts, readers, certified composition | stale/holiday/provenance + market-hours proof | Codex + live |
| B | Connect decision persistence + selected planning | parent runtime, bridge, journals, P6/P5 runtimes | exactly-once parent→plan audit | Codex, then live |
| C | Connect lifecycle scheduler/recovery | continuous runtime, reservations, positions | restart/EOD/reconciliation rehearsal | manual-sized + live |
| D | Canonical prediction/outcome ledger | journal/audit/lifecycle results | exactly-once classifications | Codex |
| E | Reports/dashboard publication | report runners/read models/publication | reconciled daily/weekly/monthly visible views | Codex + manual review |
| F | Official pre-certification gate | preflight/certification runners | isolated marker, inclusion rules, rehearsal | manual-sized + live |

## 20. Official Task 6 start checklist

- [ ] R1 VIX/external evidence market-hours proof complete.
- [ ] Parent decision → plan → lifecycle persistence connected exactly once.
- [ ] Scheduler/recovery/EOD rehearsal complete.
- [ ] Prediction/outcome ledger and inclusion rules accepted.
- [ ] Dashboard/reports reconcile with persistence.
- [ ] PAPER route guard and provider-read-only guard tested from entry point.
- [ ] Isolated official start marker and empty counters recorded.
- [ ] Full suite and focused certification gates pass.

## 21. Recommended immediate next task

**A — Authoritative India VIX previous-close and market-hours evidence adapter.** It is bounded, blocks R1 authority, and can be implemented without altering planning/lifecycle behavior; the final proof requires one supervised PAPER market-hours capture.

Console summary: readiness **42%**; COMPLETE_AND_CONNECTED **3**; COMPLETE_BUT_UNCONNECTED **4**; PARTIAL **12**; MISSING **2**; REQUIRES_LIVE_PROOF **3**. Top blockers: VIX authority, external context authority, parent→lifecycle connection, prediction/outcome ledger, continuous recovery/reconciliation. Report: `docs/audits/r1_r8_repository_readiness_audit.md`.
