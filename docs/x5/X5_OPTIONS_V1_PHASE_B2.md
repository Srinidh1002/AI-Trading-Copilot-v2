# X5-B2 — Offline option-chain analytics over verified captured windows

New files: `services/x5/analytics_v1.py`, `tests/test_x5_analytics_v1.py`, this document. The phase does not change A/B1, FYERS provider code, Brain V1 registry, X1–X4, any strategy, PAPER state or trading runner.

## Input and scope

`analyze_x5_chain_v1(capture=..., max_age_seconds=...)` recomputes `validate_x5_chain_v1` on the supplied immutable `X5ChainCaptureV1`. Only metrics whose exact readiness is `AVAILABLE` can run. If capture metadata, expiry, freshness or point-in-time provenance fails, all nine metrics remain unavailable. Existing B1 source flags are caller-supplied evidence claims; these tests do not verify live FYERS data semantics.

**Every result refers only to `CAPTURED_STRIKE_WINDOW`.** Equal CE/PE strike coverage within a truncated FYERS `strikecount` window does not establish complete exchange-wide coverage. Never label PCR, max pain, strike levels or total OI as exchange-wide values; they are conditional on the supplied strike range.

## Nine descriptive metrics

1. `PCR_OI`: verified PUT OI divided by verified CALL OI. A zero CALL denominator returns `UNAVAILABLE`; zero PUT total is a legitimate zero ratio.
2. `PCR_VOLUME`: analogous volume ratio using independently verified, consistent volume units and timestamp semantics.
3. `MAX_PAIN`: settlement strike minimizing the sum of intrinsic CALL+PUT payout weighted by verified OI. Ties are resolved by minimum distance to separately verified underlying price and then lower strike. This is an observed concentration model, not a price target.
4. `OI_CONCENTRATION`: largest combined CE+PE strike OI divided by total captured-window OI. Zero total OI returns unavailable.
5. `OI_BUILDUP`: `(sum(PUT signed OI change) - sum(CALL signed OI change)) / (abs(sum(PUT change)) + abs(sum(CALL change)))`, zero if both changes are zero. Every row needs verified absolute signed change and the **same comparison-window baseline ID**. Differing per-option source/baseline IDs are not treated as proof of window comparability by B2; the metric becomes unavailable. B1 can supply per-symbol baseline IDs, so B1-ready status alone does not guarantee B2-ready OI buildup.
6. `OI_SUPPORT_RESISTANCE`: highest verified PUT OI at/below underlying and highest CALL OI at/above underlying; deterministic ties use distance then strike. The scalar is separation in basis points and the selected strikes/weights are in metric `detail`. Both sides must exist. These are descriptive OI levels, not guaranteed support or resistance.
7. `IV_SKEW`: mean verified PUT IV minus mean verified CALL IV in percentage points. Verified `DECIMAL` inputs are converted by 100; mixed or unverified units remain unavailable.
8. `QUOTE_SPREAD`: mean quoted `(ask - bid)/mid * 10000` in basis points. Verified option-premium units and strictly positive midpoints are required; no LTP fallback.
9. `GREEKS`: descriptive mean absolute delta; CE/PE average deltas plus gamma/theta/vega averages are in `detail`. Only available if all four Greek fields are verified for each row. No theoretical Greek is imputed.

These calculations follow the arithmetic of existing canonical option-chain modules where applicable. They deliberately do **not** import the legacy market-universe constraints, policy weights, directional score, candidate selection or execution paths. Ratios, price concentration, levels and OI change share the `OPTION_OI_POSITIONING` dependency group. `independent_vote` is always `False` and no aggregate bias or trade action is emitted.

## Provenance and failure behavior

The immutable output contains source capture and validation SHA-256 identifiers; identical normalized captures and the same age budget yield deterministic output. Unavailable features carry blockers and `value=None`, never fabricated zeroes. If only some verified measurements exist, the output is `PARTIAL`. Neither a passing offline fixture nor a caller's `verified=True` flag independently establishes FYERS field units, OI-change semantics, individual quote timestamps, available strike coverage or market performance.

All components have disabled execution, risk, position, certification and live-eligibility authority; the package neither imports the FYERS SDK nor touches the PAPER runtime. X5-B3 will project feature evidence and control correlations; X5-B4 will handle adversarial replay/provenance; X5-B5 is the scoped final audit and commit.
