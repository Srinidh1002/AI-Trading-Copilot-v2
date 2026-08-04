# P6B Canonical trade-plan input contract

## Purpose
`CanonicalTradePlanInputV1` is an immutable PAPER-only planning request.
## Architectural boundary
It accepts typed P5 evidence and has no broker, provider, execution, UI, AI, or network dependency.
## Input fields
It carries the selected candidate/regime/session, optional option-chain/external context, INR capital/risk limits, planning constraints, provenance, and diagnostics.
## Identity and timestamp rules
Canonical identity and aware supplied timestamp are required; no UUID or clock default exists.
## Selected opportunity and regime coherence
Candidate regime/session must equal supplied children.
## Option-chain availability
Explicit boolean availability must match exact typed child presence.
## Session and event context
Typed candidate external context and session reasons are preserved.
## Capital and risk units
Currency is INR; fractions are 0--1; no quantity calculation occurs.
## Execution constraints
Premium, spread/slippage, brokerage, lots, and expiry permissions are planning constraints only.
## Planning eligibility
Derived from PAPER candidate/session eligibility and absence of blockers.
## Serialization and immutability
Frozen slots, mapping proxies, deterministic `to_dict`, `to_json`, and `semantic_dict`.
## Validation failures
Identity/type/coherence, limits, availability, diagnostics, metadata, and PAPER violations fail loudly.
## PAPER-only guarantees
No strike or expiry is selected; no entry, stop, target, order, or live execution is created.
## P6C handoff
P6C owns planning policy and all calculation rules.
