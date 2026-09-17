# P6H-4C2 Supplemental eligibility enforcement

## Purpose

Enforce supplied candidate eligibility evidence without deriving it.

## Architectural boundary

No raw ranking, date calculation, spot/strike calculation, provider fetch, order, or execution.

## Candidate-ID evidence lookup

Evidence is retrieved only by canonical candidate ID.

## Missing evidence

Candidates without evidence are ineligible but input construction may remain partial.

## Candidate validation order

Evidence checks follow moneyness category and precede OI/volume/liquidity.

## Moneyness category

Candidate category remains P5 typed evidence.

## Moneyness steps

Caller-supplied evidence steps are compared to resolved maximum.

## Expiry category

Caller-supplied WEEKLY/MONTHLY evidence uses resolved permissions.

## Same-day expiry

Caller-supplied DTE zero uses resolved same-day permission.

## Days-to-expiry bounds

Caller-supplied DTE uses resolved bounds only.

## Ranked fallback

Later evidenced candidates retain ranked fallback behavior.

## NO_CONTRACT outcome

Evidence exhaustion remains NO_CONTRACT.

## Diagnostics and provenance

Stable rejection codes are deterministic.

## Determinism

No timestamps or IDs are generated.

## PAPER-only guarantees

Live execution is disabled.

## Prohibited derivations

No strike/spot steps, expiry inference, DTE calculation, or current time.

## Deferred P6H-4C3 behavior

Lot-count reporting is deferred.

## P6H-4C3 handoff

No P6H-4C3 work is included.
