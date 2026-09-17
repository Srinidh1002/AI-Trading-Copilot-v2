# Contract and Architecture Gaps

## Verified contract gaps

1. **HIGH — Snapshot shape conflict.** `services/market_snapshot.py` emits a dict consumed with direct keys in `dashboard/dashboard_v2.py`; `services/core/snapshot_schema.py:Snapshot` is a dataclass, and `services/core/market_snapshot.py` is separately imported by `services/trade/trade_engine.py`. Impact: missing/default fields and timestamp/data-health semantics are not enforced. Recommendation: version one typed contract. Confidence: VERIFIED.
2. **HIGH — OHLCV casing is an adapter concern only in one path.** `services/live_analysis_pipeline.py` sends uppercase data to technical/multi-timeframe engines and lowercase data to candle/volume/chart/structure engines; `services/market_snapshot.py:65` lowercases directly. Impact: callers can bypass normalisation. Recommendation: central normalization at provider boundary and contract-test every consumer. Confidence: VERIFIED.
3. **HIGH — action vocabulary differs.** Specification requires `BUY`, `SELL`, `WAIT`, `HOLD`; the live pipeline emits `TRADE_ALLOWED`, `TRADE_READY`, waiting/rejection states, while master paths use `NO_TRADE`/`HOLD`/directional values. Impact: presentation/execution ambiguity. Recommendation: distinct `action` and `authorization_status` enums. Confidence: VERIFIED.
4. **MEDIUM — confidence representation is inconsistent.** Functions accept a mapping or scalar (`services/master_decision_engine.py`, `services/trade_quality_engine.py`); `services/technical_analyzer.py` declares integer confidence; multiple engines calculate separately. Impact: uncertain scale and capping semantics. Recommendation: one 0–100 documented score with components and provenance. Confidence: VERIFIED.
5. **MEDIUM — configuration namespace conflict.** root `config.py` holds environment, risk and feature flags while `config/__init__.py` exports only version fields. Python resolves the package for `from config import DEBUG_MODE`. Impact: runtime failure. Recommendation: migrate to a single package. Confidence: VERIFIED.

## Architecture health

`dashboard/dashboard_v2.py` includes data access (SQLite), orchestration, analysis invocation, presentation and error control, contrary to UI/business separation. `config.py` creates directories at import time (`mkdir` for database/reports/logs): an import-time side effect. Production archive imports are listed in report 03. No circular-import claim is made: it was not dynamically verified. Severity: HIGH for coupling, MEDIUM for import side effects. Confidence: VERIFIED.

Secrets: `config.py` loads `.env` and declares Angel/Upstox/OpenAI variable names; `.env` exists. Values were deliberately not read or reported. Risk is **MEDIUM** because a secret-bearing local file exists; whether secrets are committed is UNKNOWN (the audit did not disclose values). `requirements.txt` pins most dependencies but leaves `smartapi-python` and `pyotp` unpinned: MEDIUM reproducibility risk, VERIFIED.
