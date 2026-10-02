# X6 Phase B2: bounded implied volatility and analytical Greeks

**Scope:** new, independent, offline `services/x6/iv_greeks_v1.py`. Does not
change the frozen X5 or X6-A/B1 source. Consumes the immutable X6 capture and
its exact bound X5 capture through `validate_x6_input_v1`. No SDK or I/O.

## Computation

- Models are fixed by market: Black–Scholes with independently verified spot,
  annual continuous discount rate and dividend yield for NIFTY/SENSEX;
  Black-76 with a verified exact futures reference and continuous discount
  rate for CRUDEOILM/GOLDM/NATGASMINI. Both assume European-style payoff and
  lognormal price dynamics; model applicability and actual exercise/settlement
  rules are **not** certified by unit tests.
- For each independently verified LTP or MID premium, solve the B1 model
  price using 96-step monotone bisection, allowing `0 < annual sigma < 5`
  (decimal annualized, where `0.20` means 20% annual implied volatility).
  Reject prices below discounted intrinsic, beyond the supported volatility
  range, at non-identifiable boundary prices, with large solver residual, or
  with numerically negligible vega. Unverified premiums remain unavailable.
- Compute model sensitivities analytically using the same solved IV: Delta per
  **one reference-price unit** (spot for indices, the **futures price** for
  Black-76); Gamma per reference-price unit squared; Theta as **premium per
  calendar day**, using ACT/365; Vega as **premium per +1 percentage point of
  annual IV** (a 0.01 decimal-volatility change); Rho as **premium per +1
  percentage point of annual continuous discount rate** (a +0.01 change).
  Black-76 rho is calculated holding the supplied futures price constant,
  yielding `-T * theoretical_price * 0.01` for calls and puts; this is not
  an all-in hedge/financing sensitivity.
- Output `model_price` and signed `price_residual = model_price - premium` in
  native per-unit premium units, not lot-level P&L. No contract ranking.

## Provenance, time and fail-closed behavior

`analyze_iv_greeks_v1` binds three immutable hashes: X6 capture, X5 source
capture, and X6 input validation. Repeated calculations are deterministic.
Mixed market, expiry, source observation or premium are rejected by the frozen
X6 validator, not repaired by the solver. An X6 retrospective capture produces
`RETROSPECTIVE` rows, never point-in-time `AVAILABLE`. A partially valid chain
produces `PARTIAL` and keeps rejected rows entirely unavailable, without
imputation. An absent or unverified rate, dividend, expiry instant, reference
price, futures identity or premium cannot produce IV or Greeks.

Verification flags and fixture tests are **not independent proof** of actual
FYERS source accuracy or contemporaneous data availability. IV and Greeks are
**model-calculated**, not FYERS-reported/independently verified market Greeks.
Exercise, early assignment, volatility smiles, discrete dividends, bid/ask
quality, microstructure and model calibration quality are not established by
this module. Neither profitability nor trading eligibility follows.

## Authority

All exported contracts are frozen, data-only, independent-vote false and
execution/risk/position/certification/live-eligibility false. No broker calls,
order selection, strategy votes, sizing or PAPER-trade counting. X6 remains
uncommitted until final B5 freeze.

## Offline tests

`python -m pytest -q tests/test_x6_*.py` and `python -m ruff check
services/x6 tests/test_x6_*.py`. The B2 test module covers parameterized
five-market and call/put IV recovery, finite-difference checks of Delta,
Gamma, Theta, Vega and Rho, model-specific Black-76 rho, intrinsic and
volatility-range boundaries, incomplete and retrospective captures, broken
hashes, deterministic replay, immutable outputs, and banned authority calls.
