# X5 Phase B3: fixed feature manifest and read-only research view

## Scope

Offline, pure projection of a single `X5ChainCaptureV1`, `X5ChainValidationV1`, and
`X5AnalyticsResultV1` into a deterministic research view. This phase **does not**
fetch FYERS data, re-run calculations, create a trading signal, score entries,
select strikes, place orders, modify risk policy, touch production PAPER state,
or count certification trades.

The only new files are `services/x5/feature_manifest_v1.py`,
`services/x5/research_view_v1.py`, `tests/test_x5_research_view_v1.py`, and
this document. No existing provider, analytics, X1–X4, Brain, or production
runtime source is changed.

## Registered metrics and dependency groups

| Feature | Family | Dependency group |
| --- | --- | --- |
| `PCR_OI` | Option positioning | `OPTION_OI_POSITIONING` |
| `PCR_VOLUME` | Option volume | `OPTION_FLOW_VOLUME` |
| `MAX_PAIN` | Option positioning | `OPTION_OI_POSITIONING` |
| `OI_CONCENTRATION` | Option positioning | `OPTION_OI_POSITIONING` |
| `OI_BUILDUP` | Option positioning | `OPTION_OI_POSITIONING` |
| `OI_SUPPORT_RESISTANCE` | Option positioning | `OPTION_OI_POSITIONING` |
| `IV_SKEW` | Option volatility | `OPTION_VOLATILITY` |
| `QUOTE_SPREAD` | Option liquidity | `OPTION_QUOTE_LIQUIDITY` |
| `GREEKS` | Option sensitivity | `OPTION_GREEKS_SHAPE` |

B3 checks its fixed registry against the B2 `METRICS`, `_GROUPS` and `_UNITS`
interfaces. It fails if the B2 order, dependency grouping, or units change.
The five OI-positioning metrics share their underlying data and **are not five
independent confirmations**. The `group_coverage` field counts available
measurements; it is **not** a score, weight, vote, directional strength or
recommendation.

## Entry point

```python
manifest = build_x5_feature_manifest_v1()
view = build_x5_research_view_v1(
    capture=capture,
    validation=validation,
    analytics=analytics,
    manifest=manifest,  # optional; default is the fixed registry
)
```

`build_x5_research_view_v1` enforces equal market, expiry, capture ID and
`as_of`; the validation's source-capture SHA-256 must equal the provided
capture; the analytics' capture and validation hashes must match; and B2's
metric inventory, status, units and dependency groups must agree with the
manifest. It refuses to convert validation-blocked evidence into available
metrics. It never recalculates a missing metric or substitutes an assumed
value. Feature and view records include source hashes for deterministic audit.

The research view reports the *captured strike window*, observed CE/PE coverage,
availability, validation diagnostics, groups, and provenance. It makes no
claim that the capture includes every exchange-listed strike.

## Point-in-time and provider limitations

X5-A/B1 validation requires explicit source timestamps, verified expiry,
provider identity and declared measurement semantics. Retrospective downloads
are not promoted to point-in-time evidence merely because their simulated
historical timestamps precede the replay checkpoint. The B3 projection
retains these limitations and cannot itself validate caller-supplied proof.

The native B1 adapter does not currently provide verified IV or Greeks, and
unverified OI or volume cannot enter the corresponding B2 metrics. A passed
offline fixture suite does **not** establish that real FYERS data is live-
certified or that its units are independently verified. Separate real-provider
capture/provenance testing is required before any broader integration.

## Safety and freeze

All feature, manifest and view records are immutable, data-only, have
`independent_vote=False`, and force execution, risk, position, certification
and live-execution authority to `False`. X5 is not registered in Brain V1,
production PAPER policy, execution or certification. Do not commit Phase B3
until focused X5, combined Brain+X1–X5, and existing FYERS compatibility
regressions pass locally. Retain the existing development branch and SHA gate.
