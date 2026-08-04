# P6I-3 Capital and quantity planning input

## Purpose
Immutable PAPER-only typed upstream boundary for later capital planning.
## Typed references
Requires exact canonical input, supplemental policy, entry, stop, targets and selection result contracts.
## Identity and policy coherence
Canonical identity/direction must match all result contracts; the supplied policy ID matches supplemental policy.
## Capital and affordability authority
Capital delegates only to canonical input. P6H affordability, contract and lot evidence are reused only through read-only properties.
## Risk-model coherence
PREMIUM_AT_RISK forbids caller risk; caller-supplied model requires finite positive per-lot evidence.
## Trading-cost attachment
Required typed cost policy and mode-dependent optional caller evidence are attached only. No cost is applied to planning in this boundary.
## Status and diagnostics
Upstream statuses remain constructible; planner diagnosis is deferred. Caller diagnostics are immutable and not merged.
## Serialization and immutability
Nested public serializers, frozen metadata, deterministic JSON; semantic exclusions are planning input ID, evaluated time and source timestamps.
## PAPER-only guarantees
Live execution is disabled.
## Deferred P6I-4
No result, sizing, risk budget, quantity, allocation, order or execution is implemented.
