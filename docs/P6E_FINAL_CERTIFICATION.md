# P6E Final certification

## Scope

This certification covers the deterministic PAPER-only boundary:
`EntryZoneEvaluationInputV1` + `TradePlanningPolicyV1` +
`evaluate_entry_zone` -> `EntryZoneEvaluationResultV1`. P6F has not started.

## Certified contracts

The input and result contracts have complete canonical identity, direction/right,
price, limits, diagnostics, provenance, metadata, serialization, schema, and
PAPER-only fields. Result statuses are READY, BLOCKED, and NO_ENTRY.

## Certified evaluator

The evaluator accepts exact typed inputs, copies caller IDs and timestamps, has
deterministic early blocks, and emits only READY or BLOCKED in current P6E.

## Reference methods

OPTION_MID, OPTION_ASK, LAST_TRADED_PRICE, SIGNAL_REFERENCE, and HYBRID were
replayed. HYBRID priority is MID, ASK, LTP, SIGNAL; its fallback warning occurs
once and in stable order.

## Entry-zone formulas

For reference `r`: `lower = r * (1 - below)`, `upper = r * (1 + above)`, and
`maximum_chase = r * (1 + chase)`. The scalar tolerance is `max(below, above)`.
No rounding or implicit quote computation occurs.

## Premium-limit behavior

The stricter available input/policy cap applies. Equality is accepted; a
reference, upper-zone, or chase breach blocks without silently capping geometry.

## Spread-limit behavior

Spread is `(ask - bid) / option_mid`, falling back to the selected reference
only when mid is absent. The stricter available limit applies; equality is
accepted, excess blocks, and an absent bid/ask pair leaves spread absent.

## Status behavior

READY has complete geometry and no blockers. Early BLOCKED results have absent
geometry; post-geometry blocks retain complete geometry. Partial geometry is
never emitted. NO_ENTRY is supported by the result contract but not emitted by
the evaluator.

## Diagnostic ordering

Ordering is input blockers, planning blocker, policy mismatch, unavailable
reference, premium breach, then spread breach. Diagnostics remain deduplicated
in first-occurrence order.

## Deterministic replay

The 12-case fixed replay matrix covers NIFTY, BANKNIFTY, FINNIFTY, and SENSEX;
BULLISH/CALL and BEARISH/PUT; every reference method; READY; planning, input,
policy, missing-reference, premium, spread, and combined premium/spread blocks.
Repeated evaluations compare equal with byte-identical JSON, unchanged supplied
IDs/timestamps, stable diagnostics, reference source, geometry, evidence, and
PAPER fields. It uses no random values, UUIDs, clock reads, providers, or network.

## Serialization and immutability

Input and result `to_dict()` data is detached, nested metadata cannot mutate the
typed object, source timestamps remain unchanged, `to_json()` is stable, and
semantic exclusions are exactly IDs, evaluated time, and source timestamps.
Result geometry properties are repeatable.

## Isolation boundary

Fresh subprocess imports for both contracts, `TradePlanningPolicyV1`, and the
evaluator succeeded. The evaluator dependency source contains no provider,
broker, runtime execution adapter, order manager, portfolio, database,
dashboard/Streamlit, AI/news/network client, pandas/numpy/scipy/yfinance/
SmartApi, random/UUID, wall-clock, or order-placement dependency.

## Regression boundaries

P6B-P6D and the recovered seven-file option-contract boundary both passed.

## Exact pytest results

- Combined focused P6E: `154 passed in 1.01s`.
- Replay-only: `15 passed in 0.27s`.
- Combined P6E plus replay: `169 passed in 1.15s`.
- P6B-P6D: `36 passed in 1.07s`.
- Seven-file option regression: `198 passed in 0.87s`.

No failures, skips, or warnings were reported by any of these pytest commands.

## PAPER-only guarantees

There is no quote fetching, option selection, stop calculation, target
calculation, sizing, order creation, execution, portfolio allocation, broker,
provider, or execution integration. Live execution remains disabled.

## Deferred behavior

No fake evaluator NO_ENTRY path was added. P6F has not started.

## Final decision

P6E CERTIFIED COMPLETE
