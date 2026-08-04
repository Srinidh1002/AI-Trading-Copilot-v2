# MarketSnapshot v1

`services.contracts.market_snapshot_v1.MarketSnapshotV1` is the side-effect-free canonical market-input contract. It performs no provider calls, decisioning, paper trading, broker execution, or persistence.

## Required fields

Identity: `schema_version` (`market_snapshot.v1`), `snapshot_id`, non-empty `symbol`, non-empty `exchange`, and instrument type (`INDEX`, `EQUITY`, `FUTURE`, or `OPTION`). Time: timezone-aware `captured_at` and `market_timestamp`, with explicit `timezone`. Price: positive finite `ltp`.

Price summary fields (`previous_close`, `open`, `high`, `low`, `close`) are optional but, when supplied, must be positive finite values. `volume` is optional but must be finite and non-negative. Options require ISO `YYYY-MM-DD` expiry, positive strike, and `CE`/`PE` type.

## OHLCV

The single canonical schema is lowercase: `timestamp`, `open`, `high`, `low`, `close`, `volume`. Each bar has a timezone-aware timestamp; prices are positive finite and volume is non-negative. Partial timeframe mappings are allowed for `1m`, `3m`, `5m`, `15m`, `1h`, and `1d`. `to_uppercase_ohlcv` is an explicit legacy adapter; canonical storage never duplicates casing.

## Health and freshness

Source states are `UNAVAILABLE`, `EMPTY`, `STALE`, `INVALID`, and `VALID`. Option, VIX, and institutional sources retain independent status and error lists. `option_chain_available`, `option_chain_complete`, `india_vix_available`, and `fii_dii_available` are explicit derived/serialized fields; `STALE` remains available but is never fresh evidence. `freshness_seconds` is calculated from an injected/reference capture time; staleness is explicit (`is_stale`) and produces `STALE` overall status. Identity/critical-price errors produce `validation_passed=False`, `overall_status=INVALID`, and `critical_errors`.

An unknown source status is normalized to `INVALID` with a warning. `UNAVAILABLE` is added to `missing_sources`; `STALE` is added to `stale_sources`. Optional unavailable, empty, stale, or invalid sources are never translated into a favourable/neutral signal.

## Serialization and adapters

`to_dict()` and sorted `to_json()` are deterministic for an unchanged snapshot. `from_dict()` supports round-trip replay. `from_dashboard_snapshot`, `from_core_snapshot`, and `from_live_analysis_inputs` explicitly adapt current formats. `to_legacy_dashboard_dict` emits legacy lowercase-history fields. Unmapped legacy fields are recorded as warnings; incompatible OHLCV is not silently converted.

## Examples

Valid: an INDEX snapshot with NIFTY/NSE, aware timestamps and positive LTP. Partial: the same snapshot with only `5m` candles and VIX/options unavailable. Stale: `is_stale=True` and `stale_sources=["market"]`. Invalid: missing symbol, NaN LTP, negative volume, or malformed option expiry leaves the object constructible for audit but `validation_passed=False`; consumers must not treat it as valid evidence.
