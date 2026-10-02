# X4 Phase B2 — Multi-timeframe futures research

Status: offline candidate; **not frozen, registered, or production wired**.

This phase composes previously verified `X4AdaptedCandlesV1` captures through the pure `analyze_futures_v1` engine. It does **not** authenticate to FYERS, request candles, read live quotes, write journals, generate orders or change R2.2 PAPER/certification state. It adds no new execution authority.

## Contract and replay rules

- Accept at least two distinct supported requested timeframes and explicit positive, finite `max_age_seconds_by_timeframe` for **every** requested timeframe. A missing timeframe remains explicitly missing; it is never synthesized or silently excluded from directional alignment.
- Each capture must have exactly the same immutable `X4ContractV1` (including provider symbol, market, expiry, price unit and metadata source), exactly the same historical `as_of` instant, and the same verified session ID. Capture IDs are unique per timeframe. Identical instants with different timezone offsets are accepted by Python datetime equality.
- The existing B1 adapter must already have verified the original provider/capture identity, exchange session, bar-start timestamp semantics, closed bars and market-specific quote units. This composer checks its output and delegates sequence/expiry/staleness checks to the existing X4 engine.
- One stale or otherwise unavailable timeframe cannot generate a consistent up/down alignment. A missing or unverified OI field produces `UNKNOWN` positioning for its timeframe; there is no conversion to zero, interpolation or implicit score.
- `CONSISTENT_UP` means that every **required** timeframe has valid positioning in the descriptive states `LONG_BUILDUP` or `SHORT_COVERING`; `CONSISTENT_DOWN` analogously covers `SHORT_BUILDUP` and `LONG_UNWINDING`. `FLAT`, `MIXED`, and `INSUFFICIENT_DATA` are distinct. These are diagnostics, **not** independent votes, execution signals, calibrated confidence or forecasts. Overlapping candles across timeframes are correlated evidence.
- Per-timeframe `oi_change_verified`, `volume_change_verified` and `candle_vwap_estimate_available` are taken from the actual X4 feature availability. `FUTURES_CANDLE_VWAP_ESTIMATE` is **not** traded/tick VWAP; unverified or missing volume cannot be promoted to a volume signal. OI acceleration and volume change remain the existing Phase A features; Phase B2 makes them visible per timeframe, without inventing additional thresholds.
- Missing basis means partial analytical coverage. Missing basis alone does not change the descriptive positioning alignment, but `status` remains `PARTIAL` and blockers retain the missing feature. Consumers must not interpret partial research as approved trading readiness.
- Identical captures and policy arguments produce a deterministic serialization and SHA256; no wall-clock calls, network, file writes or background workers occur in the composer.

## Explicitly deferred

Provider-specific volume/OI field semantics require separately captured evidence before setting B1 verification flags. Live/streaming composition, authoritative replay journals, actual multi-timeframe captures, X4 feature manifest and broader Brain V2 registration are not part of B2. Feature registration belongs to X9; certification belongs to a distinct later policy epoch. The full legacy test suite is not claimed green by these focused tests.

## Offline checks

`python -m ruff format services/x4 tests/test_x4_*.py`

`python -m ruff check services/x4 tests/test_x4_*.py`

`python -m pytest -q tests/test_x4_*.py`
