# P5-3 — Canonical multi-timeframe intelligence

- Added canonical structural multi-timeframe contracts, quality-gated evidence,
  deterministic alignment, and no-fetch pipeline boundaries. Certification:
  `7645 passed, 2 warnings in 17.94s`.

# P5-2 — Provider-neutral data quality and freshness

- Added provider-neutral provenance, quote/candle/series, freshness, quality,
  and consensus contracts/evaluators without provider or cache migration.
- Certification: `7023 passed, 2 warnings in 18.52s`.

# P5-1 — Canonical four-market universe

- Added immutable ordered four-market universe contracts and a provider-neutral
  static mapping adapter; legacy mappings remain contained, not migrated.
- No live-provider, network, or P3/P4 execution behavior changed. P5-1
  certification: `6381 passed, 2 warnings in 17.36s`.

# P5-0 — Data and intelligence audit

- Completed the audit-only P5-0 inventory; no runtime behavior changed.
- Documented data/intelligence risks and set P5-1 canonical four-market
  universe as the next scope. Certification: `6044 passed, 2 warnings in
  16.38s`; warnings are the pre-existing SmartAPI TLS deprecations.

# P4-7 — Final Phase 4 certification

- Certified the safe paper-entry architecture for NIFTY, BANKNIFTY, FINNIFTY,
  and SENSEX across BUY/CALL/LONG and SELL/PUT/LONG only.
- Confirmed explicit manual authorization, deterministic paper execution,
  process-local repositories, read-only replay, no persistence, and no live or
  automatic execution.
- Final certification: `6009 passed, 2 warnings in 16.45s`; warnings are the
  pre-existing SmartAPI TLS deprecations.

# P4-6 — Deterministic paper execution replay and observability

- Added immutable canonical paper-execution observations, a process-local
  observation repository, and deterministic read-only replay.
- Added four-index traceability with no second execution, automatic storage,
  persistence, or live execution.
- Certification: `425 passed` focused and `5527 passed, 2 warnings` full
  suite; warnings are the pre-existing SmartAPI TLS deprecations.

# P0-1 — Configuration import compatibility

- Restored `from config import ...` compatibility by re-exporting historical
  root `config.py` constants from the `config` package without changing values.
# P0-2 — Dashboard paper-trade side-effect separation

- Made dashboard trade analysis read-only and introduced explicit
  `execute_paper_trade(analysis_result)` submission.
# P0-3 — Entry-point fail-safe verification matrix

- Added deterministic fail-safe verification coverage and documented supported
  decision entry-point safety status, including known unsafe paper-boundary gaps.
# P0-4 — Explicit paper-execution boundary hardening

- Added fail-closed validation to explicit legacy paper execution and stable
  non-mutating rejection responses for malformed or unapproved results.
# P1-1 — MarketSnapshot v1 contract

- Added a typed, versioned, side-effect-free market snapshot contract with
  lowercase OHLCV normalization, validation, serialization, and legacy adapters.
# P1-2 — FinalDecision v1 contract

- Added a typed, versioned, side-effect-free final-decision contract with
  separate action, authorization, execution, typed plan/risk, and fail-closed adapters.
# P1-3 — Runtime shadow contract adapters

- Added opt-in, side-effect-free dashboard/live shadow adapters and deterministic
  diagnostics without changing runtime routing or legacy outputs.

# P2-1 — Green baseline compatibility remediation

- Restored fail-closed broker empty-response handling, fresh-only request cache
  behavior, injectable live-data/analysis constructors, and injected-client
  propagation through default live-option dependencies.

# P2-4 — Additive canonical pipeline

- Added an explicit, side-effect-free canonical path from `MarketSnapshotV1`
  through `AnalysisResultV1` to an analysis-only `FinalDecisionV1`; no legacy
  runtime route or execution boundary was migrated.

# P2-5 — Canonical/legacy diagnostic comparison

- Added opt-in dashboard and live-option comparison APIs that report semantic
  differences between supplied legacy payloads and canonical contract output
  without changing runtime behavior or execution state.

# P2-6 — Dashboard canonical analysis migration

- Routed the dashboard analysis boundary through a temporary canonical/legacy/
  compare application service; canonical output is default, read-only, and
  analysis-only, with an explicit legacy rollback mode.

# P2-7 — CLI canonical analysis and paper separation

- Added explicit canonical CLI analysis, paper-candidate preparation, and
  paper-submission boundaries, plus an immutable candidate contract; canonical
  decisions remain plan-free and cannot automatically prepare or execute paper trades.

# P3-2 — Structured observability

- Added opt-in typed audit events, bounded redaction, no-op/in-memory/JSONL
  sinks, and dependency-injected canonical/replay lifecycle diagnostics.

# P3-4C3 — Canonical option and trade-plan observability

- Added fail-open, bounded audit events for option selection and trade-plan
  construction, plus deterministic synthetic replay scenario coverage.

# P3-5A — Risk policy and position-sizing contracts

- Added immutable validation-only risk-policy and position-size-result
  contracts. No sizing runtime, paper integration, or execution path was added.

# P3-5A1 — Position-size blocked identity compatibility

- Allowed honest absent selected-contract identity on non-approved position-size
  results while preserving complete-identity requirements for approval.

# P3-5A2 — Position-size blocked direction compatibility

- Allowed non-approved position-size results to preserve `WAIT` with no option
  type, without weakening approved BUY/CALL and SELL/PUT validation.

# P3-5B — Deterministic position sizing

- Added an isolated, deterministic P3-5B sizing service based on supplied trade
  plans and risk policy limits; it remains non-executable and side-effect free.

# P3-5C — Risk validation integration

- Added a typed canonical risk-validation result and a deterministic wrapper around P3-5B sizing; no execution integration was added.

# P3-5D — Paper-preparation integration

- Added an optional approved-canonical-risk preparation path that creates a
  sized paper candidate without submitting an order.

# P3-5E0 — Risk observability vocabulary

- Added controlled P3-5 position-sizing, risk-validation, and paper-preparation
  audit lifecycle event types without adding runtime hooks.

# P3-5E — Replay coverage and optional observability hooks

- Added deterministic risk-sizing replay coverage and opt-in fail-open,
  bounded audit lifecycle hooks for sizing, canonical-risk validation, and
  canonical-risk paper preparation. No execution behavior changed.

# P4-0 — Execution-readiness audit and roadmap lock

- Completed a static execution-readiness audit and a bounded manual-paper
  execution roadmap. No runtime behavior changed, no execution was enabled,
  and Codex did not run tests.

# P4-1 — Canonical paper execution contracts

- Added immutable deterministic paper execution request, result, and order-state
  contracts with focused tests. No executor, broker/provider calls, runtime
  routing change, or execution enablement was added; Codex did not run tests.

# P4-2 — Manual paper execution authorization

- Added manual authorization and validation-result contracts plus a deterministic validator. No executor, authorization-consumption state, routing change, or execution enablement was added; Codex did not run tests.

# P4-3 — Deterministic paper executor

- Added an explicit immediate full-fill paper executor with optional in-memory idempotency. No live or legacy execution, broker/provider/network/database/filesystem behavior, retries, partial fills, slippage, or fees were added; Codex did not run tests.

# P4-3A0 — Four-index identity audit

- Started the four-index identity audit for future BANKNIFTY and FINNIFTY support. No runtime behavior or tests changed, and Codex did not run tests.

# P4-3A1 — Shared canonical identity registry

- Added an immutable four-index identity registry and delegated the existing market-session identity API to it. No contracts, formulas, or execution behavior changed; Codex did not run tests.

# P4-3A2 — P3 four-index compatibility

- Expanded P3 option-contract, trade-plan, position-size, and sizing identity gates to the shared four-index registry with focused coverage. No formulas, scoring, lot-size ownership, or execution behavior changed; Codex did not run tests.

# P4-3A3 — P4 four-index compatibility

- Expanded P4 request, authorization, result, validator, and deterministic executor compatibility to the shared four-index registry. No formulas, authorization semantics, idempotency behavior, persistence, or execution enablement changed; Codex did not run tests.

# P4-3A4 — Four-index replay and certification

- Certified deterministic NIFTY/BANKNIFTY/FINNIFTY/SENSEX paper-execution compatibility: 4,667 tests passed with two pre-existing SmartAPI TLS warnings. No formulas or scoring changed, and no live execution was enabled.

# P4-4 — Canonical paper execution pipeline

- Added explicit canonical paper execution orchestration with bounded result mapping and four-index support. No analysis, decision, selection, planning, sizing, risk, or session reruns, legacy executor, or live execution was added; Codex ran tests.

- Made the historical `services.core.get_market_snapshot` import lazy to avoid
  loading the snapshot dependency graph when importing the identity registry.

# P3-5A3 — Paper single-target compatibility

- Allowed paper candidates to preserve a validated single target without
  fabricating an additional target; multi-target validation remains strict.

# P3-5A4 — Paper candidate position side

- Added controlled long/short premium-side validation so SELL/PE long-option
  candidates can be represented without changing legacy SELL/SHORT defaults.

# P3-1B — Offline replay scenario coverage

- Added deterministic synthetic NIFTY/SENSEX replay fixtures, stable expanded
  expectation checks, and an isolated directory suite runner with typed
  aggregate results; no runtime route or trading formula changed.
# P4-5

- Added the canonical in-memory paper-order repository with deterministic
  ordering, lookup, uniqueness checks, and atomic controlled transitions.
- Added four-index repository coverage without persistence or automatic
  execution; live execution remains disabled.
- Added canonical `underlying_symbol` and `exchange` to `PaperOrderStateV1`;
  repository identity filters use stored fields and never infer from a trading
  symbol.
- P4-5 identity certification: `257 passed` focused and `5102 passed, 2
  warnings` full suite; warnings are the pre-existing SmartAPI TLS deprecations.
# P5-4 — Canonical technical intelligence

- Added immutable technical evidence contracts, deterministic indicators,
  category intelligence, timeframe analysis, non-renormalized aggregation, and
  a paper-only four-index pipeline.
- Added completed-candle/look-ahead protections and lazy contract-export import
  isolation. No providers, fetching, caching, resampling, option, regime,
  decision, ranking, risk, or execution behavior was introduced.
