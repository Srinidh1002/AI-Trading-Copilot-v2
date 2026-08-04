# AnalysisResult v1 Contract

## Purpose

`AnalysisResult v1` is the canonical typed output of market-analysis engines and the sole internal input to the future canonical decision pipeline.

It sits between:

```text
MarketSnapshot v1
    ↓
CanonicalAnalysisPipeline
    ↓
AnalysisResult v1
    ↓
CanonicalDecisionPipeline
    ↓
FinalDecision v1
```

The contract describes analysis evidence only. It does not contain action, authorization, execution, paper-trading, broker-order, or live-execution fields.

## Canonical location

```text
services/contracts/analysis_result_v1.py
```

## Identity fields

- `schema_version`
- `analysis_id`
- `snapshot_id`
- `symbol`
- `created_at`
- `market_timestamp`
- `timezone`

## Market-state fields

- `market_regime`
- `directional_bias`
- `direction_resolved`
- `trend_strength`
- `volatility_state`
- `market_session`

## Directional bias vocabulary

- `BULLISH`
- `BEARISH`
- `NEUTRAL`
- `CONFLICTED`
- `UNKNOWN`

## Market-regime vocabulary

- `TRENDING`
- `RANGING`
- `BREAKOUT_TRANSITION`
- `HIGH_VOLATILITY`
- `LOW_LIQUIDITY`
- `EVENT_DRIVEN`
- `UNCERTAIN`
- `UNKNOWN`

## Evidence sections

The contract contains typed evidence sections for:

- Technical analysis
- Market structure
- Candlesticks
- Volume
- Options
- Institutional/FII-DII context
- Volatility/India VIX context
- Global/news/event context

Each section contains:

- `status`
- `signal`
- `score`
- `confidence`
- `reasons`
- `contradictions`
- `warnings`
- `errors`
- `source_timestamp`
- JSON-safe metadata

### Evidence status

- `VALID`
- `PARTIAL`
- `UNAVAILABLE`
- `EMPTY`
- `STALE`
- `INVALID`
- `ERROR`

### Evidence signal

- `BULLISH`
- `BEARISH`
- `NEUTRAL`
- `MIXED`
- `UNAVAILABLE`

Unavailable, empty, invalid, or errored evidence cannot provide bullish or bearish confirmation.

## Multi-timeframe summary

The contract includes:

- Alignment
- Primary execution timeframe
- Confirmation timeframe
- Higher timeframe
- Per-timeframe direction and trend strength
- Conflicting timeframes
- Missing timeframes
- Warnings

### Alignment vocabulary

- `ALIGNED_BULLISH`
- `ALIGNED_BEARISH`
- `MIXED`
- `CONFLICTED`
- `INSUFFICIENT_DATA`

## Scores

All scores use the range `0..100` and remain optional:

- `technical_score`
- `structure_score`
- `candlestick_score`
- `volume_score`
- `options_score`
- `institutional_score`
- `volatility_score`
- `context_score`
- `data_quality_score`

Missing scores remain `None`. The contract never invents neutral score values.

## Analysis-level collections

- `supporting_reasons`
- `contradictions`
- `missing_inputs`
- `warnings`
- `engine_errors`
- `source_timestamps`
- `trace_metadata`
- `validation_errors`

All reason/error collections are deterministic and serialized as ordered lists.

## Safety invariants

- Required identity must be present.
- Timestamps must be ISO-8601-compatible and timezone-aware after construction.
- Scores must be finite and within `0..100`.
- Conflicted or unknown direction cannot be marked resolved.
- Conflicted multi-timeframe alignment cannot be marked direction resolved.
- Critical engine failures invalidate the analysis.
- Missing/invalid evidence cannot provide bullish or bearish confirmation.
- Metadata must be JSON-serializable.
- No DataFrame, provider client, broker client, file handle, or mutable live object may appear in serialized output.
- Construction has no provider, paper, database, or broker side effects.
- The contract contains no trade authorization.

## Critical engines

Default critical engine names:

- `market_data`
- `technical`
- `market_structure`
- `risk_precheck`

A recorded error for a critical engine makes `analysis_valid=False`.

This list is configuration-like contract metadata and may later be centralized after canonical pipeline implementation.

## Serialization

- `to_dict()` produces deterministic JSON-safe structures.
- `to_json()` uses sorted keys and compact separators.
- `from_dict()` supports contract round-trip reconstruction.

## Examples

### Minimal valid unknown analysis

```python
AnalysisResultV1(
    snapshot_id="snapshot-1",
    symbol="NIFTY",
    created_at=now,
    market_timestamp=now,
)
```

### Valid bullish analysis

```python
AnalysisResultV1(
    snapshot_id="snapshot-1",
    symbol="NIFTY",
    created_at=now,
    market_timestamp=now,
    market_regime="TRENDING",
    directional_bias="BULLISH",
    direction_resolved=True,
    technical=EvidenceSection(
        status="VALID",
        signal="BULLISH",
        score=78,
        reasons=("Trend and momentum aligned.",),
    ),
)
```

### Conflicted analysis

```python
AnalysisResultV1(
    snapshot_id="snapshot-1",
    symbol="NIFTY",
    created_at=now,
    market_timestamp=now,
    directional_bias="CONFLICTED",
    direction_resolved=False,
    contradictions=("5m bullish while 1h bearish.",),
)
```

### Critical engine failure

```python
AnalysisResultV1(
    snapshot_id="snapshot-1",
    symbol="NIFTY",
    created_at=now,
    market_timestamp=now,
    engine_errors={"technical": ("Technical engine failed.",)},
)
```

The result remains serializable but has `analysis_valid=False`.

## Compatibility limitations

This version intentionally provides no adapters from legacy engine dictionaries. Legacy-to-analysis adapters should be introduced only during canonical pipeline implementation after the actual engine outputs are inventoried.

This avoids embedding legacy assumptions into the new canonical contract.
