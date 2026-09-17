# P6H-4C3 Lot affordability and result population

## Purpose

Apply resolved lot bounds to typed candidate premium affordability.

## Architectural boundary

No exchange lookup, hardcoded lot size, charges, brokerage, taxes, slippage, final sizing, order, or execution.

## Effective lot bounds

Uses resolver-provided minimum and maximum bounds only.

## Typed lot-size evidence

Lot size comes only from the typed candidate contract.

## One-lot premium cost

Cost is premium times lot size.

## Raw affordable-lot count

Uses deterministic floor division.

## Minimum-lot eligibility

Raw affordability must meet the effective minimum.

## Maximum-lot reporting cap

Reported count is capped at effective maximum; exceeding it does not reject.

## READY result population

READY carries typed cost and capped affordable count.

## NO_CONTRACT affordability outcome

Insufficient raw lots produce ordinary candidate rejection.

## Candidate validation order

Lot-size validation precedes affordability.

## Diagnostics and provenance

Stable deterministic result fields are preserved.

## Determinism

No runtime state is read.

## PAPER-only guarantees

Live execution remains disabled.

## Excluded charges and sizing

P6I owns charges and final quantity sizing.

## Deferred P6H-4C4 behavior

No P6H-4C4 behavior is included.

## P6H-4C4 handoff

Future work may consume the typed result.
