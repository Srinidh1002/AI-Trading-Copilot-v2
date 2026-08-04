# P2-4 — Additive Canonical Pipeline

## Decision

Implemented the proposed ADR-001 canonical flow as an explicit, additive
application API. It is not imported by any existing dashboard, CLI, paper,
broker, or execution entry point.

```text
MarketSnapshotV1 -> CanonicalAnalysisPipeline -> AnalysisResultV1
                 -> CanonicalDecisionPipeline -> FinalDecisionV1
```

## Files and responsibilities

- `services/canonical/adapters.py` converts canonical OHLCV and contained
  legacy-engine evidence into typed analysis contract sections.
- `services/canonical/analysis_pipeline.py` runs analysis-only engines with
  exception isolation and emits `AnalysisResultV1`.
- `services/canonical/decision_pipeline.py` creates a conservative,
  analysis-only `FinalDecisionV1` and blocks invalid inputs.
- `services/canonical/pipeline.py` supplies the public dependency-injected
  `run_canonical_pipeline` API.
- `services/canonical/__init__.py` exposes the narrow public API.
- `services/contracts/__init__.py` exports `DataStatus` for contract users.
- Focused tests document directional, missing-data, analysis-only, and
  fail-closed behavior for the new path.

## Compatibility and safety decisions

Existing engines are reused only behind adapters and only with the data already
present in `MarketSnapshotV1`. No provider-backed option-chain helper is used
without an explicit snapshot payload. Engine exceptions become typed analysis
errors. The decision pipeline never creates a trade plan or promotes a result
beyond `ANALYSIS_ONLY`, so it cannot request paper or live execution.

No legacy route was migrated or modified. Decision thresholds, scores,
confidence formulas, risk formulas, and option-selection rules remain owned by
their legacy modules and are not changed here.

## Verification status

Per the P2-4 workflow instruction, no pytest, full suite, coverage, lint,
formatting, or external service was run. The project owner must run the new
focused canonical tests and the configured suite manually.
