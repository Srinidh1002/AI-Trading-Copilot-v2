# Prioritized Remediation Plan

| Priority | Task | Evidence / outcome |
|---|---|---|
| P0 — Safety blockers | Fix `config.py`/`config/` collision; preserve behaviour and restore collection | `utils/debug.py:1` causes 14 collection errors |
| P0 — Safety blockers | Block dashboard paper side effects until explicit authorization boundary exists | `services/trade/trade_engine.py:380` runs on UI analysis |
| P0 — Safety blockers | Ensure every dashboard/CLI decision traverses one fail-closed gate | dashboard bypass confirmed |
| P1 — Runtime/contracts | Define and contract-test `MarketSnapshot v1` and `FinalDecision v1` | dict/dataclass/casing/action conflicts |
| P1 — Runtime/contracts | Map legacy status values to stable action + authorization enums | `TRADE_ALLOWED` vs spec actions |
| P1 — Runtime/contracts | Re-run suite; repair collection first, then group assertion failures | current tests do not execute |
| P2 — Architecture | Select one decision, confidence, risk and trade engine; deprecate other public APIs | duplicate groups in report 03 |
| P2 — Architecture | Replace `exec(compile())` archive wrappers and remove production archive imports | root wrappers and four service groups |
| P3 — Test completeness | Add entry-point integration safety matrix and contract tests; include root/service tests deliberately or move/retire them | suite scope and safety gaps |
| P4 — Maintainability/performance | Move dashboard DB/orchestration out; centralize configuration; audit cache/retry/timeout behaviour | UI coupling and scattered thresholds |
| P5 — Future features | Approved live execution, expanded data evidence, AI/backtesting after safety certification | specification governance sequence |

Each task should be one feature branch, with approved contracts, test evidence, and a no-live-order invariant until limited-live governance is approved.
