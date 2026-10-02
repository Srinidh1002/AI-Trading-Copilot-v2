# X7-A: Five-Market External-Context Research Contracts

## Scope

X7 provides a new **offline, zero-authority, five-market research boundary** for
structured global and macro observations, index-specific India cash-equity
institutional flow, and confirmed scheduled-event facts. These are normalized
*supplied* facts. There are no market-data requests, news scraping, inference,
trade directions, brokerage instructions or PAPER-certification effects.

Frozen parent: `253c1ae3f74c8a5a7221442aa1144fa96fe2af6a` on
`x23-shadow-features-v2`. Production R2.2 is a separate worktree.

## Why X7 is not another P5-9 implementation

The repository already contains `services/external_context/{global,
institutional,events,aggregate,integration}.py` and the P5-9 typed contracts.
Those types rely on an older index-market identity registry, unlike the five
X1–X6 research markets. X7 establishes a five-market, hashable bridge contract;
future adapters can reuse P5-9 outputs only where provenance, units and exact
market applicability have been verified. Neither engine replaces production.

## A-phase contracts

- `X7GlobalObservationV1`: strict controlled name/type/unit/session, source
  observation/publication/availability time, separate source/value proof.
- `X7InstitutionalFlowV1`: signed FII/DII *cash equity* observations in declared
  crore INR. Only NIFTY/SENSEX applicability is initially accepted; no
  commodity-specific conclusion is inferred from equity flows.
- `X7ScheduledEventV1`: sourced, explicitly applicable scheduled fact, distinct
  from exchange-session truth or an authoritative risk restriction.
- `X7ContextCaptureV1`: one market/session/as-of capture with unique names and
  IDs, explicit point-in-time vs retrospective capture mode, deterministic hash.
- `X7ContextValidationV1`: per-family availability, explicit blockers and
  warnings, linked to exact capture content hash.

`AVAILABLE` requires independently *supplied* source and measurement proof
flags. Those flags are claims by the upstream capture, not independent source
authentication. `point_in_time_verified` cannot be true for historical retrieval,
future source availability, absent availability timestamps or unverified
source records. A confirmed future scheduled date is allowed when the event
announcement itself was already available as of capture time.

No source is mandatory in A. A missing family is UNAVAILABLE; the whole capture
is PARTIAL when some, but not all, available families are present. Empty or
unverified captures fail closed. P5-9 source-specific freshness rules, market
sessions, calendar ownership and portfolio policy are not duplicated here.

## Follow-on plan

- **B1**: verified provider-neutral global/India VIX and correlation-group
  adapters, clearly distinguishing index closes from futures and publication
  from observation.
- **B2**: compatible P5-9 FII/DII index-flow bridge; commodity institutional
  context remains unavailable without commodity-native evidence.
- **B3**: confirmed calendar-event bridge, affected-market/session mapping and
  event-risk description without risk/trade authority.
- **B4**: normalized research view, time-aligned descriptive grouping,
  deterministic replay, source-authenticity limitations and anti-duplication.
- **B5**: scoped regression, authority audit, exact-file Git freeze and push.

## Explicit limits

No source credentials, network calls, yfinance fallback, AI-generated event,
sentiment model, independently weighted trade vote, new-entry restriction,
capital allocation, order, broker submission or certification counter. All
source and runtime families must be audited before production integration.
