# X3 Shadow Technical & Structure V2 — Detached implementation patch

**Status:** Locally tested patch; not frozen, not committed to GitHub, and not
validated against the full Windows repository. The branch baseline used to
prepare the patch is X2 `a4686cfb90782c97f2202055fed085018674f064`.

## Architecture

The new `services/x3` namespace is additive. Nothing imports X3 from any
trading runner. It accepts independently validated, already supplied candle
series; does not authenticate, subscribe, fetch data, access credentials,
or call execution or certification logic.

- `indicator_extensions_v1.py`: stochastic K/D, CCI, Williams %R, Aroon,
  Money Flow Index, ROC, momentum and volume change. The implementations
  return `None` for invalid or insufficient data; all formulas use finite
  numbers and explicit warm-up periods.
- `pipeline_v1.py`: lazily reuses `services.technical_intelligence.indicators`
  for existing EMA, RSI, MACD, ADX, ATR, Bollinger and an OHLCV-weighted
  price **VWAP proxy**; existing code and production policy remain unchanged.
- `series_validation_v1.py`: strictly requires an upstream READY / READY_WITH_WARNINGS
  quality assessment, completed and chronologically valid candles, explicit
  `as_of`, and no unverified same-session gaps. Cross-date session validity
  remains an upstream market-calendar responsibility.
- `structure_v1.py`: strictly confirmed left/right pivots. A pivot at index `i`
  is first visible after candle `i + lookback` has closed. Breakouts and retests
  are observed only on later completed candles.
- `patterns_v1.py`: completed-candle shapes and conditional contextual
  confirmations. Doji and unconfirmed hammer/star shapes are NON_DIRECTIONAL.
- `contracts_v1.py`, `family_normalization_v1.py`: immutable, versioned results
  with deterministic JSON hashes. Each technical family yields at most one
  state. A higher number of correlated features never creates extra votes.
- `multi_timeframe_v1.py`: preserves missing timeframes and conflicts. It does
  not substitute 5m for missing 1h/daily data or generate market-level scores.
- `research_view_v1.py`: carries independent X2 and X3 result hashes; no
  combined trade score, strategy, confidence formula or CALL/PUT decision.
- `feature_manifest_v1.py`: provisional dependency families. The official V2
  analyzer registry and snapshot belong to X9, Shadow Brain V2 to X10.

## Indicators and conventions

Stochastic: %K uses high/low of the last `period` bars and current close;
%D is the SMA of the most recent `smooth` %K observations. Zero high-low
range is 50 (non-directional). CCI uses the population mean absolute
deviation of typical price. Williams %R spans -100..0; zero range is -50.
Aroon requires `period+1` bars, and same-value extrema prefer the newest.
MFI uses the previous typical price and the most recent `period` positive
and negative money flows. Entirely absent traded volume is unavailable.
ROC is percent change, momentum is raw price-unit change and volume change
is percent change. Overbought/oversold levels alone confer no trade signal.

The VWAP proxy is an OHLCV typical-price approximation using bars from the
latest India trading date. It is **not** exchange/trade-level VWAP and is
unavailable for daily candles or when trade-volume semantics are unavailable.

## Data and causality constraints

- The caller must supply an existing trusted, replayable, quality-checked
  candle-series source. The X1 streaming bridge publishes quotes, and does
  **not** construct historical candles, verified index weights or sectors.
- Daily/weekend/holiday and cross-session gaps require the existing upstream
  session authority to validate them. A `READY` string must never be
  synthesized when that authority has not validated the source.
- Only candles with end_at <= as_of and is_complete=True are eligible.
- If an incomplete candle is last, it is excluded with a warning; an incomplete
  candle in the middle of history blocks evaluation.
- Snapshot IDs, timeframes, source series IDs and evidence hashes are retained.
- The same price data in multiple timeframes must not be mistaken for
  statistically independent evidence.
- Feature-family results do not own risk, execution, broker order, position,
  trading-decision, certification or market-level aggregation authority.
- Five-market compatibility is numerical/data-contract coverage; there is
  no live FYERS proof for all instruments.

## Local verification and repository gates

The detached patch's standalone tests cover mathematical reference examples,
contracts, family conflicts, swing confirmation, breakout/retest, pattern
classification, source quality, incomplete candles, five-market numeric
path coverage, deterministic replay hashes, MTF missing data and X2/X3
research-envelope invariants.

`test_x3_reuse_canonical_v1.py` is an additional repository-only integration
test for the actual existing primitive package and must pass in the full repo.

The following remain **unverified here**, so X3 cannot be marked frozen:

1. Run repository-only canonical primitive integration.
2. Run all X1 (173), X2 (110), new X3 and existing technical tests together.
3. Reproduce the frozen B4.6 test gate (1,001 pass/10 known skips).
4. Run full repository syntax and Ruff checks; check PAPER/live-state paths.
5. Review the code against the actual complete repository and record a scoped
   X3 commit on `x23-shadow-features-v2` only after gates pass.
6. Demonstrate replay using actual X1 historical candle evidence where
   a valid, quality-controlled historical source is available.
7. Source-specific sector/index weights remain X2 upstream requirements.
8. Additional exact session calendar alignment and provider-time freshness
   require actual upstream evidence. They are not inferred from wall time.

This detached patch is an implementation deliverable, not an X3 completion
certificate or authorization to begin X4.

## X3 additional structure/pattern modules

- `session_levels_v1.py`: previous observed India trading date high, low,
  close, floor pivot P/R1/S1 and signed opening-gap percentage. These
  levels remain UNAVAILABLE when the previous session is not represented;
  gap direction alone is NON_DIRECTIONAL evidence.
- `chart_patterns_v1.py`: double top/bottom is confirmed only after two
  confirmed similar pivots, an intervening neckline and a subsequent closed
  candle crossing the neckline. Unconfirmed candidates confer no signal.

The existing SMA20/SMA50 and MACD line/signal/histogram are exposed separately
without multiplying the trend or momentum family vote. Bollinger lower,
mid, upper and width similarly belong to one VOLATILITY family.

Use `VERIFY_X3.ps1` in the complete Windows repository to run the new
repo-only canonical integration test, all X1/X2/X3 tests, provider regressions,
all 48 frozen regression modules, syntax, Ruff and live-state isolation.
It does not create a commit or push anything.
