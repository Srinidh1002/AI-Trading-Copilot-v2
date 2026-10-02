# X7-B1 — Offline Global/India VIX Evidence Adapter

Parent: frozen X6 `253c1ae3f74c8a5a7221442aa1144fa96fe2af6a`; X7-A is installed but uncommitted. Research worktree only. The production R2.2 PAPER worktree and certification records are out of scope.

## Contract and adapter

New `services/x7/global_adapter_v1.py` contains three immutable zero-authority results and two pure functions:

- `X7GlobalSourceProofV1` is the independent **caller-supplied assertion** of name, exact type, unit, source ID, source-record ID, session meaning, observation/publication/availability timestamps and separate source, timestamp-semantics, value-unit and measurement-verification flags. Construction never establishes authenticity of the underlying provider; it validates that the assertion is internally consistent.
- `adapt_x7_global_observation_v1(raw_record, proof, as_of, max_age_seconds)` checks exact matching between the normalized raw fields and proof. It returns an existing `X7GlobalObservationV1` plus raw/proof content hashes and declared freshness budget. Numeric strings, unsupported fields, guessed timestamps, silent unit conversions and lookahead are rejected. `AVAILABLE` requires actual provided measurement and all verification flags, `STALE` retains known numbers without declaring current availability, `UNVERIFIED` never promotes unverified values, and `UNAVAILABLE` represents a missing measurement.
- `adapt_x7_global_batch_v1(market, session_id, capture_id, as_of, raw_records, proofs, max_age_seconds_by_name)` requires one proof and one explicit freshness budget for each unique controlled global name; duplicate source-record IDs and missing policy are errors. Its results are sorted and deterministically hashed. It groups related sources **descriptively**, not as independent votes or aggregated scores.

The raw normalized record must contain exactly:
`name`, `observation_type`, `unit`, `session_reference`, `source_id`, `source_record_id`, `observed_at`, `published_at`, `available_at`, `value`, `previous_value`.
Timestamp fields must be timezone-aware Python `datetime` values (or `None` for explicitly unknown publication/availability on **unverified** records). An upstream licensed source adapter—not X7—must prove the source field semantics and convert its provider payload to this normalized shape. No such live adapter or independent source verification is supplied in B1.

`SP500`, `NASDAQ`, `DOW_JONES`, `NIKKEI_225`, `HANG_SENG`, `SHANGHAI_COMPOSITE` are `INDEX_CLOSE`, **not live futures**. `GIFT_NIFTY` has its separate future identity. `INDIA_VIX` is an observed volatility index in `PERCENT_ANNUALIZED`, **not** X6 model-implied volatility. `US_10Y_YIELD` and `INDIA_10Y_YIELD` are in `PERCENT_PER_YEAR`, not decimals, basis points or trading signals. USD/INR, DXY and crude retain their exact X7-A units; no provider-dependent unit conversion is inferred.

## Source group identities (one descriptive group each)

`GIFT_INDEX_FUTURE`, `US_EQUITY_CLOSES`, `ASIAN_EQUITY_CLOSES`, `CRUDE_BENCHMARKS`, `FX_CONTEXT`, `BOND_YIELDS`, `INDIA_VOLATILITY`. Within a group, multiple records must not later be counted as separate confirmations. B1 does not compute correlations, directions, causality, weights or an aggregate confidence score. Any empirically calibrated correlation model belongs to a separately validated later phase.

## Time and availability

B1 requires three separate source times when a source is asserted verified:
`observed_at <= published_at <= available_at <= as_of`. Any future source observation, publication or availability time is rejected, including historical/replay inputs. The caller must provide a **positive finite per-name freshness budget**—for example, an overnight index close and a current India VIX quote generally need different policies. B1 never guesses an exchange close, freshness window or publication delay. `source_verified`, `timestamp_semantics_verified`, `value_unit_verified` and `value_verified` are explicit upstream claims, not a substitute for independent provider evidence.

`X7GlobalBatchV1.observations` can be projected to an `X7ContextCaptureV1.global_observations` tuple. The caller still owns the capture's independent `capture_verified`, `historical_retrieval` and `point_in_time_verified` flags and other families (institutional/event). B1 cannot elevate retrospective captures or increment certification counts.

## Offline validation

The B1 focused suite tests all fourteen controlled names across all five target markets, exact proof/raw consistency, missing data, stale vs unavailable status, future timestamps, source/units spoofing, yield numeric boundaries, immutable hashes, group membership, ordering, duplicate names/record IDs, original X7-A capture compatibility and a static authority scan. FYERS/provider compatibility regression and full Brain + X1–X7 regression must be run in the user's local dedicated `.venv312` before moving to B2.

## Explicit non-goals and limitations

No FYERS/global-source network requests, credentials, assumed real-time India VIX access, news or event harvesting, market direction, independent vote, buy/sell decision, risk sizing, contract selection, position changes, broker order placement, PAPER counts or live eligibility. Hashes establish internal reproducibility, not external publisher authenticity. B2 will cover independently supplied index FII/DII cash-flow evidence; B3 covers scheduled events; B4 owns research-view integration and replay; B5 owns the scoped Git freeze.
