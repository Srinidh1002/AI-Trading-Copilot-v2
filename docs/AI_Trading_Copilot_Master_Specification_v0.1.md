# AI Trading Copilot — Master Product & System Specification

**Version:** 0.1  
**Status:** Foundation draft for Codex audit and build  
**Primary market focus:** India — NIFTY 50, SENSEX and Futures & Options

> This system is intended as a decision-support and risk-control product. It must not promise profits, guarantee accuracy, or execute unrestricted live trades.

## 1. Product Mission

Build an Indian-market AI Trading Copilot that continuously gathers relevant market evidence, evaluates trade quality, rejects weak or unsafe setups, and produces one clear, explainable, risk-controlled decision for the trader.

The app is not another charting tool or a collection of indicators. Its value is the decision layer: combining technical data, price action, derivatives positioning, market context and risk controls into an actionable recommendation.

## 2. Core Product Goal

- Understand the current market state before looking for a trade.
- Combine multiple independent categories of evidence rather than relying on one indicator.
- Distinguish between a market opinion and an executable trade setup.
- Recommend `WAIT` when evidence is incomplete, contradictory, stale or low quality.
- Provide entry, invalidation, targets and position sizing only after risk checks pass.
- Explain why the trade is valid, what could invalidate it and what the trader must watch.
- Record every recommendation and outcome for later validation and performance analysis.

## 3. Product Boundaries

The app must analyze and rank evidence, produce `BUY`, `SELL`, `WAIT` or `HOLD`, calculate a risk-controlled trade plan, support manual confirmation and maintain an audit trail.

The app must not guarantee profit, force trades, hide uncertainty, enable unrestricted autonomous execution in early phases, or change its own rules without controlled validation.

## 4. Target Market and Modes

Initial scope:

- NIFTY 50 and its liquid Futures & Options instruments.
- SENSEX and its liquid Futures & Options instruments.
- Indian market hours, expiry behaviour, holidays and exchange-specific rules.

Operating modes:

1. Research — no execution.
2. Live Analysis — live/read-only feeds, no automatic orders.
3. Paper Trading — simulated orders and P&L.
4. Limited Live — small capital with manual confirmation.
5. Advanced Live — future controlled automation only after governance approval.

## 5. End-to-End Behaviour

1. Verify market session, feed health, timestamps and instrument identity.
2. Collect market data across required timeframes.
3. Normalize inputs into stable contracts.
4. Determine market regime.
5. Run technical, price-action, structure, options, institutional, volatility, global and news analysis.
6. Evaluate alignment and contradiction.
7. Generate bullish, bearish or neutral bias.
8. Reject invalid setups through mandatory filters.
9. Calculate trade quality, confidence, entry, stop, targets and size.
10. Produce exactly one action: `BUY`, `SELL`, `WAIT` or `HOLD`.
11. Explain the decision and invalidation conditions.
12. Write an immutable audit record.
13. Track outcome and performance.

## 6. Required Input Categories

### Market and Price Data
LTP, timestamps, OHLCV, multi-timeframe candles, previous close, session levels, gaps, range expansion, price velocity, market breadth and sector/index context where available.

### Multi-Timeframe Context
Execution, confirmation and higher timeframes; alignment, conflict and transition.

### Technical Evidence
Trend, moving-average structure, VWAP, RSI, MACD, ADX, ATR, volatility, volume, support, resistance and pivots.

### Price Action and Market Structure
HH/HL/LH/LL, breakout, breakdown, retest, pullback, failed breakout, range, BOS, CHOCH, supply/demand, liquidity zones, order blocks and fair value gaps where testable.

### Candlestick Context
Reversal, continuation and indecision patterns, always evaluated with location, volume and timeframe. Candles alone cannot authorize trades.

### Options and Derivatives
Option-chain health, PCR, OI, change in OI, writing/unwinding, buildups, option volume, liquidity, spreads, max pain as secondary context, Greeks where dependable and expiry effects.

### Institutional and Flow
FII/DII activity, cash/derivatives positioning, institutional alignment and participation measures where available.

### Volatility
India VIX, realized volatility, ATR, expected range and abnormal expansion/contraction.

### Global and Macro
GIFT NIFTY, major global markets, USD/INR, crude, bond yields, RBI and major macro events.

### News and Event Risk
Scheduled events, breaking news, source quality, recency and explicit uncertainty.

## 7. Data Quality Rules

Missing values must not be invented. Stale or timestamp-mismatched inputs must reduce confidence or block the trade. NaN, duplicate, malformed and outlier data must be handled deterministically. API failure must return a valid safe response.

## 8. Market Regime

The app must classify at least:

- Trending
- Ranging
- Breakout transition
- High volatility
- Low liquidity
- Event-driven
- Uncertain/conflicted

Regime must influence setup rules and trade authorization.

## 9. Decision Hierarchy

1. Data validity
2. Market state
3. Setup detection
4. Independent confirmation
5. Contradiction analysis
6. Risk viability
7. Institutional-quality filter
8. Final action

A directional opinion is not an executable trade.

## 10. Mandatory Trade Filters

- Data health
- Trend/context
- Multi-timeframe alignment
- Market structure
- Volume
- Options
- Volatility
- News/event safety
- Risk/reward
- Liquidity

Failure of a mandatory condition must produce `WAIT` or reduce size/confidence according to an explicitly approved rule.

## 11. Signal Definitions

- `BUY`: qualified bullish setup with entry, invalidation, targets, size and reasons.
- `SELL`: qualified bearish setup with entry, invalidation, targets, size and reasons.
- `WAIT`: no safe new trade; exact blockers and next confirmation required.
- `HOLD`: an existing position remains valid; include trailing and exit triggers.

## 12. Confidence and Scoring

Confidence represents evidence quality and agreement, not certainty. Component scores should include technical, options, institutional, risk, data quality and final trade quality. Strong conflicts must cap confidence.

## 13. Risk Engine

- Size positions from account capital and allowed risk.
- Define stop-loss from market invalidation.
- Include lot size, premium, spread, charges and slippage.
- Reject trades that exceed maximum-loss rules.
- Enforce daily loss, consecutive loss and exposure limits.
- Reduce/block risk during abnormal volatility, low liquidity and major events.

Required outputs: entry zone, stop, targets, risk/reward, position size, maximum planned loss, time stop and trailing rule.

## 14. Options Contract Selection

After direction is approved, the app must validate expiry, strike, liquidity, OI, spread, premium, time decay and capital compatibility. It may approve the market direction but reject the available option contract.

## 15. Final Output Contract

Every response must include:

- Identity and timestamps
- Action
- Market state
- Trade plan or `null`
- Risk
- Confidence and component scores
- Supporting evidence
- Contradictions and blockers
- Options interpretation
- Invalidation conditions
- Execution status
- Data health and audit data

Conceptual contract:

```json
{
  "decision_id": "...",
  "timestamp": "...",
  "symbol": "NIFTY",
  "action": "WAIT",
  "market_state": {
    "regime": "BREAKOUT_TRANSITION",
    "direction": "BULLISH",
    "volatility": "ELEVATED"
  },
  "scores": {
    "confidence": 0,
    "trade_quality": 0,
    "data_quality": 0,
    "institutional_score": 0
  },
  "trade_plan": null,
  "supporting_reasons": [],
  "contradictions": [],
  "blocking_reasons": [],
  "invalidation_conditions": [],
  "data_health": {},
  "audit": {}
}
```

## 16. Explainability

Every decision must rank supporting evidence, state contradictions, explain blockers, list invalidation conditions and distinguish observed facts from interpretations. Narrative output must never contradict the structured contract.

## 17. Audit and Journal

Record unique decision ID, snapshot ID, source timestamps, engine/rule versions, component outputs, scores, blockers, risk plan, user overrides, simulated/live execution, slippage, charges and P&L.

## 18. Paper Trading and Validation

Use historical replay without look-ahead bias, walk-forward testing, real-time paper trading and realistic costs. Review at least 100 initial paper trades before limited live use, followed by broader validation.

Metrics: win rate, expectancy, profit factor, drawdown, achieved risk/reward, stop adherence, calibration, WAIT quality and system reliability.

## 19. Fail-Safe Behaviour

Critical feed failure, stale snapshots, symbol/expiry mismatch, abnormal spreads, risk-limit violations, exceptions, unresolved event risk or missing position data must block unsafe output and return a valid safe response.

## 20. Architecture Principles

- One responsibility per engine.
- Stable typed contracts.
- No business logic in UI.
- No overlapping production decision engines.
- Replaceable data providers.
- Deterministic testable analysis.
- Clear separation of I/O, normalization, analysis, decision, risk, execution and presentation.
- No archive module in production without an approved migration.
- Centralized versioned configuration.

Target flow:

```text
Market/Data Providers
        ↓
Validation + Normalization
        ↓
Market Snapshot Contract
        ↓
Analysis Engines
        ↓
Market Regime + Setup Detection
        ↓
Decision / Confirmation / Contradiction Engine
        ↓
Institutional Trade Filters
        ↓
Risk Engine + Options Contract Selection
        ↓
Final Response Builder
        ↓
Audit + Journal
        ↓
Dashboard / Alerts / Paper Trading / Controlled Execution
```

## 21. Testing

Unit, contract, integration, regression, data-quality, replay, paper-execution, reliability and safety tests are mandatory. Every fail-safe must prove that unsafe BUY/SELL output cannot escape.

## 22. Codex Governance

1. Audit before changing code.
2. Approve architecture decisions.
3. Specify one task at a time.
4. Implement in a feature branch.
5. Run automated verification.
6. Review logic and unintended changes.
7. Certify with evidence.
8. Merge in a controlled way.

## 23. Phase 0 Repository Audit

Phase 0 is observation only. Codex must produce:

- `docs/audit/00_EXECUTIVE_SUMMARY.md`
- `docs/audit/01_REPOSITORY_INVENTORY.md`
- `docs/audit/02_RUNTIME_AND_DATA_FLOW.md`
- `docs/audit/03_DUPLICATION_AND_DEAD_CODE.md`
- `docs/audit/04_CONTRACT_AND_ARCHITECTURE_GAPS.md`
- `docs/audit/05_TEST_AND_SAFETY_GAPS.md`
- `docs/audit/06_RECOMMENDED_TARGET_ARCHITECTURE.md`
- `docs/audit/07_PRIORITIZED_REMEDIATION_PLAN.md`

### Initial Codex Audit Instruction

```text
You are performing Phase 0 of the AI Trading Copilot project.

Read the entire repository before making conclusions. Do not modify production code, tests, configuration, or documentation during this task.

Use AI_Trading_Copilot_Master_Specification_v0.1.md as the intended product and system baseline. Do not assume the current repository already follows it.

Produce an evidence-based audit with exact file paths, symbols and dependency relationships. Identify:
1. Runtime entry points and the actual production decision path.
2. Duplicate, overlapping, legacy and archive implementations.
3. Data-provider, normalization, analysis, decision, risk, response, audit, dashboard and paper-trading flows.
4. Inconsistent contracts, naming, casing, defaults and error handling.
5. Unsafe paths that could return BUY/SELL with missing, stale, partial or contradictory data.
6. Dead code and modules with no verified callers.
7. Circular imports and fragile compatibility wrappers.
8. Test collection status, failing groups, missing safety coverage and likely test/code mismatches.
9. Hard-coded thresholds, scattered configuration and secrets risks.
10. Recommended keep / merge / migrate / rewrite / retire classification for each major module.

Do not fix issues yet. Create the audit documents listed above. End with a prioritized remediation plan that separates critical safety blockers, architecture blockers, correctness defects, test gaps, maintainability improvements and optional future features.

Where evidence is incomplete, say UNKNOWN and specify what must be run or inspected to verify it.
```

## 24. Definition of Done

A task is complete only when requirements and non-goals are documented, contracts approved, implementation remains in scope, tests pass, fail-safe behaviour is verified, regressions are absent, documentation is updated and evidence supports certification.

## 25. Open Decisions for Version 0.2

- Live data providers
- Mandatory timeframes
- Score weights and thresholds
- Approved setup library
- Strike selection
- Risk and daily loss limits
- Event lockout windows
- Database/deployment stack
- Broker execution integration

These must be decided after Phase 0 reveals the actual repository.

## 26. Final Product Statement

The completed AI Trading Copilot will observe the market, validate data, identify regime, detect qualified setups, combine independent evidence, reject unsafe opportunities, calculate a risk-controlled plan, explain the result and record every decision for objective validation.

Its promise is not that it will always be right. Its promise is that it will follow a transparent, testable and disciplined process before recommending that the trader take risk.
