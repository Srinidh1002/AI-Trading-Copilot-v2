# Canonical/Legacy Comparison v1

`services.canonical.comparison` is an opt-in diagnostic layer. It compares
already-available legacy payloads with a canonical result built from the same
adapted `MarketSnapshotV1`; it never invokes a dashboard, CLI, broker,
provider, paper boundary, or execution boundary.

## Public APIs

```python
compare_dashboard_legacy_to_canonical(
    legacy_snapshot,
    legacy_decision,
    canonical_dependencies=None,
    reference_time=None,
) -> CanonicalLegacyComparison
```

```python
compare_live_option_legacy_to_canonical(
    legacy_decision,
    symbol=...,
    exchange=...,
    market_timestamp=...,
    ltp=...,
    timeframes=None,
    canonical_dependencies=None,
    reference_time=None,
) -> CanonicalLegacyComparison
```

`CanonicalLegacyComparison` contains the adapted snapshot, adapted legacy
decision, canonical analysis and decision, ordered semantic differences,
warnings, and contained errors. `to_dict()` and `to_json()` are deterministic.

## Difference semantics

The layer compares action, direction, market regime, authorization, execution
state, selected score fields, data health, trade-plan presence, and blocking
reasons. A difference is evidence for migration analysis only—it is neither a
recommendation nor an instruction to replace, authorize, or execute either
result. P2-5 intentionally reports expected differences caused by the current
canonical analysis-only boundary.

## Error handling and safety

Snapshot adaptation, legacy adaptation, and canonical-pipeline failures are
contained in `errors`; comparison callers do not receive a replacement legacy
response. The module does not mutate either supplied mapping. It makes no
network, database, paper, broker, or provider call.
