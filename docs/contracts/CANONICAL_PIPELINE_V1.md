# Canonical Pipeline v1

`services.canonical` is an additive, side-effect-free orchestration path:

```text
MarketSnapshotV1 -> CanonicalAnalysisPipeline -> AnalysisResultV1
                 -> CanonicalDecisionPipeline -> FinalDecisionV1
```

Its public entry point is:

```python
run_canonical_pipeline(
    snapshot: MarketSnapshotV1,
    *,
    dependencies: CanonicalPipelineDependencies | None = None,
) -> FinalDecisionV1
```

## Boundaries

- The input must already be a `MarketSnapshotV1`; this package does not fetch,
  normalize provider payloads, create clients, or invoke provider adapters.
- Analysis uses pure/default engine functions over supplied OHLCV and explicit
  injected functions for deterministic tests or alternate implementations.
- Engine exceptions become `AnalysisResultV1.engine_errors`; errors from
  critical engines make analysis invalid.
- The decision layer returns only `ANALYSIS_ONLY` for otherwise valid
  directional evidence. It creates no trade plan and grants no paper or live
  authorization during P2-4.
- Invalid, stale, mismatched, or invalid-analysis inputs return a blocked
  `WAIT` decision.
- The package never imports Streamlit, invokes legacy runtime pipelines,
  persists data, calls a provider, or calls paper/broker execution functions.

## Migration status

The dashboard, live-option CLI, paper boundary, broker, and live execution
remain on their existing legacy routes. This module is available only for
explicit callers and focused tests until a separate migration task approves
runtime routing.
