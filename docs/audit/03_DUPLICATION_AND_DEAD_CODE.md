# Duplication, Compatibility, and Dead-Code Findings

## Duplicate groups

| Group | Files and callers | Difference / canonical recommendation |
|---|---|---|
| Decision | `services/decision_engine.py`, `services/master_decision_engine.py`, `services/decision/master_decision_engine.py`, `services/unified_decision_engine.py`, `services/core/final_decision_pipeline.py` | Dashboard uses package master engine; agents use unified engine; core/live engine is separate. **HIGH**, MERGE to one safety-gated final decision API. VERIFIED. |
| Snapshot | `services/market_snapshot.py`, `services/core/market_snapshot.py`, `services/market/market_snapshot.py`, `services/core/snapshot_schema.py` | dict and dataclass contracts; dashboard and trade module name different sources. **HIGH**, MIGRATE. VERIFIED. |
| Risk | `services/risk_engine.py`, `services/risk_management_engine.py`, `services/risk_manager.py`, `services/risk/risk_engine.py`, `services/options_risk_engine.py` | different public APIs/roles; dashboard calls package risk engine. **HIGH**, MERGE after behaviour inventory. VERIFIED. |
| Confidence/scoring | root `confidence_engine.py`, `adaptive_confidence_engine.py`, `decision/confidence_engine.py`, `ai/confidence_engine.py`, `trade/trade_score_engine.py`, `scoring/trade_score_engine.py` | confidence semantics and consumers differ; several thresholds are local. **HIGH**, MERGE. VERIFIED. |
| Trade/paper | root `trade_engine.py`, `trade/trade_engine.py`, `decision/trade_engine.py`, `trade/paper_trade_engine.py`, `paper_trading/paper_trade_engine.py`, paper runtime services | overlapping responsibilities. **HIGH**, MIGRATE. VERIFIED. |
| Market structure/smart money | `archive/market_structure_engine.py`, `archive/smart_money_engine.py`, archive `services_old/*`, `analysis/price_market_structure_engine.py` | archive modules remain imported by production. **HIGH**, migrate explicit dependencies. VERIFIED. |

## Compatibility and archive dependency

Root wrappers (`run_continuous_paper_trading.py`, `live_market_research_runner.py`, `paper_trading_preflight.py`, `pre_market_readiness.py`, `monitor_paper_positions.py`, `market_session_summary.py`, `inspect_audit_log.py`) run archive source with `exec(compile(...), globals())`. `daily_research_report_runner.py` wildcard-imports a service and imports archive `main`.

Impact: import-time side effects, invisible dependencies, weak static analysis and archive code on supported paths. Recommendation: replace one wrapper at a time with named, tested functions; then RETIRE wrapper/archive code. Severity: HIGH. Confidence: VERIFIED.

No-call claims: without runtime telemetry/import graph execution, most unreferenced modules are **UNKNOWN**, not dead. Root/service `test_*.py` are likely uncollected because `pytest.ini` restricts discovery to `tests/`; this is a **MEDIUM** likely test-dead-code gap.
