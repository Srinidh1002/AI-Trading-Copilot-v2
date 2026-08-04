# P6E Entry-zone evaluator

## P6E-1 through P6E-3 scope

This document records the `EntryZoneEvaluationInputV1` and
`EntryZoneEvaluationResultV1` contracts and evaluator behavior. It does not
provide final combined P6E certification.

## Purpose

`EntryZoneEvaluationInputV1` is the immutable, PAPER-only boundary for
supplied-price entry-zone evaluation. It accepts no runtime, broker, provider,
or execution objects.

## Input fields

The contract contains the following fields:

- `evaluation_id`, `evaluation_result_id`, `evaluated_at`
- `underlying_symbol`, `exchange`, `trade_plan_input_id`, `policy_id`
- `direction`, `option_right`, `entry_reference_method`
- `last_traded_price`, `bid_price`, `ask_price`, `signal_reference_price`, and
  `option_mid_price`
- `option_quote_timestamp`, `maximum_entry_premium`, and
  `maximum_spread_fraction`
- `planning_allowed`, `blockers`, and `warnings`
- `source_timestamps` and `metadata`
- `execution_mode`, `live_execution_eligible`, and `schema_version`

The only accepted execution mode is `PAPER`; live eligibility is always
`False`; and schema version is exactly `1.0`.

## Validation

All IDs are nonblank strings. `evaluated_at`, `option_quote_timestamp`, and
every source timestamp must be timezone-aware datetimes. Market identity is
normalized through the repository's canonical market registry.

Directions are `BULLISH` or `BEARISH`; option rights are `CALL` or `PUT`; and
the required pairs are BULLISH/CALL and BEARISH/PUT. Reference methods are
`OPTION_MID`, `OPTION_ASK`, `LAST_TRADED_PRICE`, `SIGNAL_REFERENCE`, and
`HYBRID`.

Present price values and the premium cap must be finite, non-boolean numbers
greater than zero. Quotes may be partial. When bid and ask are both present,
bid cannot exceed ask; when a mid is also present, it must be within that
inclusive range. The spread cap may be absent or a finite fraction from zero
through one. `planning_allowed` must be an exact boolean.

`blockers` and `warnings` are tuple-only diagnostics. Entries are trimmed,
must be nonblank strings, and are deduplicated while retaining their first
occurrence order.

## Provenance and metadata

`source_timestamps` accepts a mapping with nonblank string keys and aware
datetime values. It is copied into an immutable mapping and is serialized with
deterministic key ordering.

`metadata` accepts only JSON-safe, recursively nested mappings, lists or
tuples, and JSON primitive values. Unsupported objects and non-finite numeric
values are rejected. Metadata is copied and deeply frozen, so mutation of the
constructor input cannot affect the contract. It must not contain runtime
provider or credential objects.

## Immutability and serialization

The input is a frozen, slotted dataclass. Diagnostics are immutable tuples;
source timestamps use an immutable mapping; and nested metadata mappings and
sequences are deeply frozen.

`to_dict()` produces a fully detached plain-Python payload with ISO datetimes,
lists for tuples, and deterministically ordered mappings. `to_json()` uses a
stable compact JSON encoding with `allow_nan=False`, so repeated calls are
byte-identical. `semantic_dict()` excludes only `evaluation_id`,
`evaluation_result_id`, `evaluated_at`, and `source_timestamps`.

## Result contract

`EntryZoneEvaluationResultV1` contains result and evaluation IDs, the aware
evaluation time, canonical market identity, direction/right, entry method,
selected reference source, status, price geometry, premium and spread evidence,
limit-entry requirement, diagnostics, source timestamps, metadata, and the
PAPER/schema fields.

The status vocabulary is `READY`, `BLOCKED`, and `NO_ENTRY`. `READY` requires
complete valid geometry and no blockers. `BLOCKED` requires at least one
blocker and may retain valid complete geometry or have none. `NO_ENTRY`
requires at least one decision reason and may likewise retain valid geometry or
have none.

## Result price groups and constraints

The result price group consists of `selected_reference_source`,
`entry_reference_price`, `entry_zone_lower`, `entry_zone_upper`,
`entry_tolerance_fraction`, and `maximum_chase_price`. It must be either wholly
absent or wholly complete; partial groups are invalid for every status.
Complete groups require a supported selected source, positive prices,
`lower < upper`, the reference inside the zone, and chase at or above the
upper zone boundary.

For `READY`, a present premium cap must cover reference, upper zone, and chase
price. If both effective spread fraction and limit are present, the fraction
cannot exceed the limit. Missing spread evidence is valid when it was not
available. `BLOCKED` and `NO_ENTRY` groups still require internal geometry
validity but do not have to satisfy READY premium/spread acceptance.

Read-only geometry properties expose `zone_width`, lower and upper distance
fractions relative to the reference, and `spread_within_limit`. They return
`None` when their required evidence is absent.

## Result provenance, metadata, and serialization

Result source timestamps and metadata follow the same immutable rules as the
input contract: timestamps use nonblank keys and aware values; metadata is
deeply copied/frozen JSON-safe data with string mapping keys only; and
unsupported objects or non-finite numeric values are rejected. Constructor
mapping mutation cannot affect the result.

Result serialization returns detached plain JSON data with deterministic field
and mapping order. `to_json()` is compact, sorted, uses `allow_nan=False`, and
is byte-stable. Its semantic serialization excludes only
`evaluation_result_id`, `evaluation_id`, `evaluated_at`, and
`source_timestamps`. Diagnostic tuples, timestamps, and metadata remain
immutable internally. The result is strictly PAPER-only and never enables live
eligibility.

## Reference-price methods

`OPTION_MID`, `OPTION_ASK`, `LAST_TRADED_PRICE`, `SIGNAL_REFERENCE`, and the
deterministic `HYBRID` priority are the supported reference methods.

## Evaluator validation and ordering

`evaluate_entry_zone()` accepts only exact
`EntryZoneEvaluationInputV1` and `TradePlanningPolicyV1` instances. It is a
pure deterministic function: it does not fetch quotes, select an option,
create IDs, read the clock, or access network/runtime services.

Evaluation order is fixed:

1. Exact type validation.
2. Existing input blockers and `planning_allowed`.
3. Input/policy coherence: policy ID, reference method, PAPER mode, and live
   eligibility.
4. Reference selection.
5. Entry-zone geometry.
6. Effective premium limit.
7. Effective spread calculation and limit.
8. `READY` or `BLOCKED` result creation.

Early planning or coherence blocks preserve input blockers first, then append
`ENTRY_PLANNING_NOT_ALLOWED` and `ENTRY_POLICY_MISMATCH` where applicable.
They return an absent price group and no premium/spread evidence. No-entry is
not emitted by the current evaluator; valid policy failures are `BLOCKED`.

## Reference selection and geometry

Non-HYBRID methods require their corresponding supplied price and select that
same source. HYBRID deterministically selects, in order: option mid, ask, last
traded price, then signal reference. A non-mid HYBRID selection appends exactly
one `ENTRY_HYBRID_FALLBACK_USED` warning after input warnings. No averaging,
computed midpoint, or quote fetch is used.

For a selected reference `r`, the geometry is:

```text
lower = r * (1 - entry_tolerance_below_fraction)
upper = r * (1 + entry_tolerance_above_fraction)
maximum_chase = r * (1 + maximum_chase_fraction)
```

The scalar result tolerance is the larger of the policy's lower and upper
tolerances; the full geometry retains their asymmetry. There is no tick-size or
arbitrary decimal rounding.

## Premium, spread, and diagnostics

The effective premium cap is the stricter available input/policy cap. A
complete price group is retained when reference, upper zone, or chase exceeds
that cap, and `ENTRY_PREMIUM_LIMIT_EXCEEDED` is appended.

When both bid and ask are supplied, spread fraction is `(ask - bid)` divided by
option mid when supplied, otherwise by selected reference. The effective spread
limit is the stricter available input/policy limit; equality is accepted. A
breach appends `ENTRY_SPREAD_LIMIT_EXCEEDED`. Without both bid and ask, spread
fraction is absent and no spread blocker is invented.

After geometry, premium is evaluated before spread, so multiple failures retain
both blockers in that order. All blocker and warning lists are deduplicated in
first-occurrence order. Stable evaluator codes are
`ENTRY_REFERENCE_UNAVAILABLE`, `ENTRY_PREMIUM_LIMIT_EXCEEDED`,
`ENTRY_SPREAD_LIMIT_EXCEEDED`, and `ENTRY_HYBRID_FALLBACK_USED` in addition to
the early-block codes above.

## Evaluator provenance and boundaries

Results copy IDs, evaluated time, identity, direction/right, and source
timestamps from the input. Result metadata preserves input metadata under
`input_metadata` and deterministically records selected source, effective
limits, quote timestamp, trade-plan input ID, and policy ID. Repeated equal
input/policy evaluations compare equal and produce byte-identical JSON.

The evaluator remains PAPER-only. It does not perform option selection,
stop/target/sizing work, or order/execution activity.

## Entry-zone formula

The evaluator applies the policy tolerance below and above the selected
reference price; chase uses the policy chase fraction.

## PAPER-only guarantees

No quotes are fetched, contract selected, stop/target/quantity calculated, or
order created by this input contract.
