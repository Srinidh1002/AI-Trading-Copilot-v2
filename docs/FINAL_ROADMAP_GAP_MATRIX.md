# Frozen Roadmap Gap Matrix

Status vocabulary: COMPLETE, PARTIAL, BLOCKED, MISSING, LEGACY_ONLY,
NOT_APPLICABLE. This matrix assigns all future prerequisite work to the eight
frozen roadmap tasks.

| Roadmap task | Requirement | Existing implementation | Status | Reusable files/contracts | Missing work | Dependency | Acceptance evidence | Planned slice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Live index/candle/options evidence | Angel readers and normalizers | COMPLETE | `certified_live_provider_readers.py`, `angel_live_observation_normalizer.py` | no Task 1 blocker; unavailable evidence remains explicit | none | source/freshness evidence | 1A–1D1 |
| 1 | India VIX and optional external context | certified shared VIX and shared typed external projections wired into both child regime evaluations | COMPLETE | `IndiaVixCaptureResultV1`, `ExternalMarketContextResultV1`, shared parent context | approved source adapters remain optional improvements; no unapproved provider is required | none | parent-only typed unavailable/ready evidence, exact terminal-component attribution, provider-call count zero | 1C/1D1 |
| 2 | Fourteen-pillar evidence | typed P5 engines, Task 2A provenance, and Task 2B shadow confidence ledger | PARTIAL | `technical_intelligence`, `option_chain_intelligence`, `market_analysis_pillar_contribution_v1`, `market_analysis_confidence_ledger_v1` | policy-approved confidence replacement remains pending | 1 | ordered contribution and shadow-ledger matrix | 2A/2B evidence closure |
| 2 | Two-market selection | parent coordinator/canary and typed child/parent explanations | PARTIAL | `two_market_parent_cycle_coordinator.py`, `pre_entry_market_action_v1`, `market_decision_explanation_v1` | Task 2E2/2E3 certification composer and matrix remain pending | 1, 2A–2E1 | validated parent reasoning | 2E2 certification result |
| 3 | Capital/affordability/quantity | typed P6 and risk pipeline | PARTIAL | `capital_quantity_planning_input_v1.py`, `risk/pipeline.py`, `position_sizing.py` | selected parent to P6 handoff | 2 | capital bounds and no-size result | 3A selected handoff |
| 3 | Option/expiry/strike/liquidity | ranking/selection contracts | PARTIAL | `option_contract_ranking_*`, `option_contract_selection_*` | certified live selected-contract evidence | 1,2 | NFO/BFO contract selection | 3B option evidence |
| 3 | Entry/SL/T1/T2/T3 | P6 evaluators | PARTIAL | `entry_zone_evaluator.py`, `stop_loss_evaluator.py`, `three_target_trade_plan_integrator.py` | integrated selected-only plan | 3A | plan or fail-closed NO_TRADE | 3C integrated plan |
| 4 | PAPER intent/fill/open persistence | P7/P8 services | PARTIAL | `paper_trade_*`, repositories, `paper_portfolio/*` | certified runtime composition wiring | 3 | idempotent persisted entry | 4A lifecycle handoff |
| 4 | Monitoring/HOLD/targets/stops/EXIT | position evaluator and appliers | PARTIAL | `paper_trade_position_evaluator.py`, target/stop/terminal appliers | active-position discovery in runtime | 4A | monitored transition matrix | 4B monitoring/recovery |
| 4 | Restart/reconciliation | recovery and repositories | PARTIAL | recovery services, JSON repositories | runtime discovery/reconciliation proof | 4A | restart/idempotency evidence | 4C recovery certification |
| 5 | Prediction/outcome journal | audit/journal/session services | PARTIAL | `paper_orchestration_journal.py`, `audit_event_v1.py`, `session_manifest.py` | immutable recommendation/outcome linkage | 3,4 | unique IDs and final marks | 5A prediction journal |
| 5 | Reports | summaries/research reports | PARTIAL | `summarize_paper_runtime.py`, `session_journal_analytics.py`, report services | reconciled daily/weekly/monthly metrics | 5A | report-to-journal reconciliation | 5B reporting |
| 5 | Dashboard visibility | read models/publication/dashboard | PARTIAL | `dashboard_publication/*`, `dashboard_v2.py`, `operator_dashboard.py` | complete position/report projection; refresh proof | 4,5 | read-only UI tests | 5C dashboard projection |
| 6 | 100+100 real-time PAPER | Task 8 canary and rules | MISSING | Task 8 canary, journals, lifecycle | controlled session and counters | 1–5 | this task's completion gate | continuous Task 6 |
| 7 | LIVE order/safety boundary | PAPER safety guards only | MISSING | `certified_runtime_safety.py`, broker abstractions | reviewed separate LIVE authority | 6 | adverse-path safety certification | 7A safety design |
| 8 | Supervised launch | no accepted LIVE pilot | MISSING | runbooks/operator controls | pilot, rollback, review | 7 | supervised acceptance | 8A pilot |

## Detailed audit findings for Tasks 3–6

Task 3 components are typed and tested but not completely composed for the
selected two-market parent: P6 planning factories/executor, option ranking and
selection, risk pipeline, capital quantity, entry, stop, and three-target
integrator are reusable. Legacy mapping-based planners are compatibility-only.

Task 4 has PAPER-only contracts and tested repositories for pending/open/exit
evaluation, fills, persistence, target/stop protection, recovery and portfolio
admission. The active composition still contains no-active-position/empty
recovery stubs, so lifecycle is partial rather than launch-ready. Existing
vocabulary maps behaviorally to PREDICTED → PLANNED → PAPER_ENTRY_PENDING →
PAPER_OPEN → HOLD/TARGET_REACHED/RISK_WARNING → EXIT_PENDING → CLOSED →
RECONCILED; canonical names must not be renamed merely for this mapping.

Task 5 has journals, audit events, trade persistence, session analytics and
summary/report utilities, but lacks one immutable prediction-outcome record and
the required daily/weekly/monthly reconciliation metric set. The required
outcome vocabulary maps to equivalent terminal/cancellation/invalidation/P&L
facts where present; a formal mapping is still needed.

Dashboard foundations are read-model/publication based and `dashboard_v2.py`
has projection components. Legacy `dashboard/home.py` and `live_market_test.py`
are not authority paths. Missing projection evidence includes complete pair
winner/loser rationale, active PAPER position/real-time premium/P&L, target and
risk events, report access, and a proof that refresh cannot trigger analysis,
entry, or LIVE submission. Persistence is independent of Streamlit through
repositories, but active runtime recovery wiring remains incomplete.

## Post-Task-1 implementation order

| Slice | Goal, likely files, tests, gate, dependency, commit boundary |
| --- | --- |
| 3A | Bind selected parent result to P6: `selected_market_planning_bridge.py`, P6 factory/executor; selected-only/no-size tests; gate is one selected plan or NO_TRADE; depends on 2; independent commit. |
| 3B | Certify live option ranking/selection evidence: option adapters/ranking/selection tests; gate is NFO/BFO constrained contract or blocker; depends on 1 and 3A; independent commit. |
| 3C | Integrate entry/stop/T1-T3/capital plan: P6 evaluators/integrator tests; gate is bounded plan with risk/costs; depends on 3A/B; independent commit. |
| 4A | Persist selected PAPER entry: lifecycle executor/repositories tests; gate is idempotent PAPER entry; depends on 3C; independent commit. |
| 4B | Wire monitoring, target/stop/HOLD/EXIT and discovery: monitoring/recovery executors tests; gate is restart-safe transition matrix; depends on 4A; independent commit. |
| 4C | Reconcile positions/portfolio after restart: persistence/recovery tests; gate is no duplicate/unreconciled position; depends on 4B; independent commit. |
| 5A | Add immutable prediction/outcome linkage: journal contracts/services tests; gate is unique cycle/prediction/final outcome; depends on 3C/4C; independent commit. |
| 5B | Build reconciled report metrics: analytics/report tests; gate is daily/weekly/monthly journal reconciliation; depends on 5A; independent commit. |
| 5C | Complete read-only dashboard projections: publication/read-model/dashboard tests; gate is refresh-safe complete view; depends on 4C/5B; independent commit. |
| 6 | Run the continuous real-time 100+100 session under the separate Task 6 rules; defects remain in Task 6; depends on 1–5; its final report is the acceptance gate. |

## Documentation status

### Task 2E1.5 certified parent-cycle identity migration

`TwoMarketParentCycleInputV1.parent_cycle_id` is the sole certified parent
cycle source. The identical value is supplied to both NIFTY and SENSEX child
evaluations; candidate and observation identities remain market-specific.
Certified paths have no candidate-ID fallback. Ledger, pre-entry action, child
explanation, and typed parent-explanation identity now use that parent cycle
without changing scoring, actions, explanations, ranking, or PAPER-only
guards. This unblocks Task 2E2; it does not declare Task 2 complete.

Task 2E2 adds typed decision-certification results and deterministic,
provider-free foundation fixtures. It retains the shared parent-cycle identity
and leaves ranking, action resolution, explanations, and shadow-ledger policy
authoritative in their production components. Task 2E3 still owns the complete
scenario matrix, aggregate report/CLI, and final Task 2 completion gate.

`FINAL_TRADING_COPILOT_ROADMAP.md` conflicts with this roadmap because it has
eleven tasks and replay-count language. It is historical/superseded. Prior P4–
P10 audits and certification documents are historical evidence, not launch
roadmap authority.
