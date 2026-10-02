# X7-B2 — Offline institutional-flow adapter

## Scope

Adds a pure provider-neutral bridge between **supplied, normalized** Indian
FII/DII cash-equity records and the immutable X7-A institutional contract.
It is additive to X7-A/B1 and does not change any frozen production or research
module. No external provider connection, news parsing, investment inference,
position sizing, broker orders or PAPER-certification operations are present.

### Input contract

- One record must carry exactly the declared record fields; the caller supplies
  a separately constructed `X7InstitutionalSourceProofV1` attestation with
  exact identity, trading date, source record, source/observation/publication/
  availability times, unit and final/provisional publication state.
- Only the canonical `CRORE_INR` **cash-equity flow** unit is accepted. Rupees,
  derivatives notional and contract counts are not converted or inferred.
- Source IDs, source-record IDs, provenance timestamps and market applicability
  are exact-match requirements. Unsupported, ambiguous or future-available
  records fail closed. Caller assertions do not independently authenticate a
  publication or prove the upstream source was available in real time.
- Provisional figures are audit-visible but are `UNVERIFIED` in the X7-A
  contract; only source/units-verified **FINAL** figures can be `AVAILABLE`.
  Stale final figures remain explicitly `STALE`.
- Reported zero is distinct from `None`. A verified single-side report can be
  available while B2 separately marks completeness `PARTIAL`; it must never
  be treated as a complete FII/DII pair.
- The `trading_date` is distinct from the observation/publication/availability
  timestamps. Yesterday's published cash flow never becomes today's trading
  session flow just because it was captured today.
- Only NIFTY and SENSEX are eligible for India cash-equity-flow context.
  CRUDEOILM, GOLDM and NATGASMINI need separately sourced commodity-specific
  positioning rather than an attributed FII/DII cash number.

### Public functions and outputs

- `adapt_x7_institutional_flow_v1` converts an exact raw record and typed
  upstream proof into an immutable `X7InstitutionalAdaptedFlowV1`, retaining
  the X7-A `X7InstitutionalFlowV1`, source record ID and raw/proof hashes.
- `adapt_x7_institutional_batch_v1` checks one-to-one records/proofs,
  duplicate dates/record IDs, market applicability, age policy and immutable,
  date-sorted batch provenance. A batch never represents a trading vote.
- Hashes ensure deterministic comparison and detect changed supplied inputs;
  they are *not* proof of the publisher's identity or original data quality.

### Follow-on work

X7-B3 will adapt confirmed scheduled-event facts and retain explicit event
calendar ownership. X7-B4 will consolidate provenance and read-only research
views, followed by final scoped audit and Git freeze. All X7 modules remain
research-only. No X7 signal can directly change the production PAPER runtime,
certification counters or trading policy.
