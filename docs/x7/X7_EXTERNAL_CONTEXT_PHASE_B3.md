# X7-B3 — Scheduled-event adapter, offline Shadow only

## Ownership and scope

This module consumes supplied, exact normalized calendar records and separate
caller-supplied attestations, then records deterministic X7-A event facts,
raw/proof SHA-256 hashes, freshness, market applicability and a point-in-time
status. It does **not** download a calendar, scrape news, infer an event date,
verify that a third-party publisher is authentic, or change any trading rules.
The canonical market-session service retains exchange open/closed, holiday and
special-session authority. X7 cannot override it.

## Evidence boundary

Every calendar record must include a controlled event category, fixed event ID,
source-record ID, source ID, time-zone-aware observation/publication/availability
and scheduled instants, declared severity, a canonical five-market applicability
list and a stated schedule state. All source verification flags are supplied by
a separately audited caller. They are assertions, **not** proof of upstream
publisher identity or data authenticity.

The states `TENTATIVE`, `POSTPONED`, `CANCELLED` and `UNAVAILABLE` remain
visible in `X7AdaptedEventV1.schedule_state` but can never be `AVAILABLE` or
`confirmed` in the X7-A event contract. Unverified source, unknown severity,
unverified session-calendar reference or unbound expiry also remain explicitly
unavailable. Stale confirmed evidence is `STALE`, never fresh. Future publication,
future availability or future *observation* relative to the capture is rejected,
even if the scheduled event itself is in the future.

## Contract and rollover safeguards

`WEEKLY_EXPIRY`, `MONTHLY_EXPIRY` and `ROLLOVER` require exactly one market,
exact contract identity, bound expiry date and caller-attested contract binding.
Expiry scheduled instants must match the contract's India-local expiry date.
Rollover cannot follow its bound expiry, but remains descriptive; it cannot
trigger a close, exit or new contract selection. Session-category events
require separate calendar-reference attestation and remain descriptive even
when that attestation is present.

## Outputs and testing

- `X7EventSourceProofV1`: immutable verified-supplied source identity, state,
  timestamps and expiry/calendar binding, with all authorities disabled.
- `X7AdaptedEventV1`: exact X7-A `X7ScheduledEventV1`, raw/proof hashes, time
  relation, completeness/rejection reasons and deterministic hash.
- `X7EventBatchV1`: market/session/capture-scoped, date/ID ordered, duplicate-free,
  reproducibly hashed tuple of adapted facts.
- `adapt_x7_scheduled_event_v1` and `adapt_x7_scheduled_event_batch_v1`:
  pure, deterministic functions with no SDK, broker, calendar or network calls.

The adversarial tests exercise the five-market/category matrix, duplicate and
mismatched proof rejection, tentative/cancelled/postponed states, expiry and
rollover bindings, future-data protection, raw/proof tampering, immutable
zero-authority flags, and compatibility with `validate_x7_context_v1`.

X7-B4 will add immutable research views, correlation grouping and full replay
provenance. The production PAPER runtime, position state and certification
counters must remain untouched. X7 stays uncommitted until its final audit.
