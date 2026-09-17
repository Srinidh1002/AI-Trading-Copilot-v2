# Phase 0 Executive Summary

Scope: observation-only audit on 2026-07-25. The named primary authority `docs/00_MASTER_SPECIFICATION.md` does not exist. This audit used the clearly corresponding `docs/AI_Trading_Copilot_Master_Specification_v0.1.md`; this is a **MEDIUM** governance gap (VERIFIED).

The repository has 399 non-test/non-archive Python files and 128 configured test files. It contains two materially different runtime paths: the Streamlit dashboard path, and the safety-gated live-option CLI path. They do not converge on one typed response or one canonical decision/risk engine.

## Five critical verified risks

1. **CRITICAL — `config` import collision.** `config/` shadows root `config.py`; `utils/debug.py:1` imports `DEBUG_MODE` from the package, which does not export it. Pytest collection stops with 14 errors before safety tests run. Impact: affected live/broker modules cannot import. Recommendation: establish one configuration package and explicitly migrate imports. Confidence: VERIFIED.
2. **CRITICAL — Dashboard bypasses the safety-gated option pipeline.** `app.py -> dashboard/dashboard_v2.py:64,77 -> services/market_snapshot.py -> services/trade/trade_engine.py`; it never calls `services/live_option_decision_pipeline.py`. Impact: dashboard BUY/SELL presentation is not demonstrably protected by the live pipeline's session, stale-candle, setup, contract and trade-plan gates. Recommendation: choose one canonical pipeline and make every UI/CLI consumer use its response. Confidence: VERIFIED.
3. **CRITICAL — UI path couples display to paper-trade side effects.** `services/trade/trade_engine.py:380` calls `process_trade(paper_trade)` during `analyze_trade`, invoked by the Streamlit fragment. Impact: dashboard refresh can create/update paper-trading state. Recommendation: separate decision rendering from explicitly authorized paper execution. Confidence: VERIFIED.
4. **HIGH — Production imports archive code.** `services/core/final_decision_pipeline.py`, `services/decision/master_decision_engine.py`, `services/market/live_multi_timeframe_engine.py`, and `services/analysis/__init__.py` import `archive.*`; root CLI wrappers execute archive source with `exec`. Impact: archive is active production dependency, contrary to the specification. Recommendation: migrate or retire by an explicit compatibility plan. Confidence: VERIFIED.
5. **HIGH — incompatible parallel contracts/engines.** `services/market_snapshot.py` returns an ad-hoc dict, while `services/core/snapshot_schema.py:Snapshot` is a dataclass; `services/trade/trade_engine.py` imports `services/core/market_snapshot.py` despite dashboard supplying the other snapshot. Multiple decision/risk/confidence implementations coexist. Impact: unsafe assumptions and test brittleness. Recommendation: define a single versioned snapshot and final-decision contract. Confidence: VERIFIED.

Recommended first remediation task: **P0-1, remove the `config.py`/`config/` namespace collision and restore test collection without changing decision behaviour.**

No existing production, test, configuration, dependency, database, script, CI/CD, or documentation files were modified by this audit; only `docs/audit/*` was added.
