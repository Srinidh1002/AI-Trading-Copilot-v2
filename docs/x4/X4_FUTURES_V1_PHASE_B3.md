# X4 Phase B3 — manifest and read-only research projection

## Scope

Offline research-only representation of the existing X4 A/B1/B2 calculations.
No FYERS requests, no registry installation, no trade scoring, no paper journal
writes, no order submission, and no mutation of B1–B4 or X1–X3. X9 owns any
future canonical MarketSnapshotV2 feature registry; X10 owns any future
evidence reduction and explicit treatment of correlated families.

## Frozen feature list

| Feature | Dependency group | Meaning |
|---|---|---|
| FUTURES_PRICE_CHANGE_PCT | PRICE_OI | Relative futures close change |
| FUTURES_OI_DELTA | PRICE_OI | Delta in the provider-reported OI unit, if verified |
| FUTURES_OI_CHANGE_PCT | PRICE_OI | Relative OI change, if verified |
| FUTURES_OI_ACCELERATION | PRICE_OI | Change in OI rate, if verified |
| FUTURES_VOLUME_CHANGE_PCT | VOLUME_DERIVED | Relative volume change, if verified |
| FUTURES_CANDLE_VWAP_ESTIMATE | VOLUME_DERIVED | Candle typical-price approximation only |
| FUTURES_VWAP_ESTIMATE_DISTANCE_PCT | VOLUME_DERIVED | Price distance from that approximation |
| FUTURES_BASIS | BASIS_REFERENCE | Futures-minus-verified, like-unit benchmark |

Price/OI measurements and derived metrics are correlated. Volume and candle
VWAP measurements are also correlated. All features are **non-voting**. The
metric UP/DOWN labels describe numerical changes, **not** BUY CE/PE decisions.
X4 positioning states and B2 alignment remain descriptive research evidence.

## Projection boundary

The B3 builder accepts only `X4MultiTimeframeResultV1`, validates frame and
capture evidence identity, validates every feature ID against the manifest,
validates fixed units, rejects duplicate feature IDs and repeated dependency
IDs, and emits a deterministic JSON/sha256 projection bound to the source
result hash and manifest hash. It does not fill in missing timeframes, replace
unverified OI or volume, fetch additional provider data, or convert missing
measurements into zero. The source result is retained unchanged.

`FUTURES_BASIS` is passed through only when the upstream A/B1/B2 result has
already evaluated a same-unit, verified reference. Its upstream feature
dependencies do not yet cryptographically bind the benchmark observation;
source-proof linkage and historical real-provider replay remain B4 gates.
The research view is therefore not proof of end-to-end provider provenance.

## Remaining X4 gates

- B4: Verify actual FYERS timestamp and OI/volume unit semantics, as-of
  provenance, session gaps, contract rollover, replay determinism, and
  report the limitations of any benchmark evidence.
- B5: Full focused/combined/adversarial regression, authority scan, scoped
  staging, and explicit freeze decision.

Do not modify production PAPER behavior or count any replay/research outcome
as a certified PAPER trade.
