# P1-1 MarketSnapshot v1 Remediation

## Audit inventory

Producers: `services/market_snapshot.py:_build_market_snapshot` emits a lowercase-history dashboard dict; `services/core/market_snapshot.py:get_market_snapshot` builds `services/core/snapshot_schema.py:Snapshot` then serializes it to a dict; `services/market/market_snapshot.py:MarketSnapshot.snapshot` emits index/options data. Consumers include `dashboard/dashboard_v2.py`, `services/trade/trade_engine.py`, legacy decision/risk engines, `services/live_analysis_pipeline.py`, and `LiveOptionDecisionPipeline` through analysis output. Fields, casing, timestamps, and missing-source meanings differ.

| Boundary | Observed fields and format | Missing-data semantics |
| --- | --- | --- |
| Dashboard producer/consumer | `symbol`, `history` (lowercase OHLCV DataFrame), `ltp`, OHLCV summary, string `timestamp`, `refresh_time`, `market_status`, indicators and option analysis | Empty 5m history aborts production; option analysis may be `{}`. |
| Core producer | `Snapshot` dataclass / dict with `history`, float prices, integer volume, string `candle_time`, status, refresh time, and analysis/decision/risk dictionaries | Optional analysis dictionaries default to `{}`; no typed source health. |
| Market component | `index`, `options`, `option_analysis` dictionary | Provider-dependent keys; no shared timestamp/health contract. |
| Live analysis | Mapping of 5m/15m/1h/1d DataFrames; technical paths require `Open`/`High`/`Low`/`Close`/`Volume`, while structure paths use lowercase | Absent or malformed frame is handled independently by the legacy pipeline. |

Identity, capture time, market timestamp and positive LTP are v1 universal requirements. Timeframes and the option/VIX/FII-DII payloads are optional analysis inputs. Provider-specific raw payloads stay under their source fields; indicators, smart money, decision, risk, and trade fields remain legacy/derived data and are deliberately excluded from v1.

## Canonical contract

New location: `services/contracts/market_snapshot_v1.py`. It supplies typed `MarketSnapshotV1`, `OHLCVSeries`, and `OHLCVBar`; lowercase OHLCV; independent option/VIX/FII-DII status; data-health fields; deterministic serialization; and explicit legacy adapters. It is not wired into current runtime paths, preventing decision or execution changes in this contract-introduction task.

## Compatibility limitations

Legacy dashboard/core snapshots do not consistently carry exchange, timezone-aware timestamps, previous close, VIX, FII/DII, or option completeness. Adapters preserve critical available fields, issue warnings for unmapped data, and mark invalid values explicitly; they do not invent missing evidence. `to_legacy_dashboard_dict` is intentionally limited to the observed dashboard fields.

Focused and full test results are recorded after execution in the task response.
