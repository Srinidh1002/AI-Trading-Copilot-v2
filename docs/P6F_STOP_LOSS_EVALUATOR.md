# P6F Stop-loss evaluator

## Purpose

P6F deterministically evaluates a supplied option-premium stop-loss in INR per
unit. Fractions use 0–1.

## Architectural boundary

`CanonicalTradePlanInputV1`, `TradePlanningPolicyV1`, an entry evaluation, and
`StopLossEvaluationInputV1` produce `StopLossEvaluationResultV1`. No runtime
data is fetched.

## Input contract

The input holds caller IDs/timestamps, canonical identity and direction/right,
complete entry geometry, optional ATR/structure/premium/swing evidence,
planning diagnostics, immutable provenance/metadata, and PAPER fields.

## Result contract

The result holds stop method/source/status, wholly-present-or-absent stop
geometry and bounds, diagnostics, invalidation rules, provenance, and PAPER
fields. READY, BLOCKED, and NO_STOP are supported.

## Stop methods

ATR, STRUCTURE, PREMIUM_FRACTION, and HYBRID are the exact policy vocabulary.

## ATR method

The supplied ATR times the supplied policy multiplier is subtracted from entry.
Missing evidence, a non-positive stop, and out-of-bound distance block.

## Structure method

Structure-stop evidence takes priority over recent swing low; the supplied raw
premium is reduced by the policy structure buffer. A PUT remains a long option
premium position, so its stop is also below entry. Swing high is retained as
unsupported future evidence.

## Premium-fraction method

Entry reference is canonical; optional premium reference must match within a
fixed 1e-9 relative tolerance. Stop equals entry times `(1 - fraction)`.

## Hybrid method

All available valid candidates are assessed. The highest valid stop price is
selected as the tightest risk; ties use structure, ATR, premium-fraction order.
No averaging occurs. A non-structure selection receives one stable fallback
warning.

## Stop-distance bounds

Distance is entry minus stop; fraction is distance divided by entry. Policy
minimum and maximum are inclusive; values are never silently clamped.

## Planning eligibility

Input blockers, planning eligibility, policy/coherence, and entry-evidence
validity are evaluated before stop calculation.

## Diagnostics

Diagnostics are tuple-only, deduplicated, and stable: input blockers, planning,
policy mismatch, evidence, invalid price, then distance constraints.

## Invalidation rules

READY results contain `STOP_OPTION_PREMIUM_BREACH`; no executable callbacks or
dynamic prose is used.

## Determinism and provenance

IDs/timestamps are caller supplied and propagated. Metadata records entry ID,
policy ID, selected source, hybrid candidates, and comparison tolerance.

## Serialization and immutability

Frozen slots, recursively immutable mappings, detached `to_dict`, sorted
byte-stable JSON, and semantic serialization support replay.

## PAPER-only guarantees

No ATR/structure data is fetched, no trailing-stop lifecycle exists, and no
target calculation, sizing, order, or execution occurs. Live execution stays disabled.

## Deferred behavior

Underlying support/resistance and recent swing high are not inferred as option
premium stops. P6G has not started.

## P6G handoff

P6G may consume only the typed stop result to calculate targets; P6F creates no
target or final trade plan.
