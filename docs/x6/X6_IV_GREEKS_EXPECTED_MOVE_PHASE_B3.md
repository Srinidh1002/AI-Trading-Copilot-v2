# X6 Phase B3 — Captured-window IV summary, history and expected move

## Boundary

This is deterministic, data-only, offline research over X5-captured option premiums and X6-B2 model-implied sensitivities. No FYERS calls, execution, contract selection, independent Brain votes, risk/position changes, PAPER counting or authorization. This is **not** an IV index or market-wide IV surface.

## Inputs and source trust

- Require an immutable X6 capture, its exact X5 source, and an X6-B2 result that matches deterministic recalculation and the input content hashes.
- The *nearest captured strike* to the verified model reference price is ATM (lower strike wins exact distance ties). **Both CE and PE** must be calibrated at this strike; never substitute a farther complete pair.
- ATM IV = mean(CE IV, PE IV), in **decimal annualized volatility**, calibrated from premiums. It is not exchange-reported IV.
- ATM skew = (PE IV − CE IV) × 100 **volatility percentage points**. It is descriptive, not a bullish/bearish vote.
- Approximate expected move = model reference price × ATM decimal IV × sqrt(verified ACT/365 time to expiry). Its unit is the native underlying reference unit per unit (index points or MCX quoted unit). This is a *one-sigma scale approximation*, not an exact 68% interval, a guarantee, a stop-loss or a projected P&L. No multiplication by lot size, no annualized-to-daily time shortcut and no live quote inference.
- Missing, rejected, unverified or retrospectively derived inputs remain unavailable/retrospective as applicable.

## Historical comparisons

- Historical points are created through `make_x6_atm_history_point_v1` from replay-checked, **point-in-time** X6-B2 captures with a valid ATM CE/PE pair. A flag supplied by the caller is not independent proof of real provider timing.
- History must be strictly older and increasing, with distinct session IDs and capture IDs and identical market/model/price units. The consumer is responsible for preserving the source captures for independent audit; a frozen summary hash alone does not prove the source was authentic.
- Only the **same option expiry and same ATM strike** enter IV change and percentile. Roll transitions and strike-window movement are excluded and disclosed. These narrow restrictions prevent mixing maturities and moneyness; the result may be unavailable frequently in real deployments.
- IV change = current ATM IV − immediately preceding comparable ATM IV, reported in **volatility percentage points**; never a percent growth rate.
- Percentile = 100 × count(comparable prior IV <= current IV) / count(comparable prior IV). It is a descriptive **prior-sample percentile**, **not** IV Rank. Requires at least 20 distinct prior sessions by default (minimum configurable with explicit provenance); low <=25, high >=75, otherwise middle. No percentile or regime if there are too few comparable records. Retrospective current captures cannot receive historical change or percentile even if history is available.
- ATM IV, skew, expected move, change and percentile are derived from overlapping option premiums, sharing explicit dependency groups with `independent_vote=False`. They must not be counted as five independent directional confirmations.

## Verification and limitations

X6-B3 requires fixture regression, adversarial identity/provenance tests, source-authority scan and combined frozen Brain/X1–X6 regression. Live FYERS timestamp semantics, IV availability, dividends, rate conventions, futures binding, provider units and early-exercise/settlement behavior remain externally unproven. Point-in-time flags supplied by fixtures are not live certification; X6 is not wired to the production PAPER runtime.
