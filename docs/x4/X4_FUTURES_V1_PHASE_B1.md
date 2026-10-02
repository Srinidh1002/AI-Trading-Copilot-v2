# X4 Phase B1 — FYERS-normalized futures observation adapter

Status: offline candidate, not frozen, not network/production wired.

This adapter accepts the normalized mapping tuple returned by the existing `FyersHistoricalDataProviderV2.get_candles` interface. The caller must obtain and verify the capture and canonical futures identity independently. Neither X4 nor its adapter may request provider data, read credentials, submit orders, change PAPER state, or update certification.

## Required evidence before accepting a record

- `ResolvedInstrumentV2`-compatible object representing a data-only, FYERS `FUTURE`, including canonical identity, exact provider symbol, explicit expiry, source and metadata status. Resolution time may not be after historical `as_of`.
- The canonical session and capture have independent verification; `capture_id` and `session_id` are caller-supplied provenance, not cryptographic proof by themselves.
- Timeframe is one of `1m`, `3m`, `5m`, `10m`, `15m`, `30m`, `1h`. Candle Unix-second timestamp **must have independently verified BAR_START semantics**. Only `bar_start + timeframe` at or before `as_of` can become an accepted completed candle. Session membership must have been verified by the caller; this module does not infer exchange hours.
- Record provider and provider symbol must match resolved identity. Price unit must be explicitly verified: `INDEX_POINTS` (NIFTY/SENSEX), `INR_PER_BARREL` (CRUDEOILM), `INR_PER_10G` (GOLDM), `INR_PER_MMBTU` (NATGASMINI). These are canonical X4 quote labels; the caller must verify actual provider-to-contract comparability before setting `price_unit_verified=True`.
- Volume and OI verification are **independent** flags. A numeric seventh candle field does **not** prove OI unit, scope or timestamp. Missing or unverified OI is never converted into a zero or a directional positioning state. `volume_unit_verified` also requires independent evidence that the FYERS volume field represents a comparable futures volume.
- Records are rejected if mixed, overlapping, future-dated, unclosed, invalid OHLC, or containing negative volume or nonpositive OI.
- Provisional contracts may be adapted for diagnostics but the X4 Phase A engine will return UNAVAILABLE; they cannot be used for signal generation.

## Deliberately deferred

- Live FYERS connectivity and X1 journal verification, which require provider-credential and session authority outside this module.
- Verifying FYERS-specific OI payloads and metadata using actual captured provider fixtures; **leave OI verification false until that happens**.
- Session-aware feed composition, multiple timeframes, feature registration, historical replay integration and stronger adversarial tests in later Phase B steps.
- No changes to frozen B1–B4, X1–X3 or the existing R2.2 PAPER worktree.

## Local checks

`python -m ruff format services/x4/fyers_adapter_v1.py tests/test_x4_fyers_adapter_v1.py`

`python -m ruff check services/x4/fyers_adapter_v1.py tests/test_x4_fyers_adapter_v1.py`

`python -m pytest -q tests/test_x4_fyers_adapter_v1.py`
