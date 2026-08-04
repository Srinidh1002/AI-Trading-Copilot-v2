# Final Trading Copilot Gap Audit

## Scope and runtime truth

Static audit at `p10-two-market-weekend-readiness`, HEAD
`906c3a45303d9f6d4bd5f1801c83c9d4284aa582`. No production code changed and no
full suite ran. READY means usable in the frozen NIFTY/SENSEX PAPER scope;
READY_BUT_NOT_INTEGRATED means typed/tested capability absent from the certified
runtime path.

The frozen product is NIFTY/NSE/NFO and SENSEX/BSE/BFO only. The active launcher
is PAPER-only: `execution_mode="PAPER"`, `live_execution_eligible=False`, and
`broker_order_submission=False`.

`build_certified_launcher()` is a **single configured-market** runtime.
`CertifiedRuntimeCompositionSettingsV1.primary_symbol`/`primary_exchange`
default to NIFTY/NSE; `CertifiedCycleSource` builds one child input. SENSEX can
replace the primary market, but no active path evaluates both, ranks both,
selects a winner, preserves the losing rationale, discovers positions, or
performs real restart recovery. `docs/TWO_MARKET_RUNTIME_STATUS.md` is the
authoritative detailed evidence.

## Capability matrix

| # | Capability | Classification | Authority/evidence | Gap or qualification |
| --- | --- | --- | --- | --- |
| 1 | identities and sessions | READY_BUT_NOT_INTEGRATED | `core/market_identity.py`, `underlying_registry.py`, `market_session/*` | Exact identities per child; one scheduled market. |
| 2 | live quote and candles | READY_BUT_NOT_INTEGRATED | `certified_live_provider_readers.py`, `market/live_multi_timeframe_data.py` | NIFTY/SENSEX routing works; no pair fan-out/skew policy. |
| 3 | normalization, cache, freshness, quality | PARTIAL | `certified_p5_normalization.py`, `data_quality/*`, `refresh/*` | Not assembled as complete two-market evidence. |
| 4 | technical indicators | READY_BUT_NOT_INTEGRATED | `technical_intelligence/*`, `live_analysis_pipeline.py` | No pair-level integration. |
| 5 | candlestick/chart patterns | READY_BUT_NOT_INTEGRATED | `candlestick_engine.py`, `chart_pattern_analyzer.py` | Analytical component, not pair join. |
| 6 | price action/structure | PARTIAL | `analysis/price_market_structure_engine.py`, `options/market_structure_engine.py` | Duplicate implementations lack one certified authority. |
| 7 | volume | READY_BUT_NOT_INTEGRATED | `analysis/volume_engine.py`, `volume_intelligence.py` | Not proved in every certified candidate. |
| 8 | volatility | READY_BUT_NOT_INTEGRATED | `technical_intelligence/volatility.py`, volatility contracts | No paired runtime consistency. |
| 9 | regime | READY_BUT_NOT_INTEGRATED | `market_regime/*`, regime contracts | No paired coordinator. |
| 10 | multi-timeframe | READY_BUT_NOT_INTEGRATED | `multi_timeframe/*`, live MTF data | Per-market only. |
| 11 | option-chain acquisition | READY_BUT_NOT_INTEGRATED | `live_option_chain_builder.py` | NFO/BFO routing; one chain per configured cycle. |
| 12 | OI/OI change/PCR/max pain/SR | READY_BUT_NOT_INTEGRATED | `option_chain_intelligence/*`, `options/*` | Not paired/ranked runtime evidence. |
| 13 | Greeks/IV/premium | PARTIAL | `options/greeks_engine.py`, `option_chain_intelligence/iv_skew.py` | No single complete certified integration contract. |
| 14 | sentiment/news/external context | PARTIAL | `external_context/*`, `broader_market_intelligence/*`, `news.py` | Capability exists; live composition incomplete. |
| 15 | contradictions/confidence | READY_BUT_NOT_INTEGRATED | typed technical/regime/option results | No pair losing rationale. |
| 16 | NIFTY/SENSEX candidate construction | PARTIAL | `CertifiedLiveOpportunityAuthority`, `MarketOpportunityCandidateV1` | One opportunity result; no two candidates. |
| 17 | two-market coordination/ranking | MISSING | `CertifiedCycleSource`, `opportunity_ranking/aggregate.py` | Scheduler is one market; existing ranker requires four. |
| 18 | capital-aware planning/sizing | READY_BUT_NOT_INTEGRATED | `risk/pipeline.py`, P6 contracts | No selected-pair handoff. |
| 19 | P6 planning | READY_BUT_NOT_INTEGRATED | `certified_p6_input_factory.py`, `p6_planning_stage_executor.py` | Accepts only supplied certified bundle; otherwise fails closed. |
| 20 | P7 lifecycle/monitoring | PARTIAL | new-entry and monitoring executors | Composition injects no-active-position input. |
| 21 | P8 portfolio/persistence/admission | READY_BUT_NOT_INTEGRATED | `paper_portfolio/*` | Pair-selected handoff absent. |
| 22 | active-position discovery | MISSING | `_no_active_position_monitoring_input` | No persisted discovery in runtime. |
| 23 | restart recovery | PARTIAL | P7/P8 recovery services | Composition uses `_recovery_success_empty()`. |
| 24 | PAPER fills/slippage | PARTIAL | `paper_trading/*`, P6 cost evidence | Deterministic fills; live-like model not certified. |
| 25 | targets/partial/stop/early exit | READY_BUT_NOT_INTEGRATED | `paper_trade_position_evaluator.py` | Monitoring composition missing. |
| 26 | journals/summaries/performance | PARTIAL | journal, runtime logging, `summarize_paper_runtime.py` | No complete pair-level performance record. |
| 27 | deterministic replay/backtesting | READY_BUT_NOT_INTEGRATED | `replay/*`, `backtesting/*`, P5-P8 tests | No final two-market runtime replay. |
| 28 | dashboard/read models/application | PARTIAL | `dashboard_v2.py`, publication/read-model packages | Display-only UI; pair view is internal and unwired. |
| 29 | notifications/operator controls | PARTIAL | `notifications/*`, operator controls, PowerShell scripts | No certified pair-decision alert policy. |
| 30 | broker isolation/PAPER safety | READY | runtime safety, launcher, PAPER contracts | Future live path remains separate/uncertified. |
| 31 | tests/certification evidence | PARTIAL | P5-P10 tests, B4/B6 tests, certification docs | No paired 100-trade evidence. |
| 32 | dead/duplicate legacy paths | LEGACY_ONLY | legacy dashboards, root/legacy engines | Must not become certified authority. |

## Duplicates and frozen-task ownership

| Finding | Frozen task | Rule |
| --- | --- | --- |
| Four-market ranker requires BANKNIFTY/FINNIFTY | 3. True two-market decision engine | Add exact two-market policy; do not adapt it. |
| `market_ranking_engine.py` has wider dictionary universe | 3. True two-market decision engine | Legacy only. |
| Multiple technical/volume/regime/structure/option engines | 2. Analytical engine completion | Choose typed canonical outputs with provenance. |
| `dashboard/home.py` and `dashboard/live_market_test.py` fetch/compute directly | 6. Stable application | Keep non-active. |
| Recovery services exist but runtime stubs discovery/recovery | 5. PAPER lifecycle and monitoring | Wire persisted discovery; preserve fail-closed behavior. |
| PAPER fill simulation coexists with broker clients | 5. PAPER lifecycle and monitoring | PAPER only until Task 10 approval. |

## Blockers

### Sunday completion

- Tasks 2-5 require complete typed evidence, pair coordination/ranking,
selected-market P6 handoff, active-position discovery, and recovery wiring.
- No end-to-end runtime currently proves both markets are evaluated exactly once.
- Sunday work remains PAPER-only; broker execution is excluded.

### Monday market hours

- Provider freshness, SmartAPI rate-limit/cooldown, NFO/BFO chains, sessions,
and pair timestamp skew need controlled live PAPER observation.
- Pair selection/rejection evidence and active-position/restart behaviour need
live-session PAPER cycles.
- 100 trades per market cannot be certified by replay alone.

## Exact inspected-file inventory

The following are the repository-relative files whose contents were read by
the static audit. Directory wildcards in the matrix are scope summaries only,
not claims that every file in those directories was opened.

- `app.py`
- `config.py`
- `run_continuous_paper_trading.py`
- `docs/AUTOMATED_PAPER_CERTIFICATION.md`
- `docs/P10A_DASHBOARD_AUDIT.md`
- `docs/P10B_READ_MODEL_DESIGN.md`
- `docs/PAPER_RUNTIME_RUNBOOK.md`
- `docs/PAPER_RUNTIME_TROUBLESHOOTING.md`
- `docs/TWO_MARKET_RUNTIME_STATUS.md`
- `scripts/paper_canary.ps1`
- `scripts/paper_daily_summary.ps1`
- `scripts/paper_preflight.ps1`
- `scripts/paper_run_5.ps1`
- `scripts/paper_run_30.ps1`
- `scripts/summarize_paper_runtime.py`
- `services/contracts/four_market_opportunity_ranking_result_v1.py`
- `services/contracts/four_market_ranking_policy_v1.py`
- `services/contracts/paper_orchestration_cycle_input_v1.py`
- `services/contracts/paper_trade_lifecycle_state_v1.py`
- `services/contracts/paper_trade_position_evaluation_input_v1.py`
- `services/core/market_identity.py`
- `services/dashboard_read_models/__init__.py`
- `services/dashboard_read_models/dashboard_two_market_runtime_view_v1.py`
- `services/live_analysis_pipeline.py`
- `services/live_option_chain_builder.py`
- `services/live_option_decision_pipeline.py`
- `services/market/live_multi_timeframe_data.py`
- `services/market_ranking_engine.py`
- `services/opportunity_ranking/aggregate.py`
- `services/paper_orchestration/certified_cycle_input_factory.py`
- `services/paper_orchestration/certified_live_provider_readers.py`
- `services/paper_orchestration/certified_runtime_composition.py`
- `services/paper_orchestration/certified_runtime_launcher.py`
- `services/paper_orchestration/certified_runtime_safety.py`
- `services/paper_orchestration/existing_position_monitoring_executor.py`
- `services/paper_orchestration/new_entry_paper_lifecycle_executor.py`
- `services/paper_orchestration/p6_planning_stage_executor.py`
- `services/paper_portfolio/paper_portfolio_admission_evaluator.py`
- `services/paper_portfolio/paper_portfolio_persistence_service.py`
- `services/paper_trading/paper_broker.py`
- `services/paper_trading/paper_trade_position_evaluator.py`
- `services/risk/pipeline.py`
- `tests/p7_fixture_helpers.py`
- `tests/test_p10b_two_market_runtime_view.py`
- `tests/test_p10_wp1_dashboard_authority_audit.py`
- `tests/test_p10_wp1_public_api_certification.py`
- `tests/test_p10_wp1_read_model_import_isolation.py`
- `tests/test_paper_operational_scripts_static.py`
- `tests/test_summarize_paper_runtime.py`
- `tests/test_two_market_runtime_readiness.py`
- `tests/test_weekend_paper_resilience.py`

## Scope-only discovery summaries

The inventory command also discovered candidate modules and tests beneath
`services/technical_intelligence/`, `services/multi_timeframe/`,
`services/market_regime/`, `services/option_chain_intelligence/`,
`services/external_context/`, `services/broader_market_intelligence/`,
`services/dashboard_publication/`, `services/notifications/`,
`services/broker/`, `services/replay/`, `services/backtesting/`, `dashboard/`,
and the P5-P10 test families. Those paths informed audit scope only; they are
not represented as individually inspected evidence in this document.
