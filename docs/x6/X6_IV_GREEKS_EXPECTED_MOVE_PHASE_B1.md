# X6-B1 — Offline Black–Scholes / Black-76 Reference Pricing

## Scope

The module `services/x6/reference_pricing_v1.py` is a pure mathematical reference
pricer. It does not fetch prices, calculate implied volatility, calculate Greeks,
select a trade, size positions, submit orders, modify PAPER journals, certify
trades, or create new Brain/X9 evidence votes. Its output is a *theoretical
reference* per one underlying native price unit, not an executable quote or a
lot-level amount. No source files from X1–X5 or the production PAPER worktree
are changed.

## Model identity

- NIFTY, SENSEX: **Black–Scholes spot** with the verified spot/index price,
  decimal continuously compounded risk-free rate `r` and explicit verified
  decimal continuously compounded dividend/forward yield `q`.
- CRUDEOILM, GOLDM, NATGASMINI: **Black-76 futures** using the precise
  underlying futures price and verified underlying futures contract identity.
  Do not apply an extra yield to futures prices. The X6 Phase-A contract checks
  that the underlying futures expire no earlier than the option.
- Time to expiry: positive ACT/365 calendar seconds from separately verified
  timestamps. **Never assume market close time**, and never infer volatility,
  rates, yield, contract identity or reference-price units.
- Annualized sigma is decimal (e.g. `0.20` means 20%). Explicit sigma `0` is
  supported as the deterministic discounted-intrinsic limit, but is not
  automatically inferred from prices. B1 restricts supplied sigma to [0, 5].

## Reference equations

Black–Scholes call = `S exp(-qT) N(d1) - K exp(-rT) N(d2)`;
put = `K exp(-rT) N(-d2) - S exp(-qT) N(-d1)` with
`d1=[ln(S/K)+(r-q+sigma²/2)T]/[sigma sqrt(T)]`, `d2=d1-sigma sqrt(T)`.

Black-76 call = `exp(-rT)[F N(d1) - K N(d2)]`;
put = `exp(-rT)[K N(-d2) - F N(-d1)]`, with
`d1=[ln(F/K)+(sigma²/2)T]/[sigma sqrt(T)]`.

Static no-arbitrage model bounds and parity are tested for both models.
These mathematical properties are not a live arbitrage or profitability claim.

## Evidence and failure behavior

`price_x6_capture_v1` first invokes `validate_x6_input_v1`, binding every
option to the original frozen X5 source capture, market, option identity,
source record, strike, timestamp and supplied premium (if present). A different
X5 capture hash or a mismatched observed premium is rejected. A theoretical
price does not require an observed market premium: if market premiums are
missing, it is marked by `NO_VERIFIED_OBSERVED_PREMIUM_FOR_COMPARISON`.

Missing/unverified model reference, rate, option expiry instant, index yield,
MCX futures identity or volatility produces `UNAVAILABLE` and a `None` price.
A retrospective capture can produce only `RETROSPECTIVE` reference values;
no result is marked point-in-time solely because a later file contains a quote.
All outputs carry X5 capture, X6 capture and Phase-A validation SHA-256 links.

The `volatility_verified` and provenance fields are supplied by the caller.
They are not independent proof of correctness of FYERS units or upstream data.
B2 will implement implied-volatility inversion and Greeks separately.

## Verification

Run `python -m ruff format --check services/x6 tests/test_x6_*.py`,
`python -m ruff check services/x6 tests/test_x6_*.py`, and
`python -m pytest -q tests/test_x6_*.py` from the Brain worktree. For broader
coverage, select `test_(brain|x1|x2|x3|x4|x5|x6)_*.py` explicitly.

B1 is uncommitted until the final X6-B5 scoped audit/freeze.
