# P7D Deterministic entry evaluator
## Purpose
Pure conversion of a READY P6J plan into WAITING, OPEN, BLOCKED, or terminal pre-entry outcomes.
## Input authority
Typed P6J result, lifecycle policy/state, and caller observation.
## Evaluation order
Ordering, freshness, quality, session, timeout, then option-premium activation.
## Entry-price basis
Selected-option premium only.
## Entry activation modes
ZONE_TOUCH, PREFERRED_ENTRY_TOUCH, and ZONE_CLOSE.
## Effective entry zone
P6 bounds plus/minus reference price times lifecycle tolerance.
## Tolerance behavior
P6 values remain unmodified.
## Gap behavior
Implemented for ZONE_TOUCH/PREFERRED_ENTRY_TOUCH: an upward option-open gap wholly above the effective zone activates only when `allow_gap_entry=True`, at option open; a downward gap waits unless later range evidence touches the zone. ZONE_CLOSE is unaffected.
## Entry fill-price rule
ZONE_TOUCH uses the higher touched BUY price; preferred uses preferred price; close uses option close.
## Observation freshness
Caller timestamp comparison only.
## Observation ordering
Duplicate is a WAITING no-op; out-of-order blocks.
## Session rules
OPEN evaluates; non-open waits or closes by policy; UNKNOWN blocks.
## Expiry rules
Implemented from P6H selected contract `expiry_date`: supplied evaluation calendar date at or after expiry closes when enabled, otherwise waits; no exchange close time is invented.
## Entry timeout
Strictly greater than policy duration invalidates.
## Pre-entry invalidation
Only machine-readable evidence; natural-language rules are deferred.
## WAITING_FOR_ENTRY behavior
No fill or position.
## OPEN behavior
One ENTRY/BUY fill and one zero-P&L position.
## BLOCKED behavior
No fill or position.
## Terminal pre-entry behavior
No fill or position.
## Diagnostics and metadata
Stable codes and P6 zone provenance.
## Determinism
No clock, network, engine, persistence, or mutation.
## PAPER-only guarantees
Live disabled.
## Prohibited behavior
No market fetch, broker/provider integration, orders, execution, persistence, stop/target processing, or P&L.
## P7-WP3 handoff
Open-position evaluation, exits, and P&L remain deferred.
