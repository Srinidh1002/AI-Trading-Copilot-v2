# ADR-001: Canonical Runtime Pipeline

- **Status:** Proposed
- **Date:** 2026-07-25
- **Decision owners:** Product Owner, System Architect
- **Applies to:** AI Trading Copilot v2
- **Related contracts:** `MarketSnapshot v1`, `FinalDecision v1`, runtime shadow adapters

## 1. Context

The repository currently contains two materially different runtime paths:

1. **Dashboard path**

   `app.py` → `dashboard/dashboard_v2.py` → `services.market_snapshot.get_market_snapshot` → `services.trade.trade_engine.analyze_trade`

2. **Live-option path**

   `live_option_decision_nifty.py` → `services.live_option_decision_pipeline.LiveOptionDecisionPipeline.analyse`

These paths do not currently share one canonical snapshot, one canonical analysis result, one canonical decision contract, or one common orchestration layer.

The project now has:

- `MarketSnapshot v1`
- `FinalDecision v1`
- Runtime shadow adapters
- A green configured test baseline
- Explicit paper-execution authorization
- A fail-closed contract strategy

The next objective is to create one canonical, side-effect-free decision pipeline before migrating dashboard, CLI, paper, audit, reporting, or future live execution.

## 2. Decision

The project will introduce a new canonical runtime orchestration path:

```text
Provider adapters
    ↓
Validation and normalization
    ↓
MarketSnapshot v1
    ↓
CanonicalAnalysisPipeline
    ↓
AnalysisResult v1
    ↓
CanonicalDecisionPipeline
    ↓
FinalDecision v1
    ↓
Immutable audit
    ↓
Dashboard / CLI / paper adapter / reports / controlled execution adapter
```

The new canonical pipeline will be implemented alongside current legacy runtime paths first. No existing entry point will switch until the canonical path passes focused, safety, contract, and full regression tests.

## 3. Canonical Responsibilities

### 3.1 Provider adapters

Provider adapters are responsible for:

- Fetching source data.
- Applying provider timeouts and bounded retries.
- Preserving source timestamps.
- Reporting provider errors.
- Avoiding decision logic.
- Avoiding paper or broker side effects.

Provider-specific response structures must not flow directly into analysis or decision engines.

### 3.2 Validation and normalization

This layer is responsible for:

- Instrument identity validation.
- Timestamp validation.
- Freshness calculation.
- OHLCV normalization.
- Multi-timeframe alignment.
- Missing, empty, stale, invalid, and valid source states.
- Safe construction of `MarketSnapshot v1`.

The canonical OHLCV schema remains:

```text
timestamp, open, high, low, close, volume
```

Stored column names are lowercase. Legacy consumers requiring uppercase data must receive it through explicit adapters.

### 3.3 MarketSnapshot v1

`MarketSnapshot v1` is the sole canonical market-input contract.

It contains:

- Instrument identity.
- Market and capture timestamps.
- Session status.
- Price summary.
- Partial multi-timeframe OHLCV data.
- Option-chain source status.
- India VIX source status.
- FII/DII source status.
- Provider/source health.
- Freshness.
- Validation errors and warnings.

It does not:

- Generate signals.
- Calculate final decisions.
- Authorize execution.
- Call paper or broker services.

### 3.4 CanonicalAnalysisPipeline

A new `CanonicalAnalysisPipeline` will orchestrate analysis only.

It may reuse verified logic from existing modules, but it will not expose their legacy response structures as its public contract.

Responsibilities include:

- Market regime analysis.
- Multi-timeframe trend analysis.
- Technical evidence.
- Price-action and market-structure evidence.
- Candlestick context.
- Volume confirmation.
- Option evidence.
- India VIX context.
- FII/DII or institutional context.
- Contradiction detection.
- Missing-input reporting.
- Engine-error isolation.

It emits `AnalysisResult v1`.

It does not:

- Execute trades.
- Persist paper positions.
- Call broker order APIs.
- Render dashboard components.
- Produce narrative that can contradict structured output.

### 3.5 AnalysisResult v1

`AnalysisResult v1` will be the typed internal contract between market analysis and decision authorization.

It will include:

- Snapshot identity.
- Analysis timestamp.
- Market regime.
- Directional bias.
- Trend strength.
- Volatility state.
- Multi-timeframe alignment.
- Technical evidence.
- Structure evidence.
- Candlestick evidence.
- Volume evidence.
- Options evidence.
- Institutional evidence.
- Supporting reasons.
- Contradictions.
- Missing inputs.
- Warnings.
- Engine errors.
- Data-quality state.
- Analysis validity.

It will not include:

- Paper execution state.
- Broker execution state.
- Mutable provider objects.
- Dataframes in serialized output.
- Direct calls to decision, paper, or broker services.

### 3.6 CanonicalDecisionPipeline

A new `CanonicalDecisionPipeline` will convert:

```text
MarketSnapshot v1 + AnalysisResult v1
```

into:

```text
FinalDecision v1
```

Its responsibilities include:

- Setup eligibility.
- Direction resolution.
- Evidence agreement.
- Contradiction handling.
- Confidence calculation.
- Trade-quality scoring.
- Institutional scoring.
- Risk validation.
- Trade-plan validation.
- Authorization assignment.
- Fail-closed final response construction.

It must return exactly one action:

- `BUY`
- `SELL`
- `WAIT`
- `HOLD`

It must separately return authorization:

- `BLOCKED`
- `ANALYSIS_ONLY`
- `PAPER_READY`
- `MANUAL_APPROVAL_REQUIRED`
- `AUTHORIZED`

It must separately preserve execution state.

### 3.7 FinalDecision v1

`FinalDecision v1` is the only canonical decision output for future consumers.

It is the sole allowed input for:

- Dashboard rendering.
- Paper candidate conversion.
- Alerts.
- Reporting.
- Audit.
- Future controlled live execution.

No consumer may recalculate or override direction, confidence, risk, authorization, or trade plan.

## 4. Existing Components to Reuse

### 4.1 Reuse from `LiveAnalysisPipeline`

The canonical analysis layer may reuse or adapt verified responsibilities for:

- Multi-timeframe analysis.
- Technical analysis.
- Candlestick analysis.
- Volume analysis.
- Market structure.
- Strategy-selection evidence.

Reuse is conditional on explicit dependencies, side-effect-free behavior, typed adapter output, no provider-specific contract leakage, and regression coverage.

The current `LiveAnalysisPipeline` response does not become the canonical internal contract.

### 4.2 Reuse from `LiveOptionDecisionPipeline`

The canonical decision layer may reuse or adapt verified safety concepts for:

- Market-session validation.
- Holiday handling.
- Stale-market rejection.
- Setup confirmation.
- Candle confirmation.
- Breakout confirmation.
- Option-chain authorization.
- Contract validation.
- ATR and trade-plan rejection.
- Decision audit behavior.

Current legacy status values remain compatibility inputs only. They do not become canonical actions.

### 4.3 Reuse from existing engines

The canonical pipeline may reuse existing trend, candlestick, volume, support/resistance, regime, option-chain, VIX, FII/DII, confidence, scoring, risk, and response-builder components only after a behavior inventory identifies one canonical owner per responsibility.

No duplicate engine may be added merely because it already exists.

## 5. Components Not Yet Declared Canonical

The following remain non-canonical until separate consolidation decisions are approved:

- Current decision engines.
- Current confidence engines.
- Current scoring engines.
- Current risk engines.
- Current response builders.
- Archive smart-money implementations.
- Archive market-structure implementations.
- Existing paper-trading orchestrators.
- Existing dashboard orchestration.
- Existing broker execution modules.

Their presence in the repository does not authorize direct use in the new canonical path.

## 6. Supported Entry Points During Migration

During the shadow and migration period, the supported user-facing entry points remain:

- Streamlit dashboard.
- Live-option CLI.
- Explicit paper-execution boundary.

Until migration is certified:

- Legacy runtime output remains official.
- Canonical runtime output remains shadow/test output.
- No consumer may use shadow output to execute or mutate state.

After migration, all supported entry points must call the same canonical application service.

## 7. Canonical Application Service

A future application-level service should expose a narrow API such as:

```python
analyse_market(snapshot: MarketSnapshotV1) -> FinalDecisionV1
```

or:

```python
run_decision_cycle(
    snapshot: MarketSnapshotV1,
    *,
    execution_context: ExecutionContext,
) -> FinalDecisionV1
```

The exact name will be selected during implementation.

This service must be side-effect free for analysis, use dependency injection, return deterministic contract output, isolate engine exceptions, fail closed, and avoid dashboard, database, paper, or broker concerns.

Audit persistence may be invoked through a separate explicit boundary after the decision is built.

## 8. Safety Ownership

### 8.1 Data safety

Owned by provider adapters, validation/normalization, and `MarketSnapshot v1`.

### 8.2 Analysis safety

Owned by `CanonicalAnalysisPipeline` and `AnalysisResult v1`.

Engine failures must become explicit analysis errors and must not create positive evidence.

### 8.3 Decision safety

Owned by `CanonicalDecisionPipeline` and `FinalDecision v1` invariants.

Critical errors, rejected risk, invalid plans, or failed data health must block authorization.

### 8.4 Paper safety

Owned by the explicit paper adapter and the existing hardened paper boundary until migration.

No dashboard refresh or analysis call may mutate paper state.

### 8.5 Live execution safety

Owned by a future controlled execution adapter.

No live execution is authorized by this ADR.

## 9. Error Boundaries

- **Provider failure:** unavailable or invalid source status in `MarketSnapshot v1`.
- **Normalization failure:** validation errors and an invalid snapshot.
- **Analysis-engine failure:** engine-specific error entries in `AnalysisResult v1`.
- **Decision-engine failure:** blocked `FinalDecision v1`.
- **Audit failure:** must not convert a blocked decision into an executable one.
- **Paper or broker failure:** updates execution state separately and must not rewrite the original decision.

## 10. Fail-Closed Rules

The canonical pipeline must return `WAIT` and/or `BLOCKED` when:

- Critical identity is invalid.
- Required market data is missing.
- Critical prices are NaN or infinite.
- Snapshot is stale beyond configured limits.
- Required timeframes conflict materially.
- Option data required for an options trade is unavailable or incomplete.
- No executable option contract is valid.
- Risk validation fails.
- Trade plan is invalid.
- Required analysis engines fail.
- Direction is ambiguous.
- Unsupported legacy status is encountered.
- Authorization cannot be proven.

Missing optional context may reduce confidence or add warnings, but must never be treated as positive evidence.

## 11. Migration Sequence

1. Create and certify `AnalysisResult v1`.
2. Create a canonical analysis pipeline consuming `MarketSnapshot v1` and emitting `AnalysisResult v1`.
3. Create a canonical decision pipeline consuming `MarketSnapshot v1` and `AnalysisResult v1`, then emitting `FinalDecision v1`.
4. Run canonical and legacy paths in comparison mode with no state mutation.
5. Migrate the dashboard behind a rollback switch.
6. Migrate live-option CLI output to `FinalDecision v1`.
7. Migrate paper candidate generation to consume only `FinalDecision v1`.
8. Migrate audit and reporting consumers.
9. Remove direct runtime calls to legacy decision and risk paths.
10. Deprecate and later retire obsolete public APIs after parity and regression evidence.

## 12. Rollback Strategy

Until canonical migration is certified:

- Legacy runtime remains available behind a temporary compatibility switch.
- Canonical output must not mutate legacy state.
- Dashboard and CLI migrations must be independently reversible.
- Database schema changes are prohibited during early migration unless separately approved.
- Paper and broker execution remain behind explicit boundaries.
- Each migration step requires a clean full-suite result before the next step.

The rollback switch is temporary and must not become permanent architecture.

## 13. Testing Strategy

Testing is performed manually by the project owner.

Required levels:

### Focused contract tests

- `MarketSnapshot v1`
- `AnalysisResult v1`
- `FinalDecision v1`
- Runtime adapters

### Pipeline tests

- Valid full analysis.
- Partial optional data.
- Missing critical data.
- Stale snapshot.
- Analysis-engine exception.
- Ambiguous direction.
- Risk rejection.
- Invalid trade plan.
- Deterministic serialization.

### Entry-point tests

- Dashboard analysis.
- Live-option CLI.
- Explicit paper candidate.
- No paper or broker side effects during analysis.

### Full regression

Current certified baseline:

```text
2,751 passed
0 failed
0 skipped
2 pre-existing warnings
```

Any failure after this ADR is a new regression unless explicitly approved.

## 14. Prohibited Architecture

The following are prohibited:

- Dashboard directly calling multiple business engines.
- Dashboard calculating action, confidence, risk, or authorization.
- Analysis functions calling paper execution.
- Decision functions calling broker execution.
- Provider-specific dictionaries passed directly into decision engines.
- Multiple canonical decision engines.
- Multiple canonical risk engines.
- `archive.*` imports in the final canonical runtime.
- `exec(compile(...))` wrappers in the final canonical runtime.
- Hidden global provider/client construction when dependencies are injected.
- Treating `TRADE_READY` or `TRADE_ALLOWED` as canonical actions.
- Treating missing inputs as neutral positive evidence.
- Automatic live execution during this phase.

## 15. Consequences

### Positive

- One controlled path from data to decision.
- Clear separation of analysis and authorization.
- Stable contracts for dashboard, paper, audit, and future live execution.
- Easier testing and replay.
- Safer migration away from duplicate engines.
- Reduced dashboard and provider coupling.
- Explicit failure handling.

### Costs and tradeoffs

- Temporary coexistence of canonical and legacy paths.
- Additional adapters during migration.
- Some duplicated computation during comparison mode.
- More explicit contract and compatibility tests.
- Legacy modules cannot be removed immediately.
- Engine consolidation remains separate.

## 16. Deferred Decisions

This ADR does not decide:

- Final scoring weights.
- Final confidence formula.
- Final risk formula.
- Approved strategy library.
- Final news provider.
- Final broker execution adapter.
- Database technology.
- Deployment platform.
- Autonomous live execution.
- Capital or profit targets.

These require separate evidence and approval.

## 17. Acceptance Criteria

This ADR is accepted when the project owner confirms:

- The new pipeline will be additive before migration.
- `MarketSnapshot v1` is the sole canonical input.
- `AnalysisResult v1` will be the sole canonical internal analysis contract.
- `FinalDecision v1` is the sole canonical output.
- Existing live-analysis and live-option modules are reuse sources, not automatically canonical as-is.
- Dashboard, paper, and broker concerns remain outside analysis and decision pipelines.
- Fail-closed behavior is mandatory.
- Runtime migration happens only after independent canonical pipeline tests pass.

## 18. Decision Summary

The AI Trading Copilot will not promote either current legacy runtime path unchanged.

It will introduce a new canonical orchestration layer that reuses verified components behind typed contracts:

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

All user-facing and execution-related consumers will be migrated to this path only after it is independently validated.
